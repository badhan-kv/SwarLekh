"""SwarLekh background tray app: hotkey -> record -> transcribe -> clean up -> paste -> log."""

import sys
import threading
import traceback

import pystray
from pynput import keyboard

import audio
import branding
import command_router
import config
import gui_root
import groq_client
import history
import hotkey_combo
import mistral_cleanup
import paste
from hotkey import HotkeyStateMachine
from retry import get_status

APP_NAME = "SwarLekh"


def _ensure_output_streams() -> None:
    """The packaged exe (built with --windows-console-mode=disable) has NO
    console at all: sys.stdout/stderr are None, and any print() call would
    crash with AttributeError the first time it runs (e.g. the very first
    auth error or [UNCLEAR] flag). Same is true running via pythonw.exe.
    Redirect to a log file instead of silently dropping output, so
    diagnostics are still inspectable. Must run before anything else in
    main()."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = open(config.CONFIG_DIR / "swarlekh.log", "a", encoding="utf-8")
    sys.stdout = log_file
    sys.stderr = log_file

# Hotkey combo is configurable (tray menu "Change hotkey..."), persisted via
# config.get_hotkey()/set_hotkey() as a list of key-name strings (see
# hotkey_combo.py); defaults to hotkey_combo.DEFAULT_COMBO (Ctrl+Win). Matching
# logic below (_on_press/_on_release) is generic over combo size/contents —
# it still cancels if any other, non-combo key joins mid-press, whatever the
# configured combo is — see HotkeyStateMachine.cancel().


def _exclusive_dialog(method):
    """Decorator: only one tray-menu dialog at a time. pystray's message pump
    can re-enter action callbacks while a previous one's nested tkinter
    mainloop is still running (both pump the same Windows message queue on
    this thread) — without this guard, rapid re-clicks on a menu item stack
    multiple dialogs that then each need dismissing separately."""

    def wrapper(self, icon, item):
        if self._dialog_open:
            return
        self._dialog_open = True
        try:
            method(self, icon, item)
        finally:
            self._dialog_open = False

    return wrapper


def _is_auth_error(exc: Exception) -> bool:
    """True if `exc` looks like a rejected/invalid API key (401/403), from
    either groq_client's requests.HTTPError or mistral_cleanup's MistralError."""
    return get_status(exc) in (401, 403)


class DictationApp:
    def __init__(self):
        self._groq_key: str | None = None
        self._mistral_client = None
        self._recorder = audio.Recorder()
        self._icon = pystray.Icon(
            APP_NAME,
            branding.tray_icon(recording=False),
            f"{APP_NAME} (idle)",
            menu=pystray.Menu(
                pystray.MenuItem("Toggle Recording", self._on_icon_click, default=True, visible=False),
                pystray.MenuItem("Edit API Keys...", self._edit_api_keys),
                pystray.MenuItem("Change save location...", self._change_history_dir),
                pystray.MenuItem("Change hotkey...", self._change_hotkey),
                pystray.MenuItem("Quit", self._quit),
            ),
        )
        self._hotkey_sm = HotkeyStateMachine(
            self._on_start_recording, self._on_stop_recording, self._on_cancel_recording
        )
        self._hotkey_combo = hotkey_combo.strs_to_combo(config.get_hotkey() or hotkey_combo.DEFAULT_COMBO)
        self._held_keys: set = set()
        self._combo_engaged = False  # True from exact-match-down until this press-cycle ends or is cancelled
        self._listener: keyboard.Listener | None = None
        self._resolving_credentials = False  # guards against overlapping prompt threads
        self._dialog_open = False  # guards against stacked tray-menu dialogs, see _exclusive_dialog
        self._startup_failed = False

    def ensure_credentials(self) -> bool:
        """Use cached keys if we already have them; otherwise load from disk or
        prompt (blocking, hidden input) if missing entirely. Returns False only
        if prompting itself failed (e.g. no console attached)."""
        if self._groq_key and self._mistral_client:
            return True
        data = config.load_config()
        if data is None:
            print("SwarLekh: API keys missing — enter them now.")
            try:
                data = config.get_credentials()
            except (EOFError, KeyboardInterrupt):
                print("SwarLekh: no keys entered, cannot record yet.")
                return False
        self._groq_key = data["GROQ_API_KEY"]
        self._mistral_client = mistral_cleanup.make_client(data["MISTRAL_API_KEY"])
        return True

    def _resolve_credentials_async(self) -> None:
        """Background-thread wrapper around ensure_credentials() for _on_press,
        which must never block pynput's keyboard-hook callback thread."""
        try:
            self.ensure_credentials()
        finally:
            self._resolving_credentials = False

    def _has_credentials_or_start_resolving(self) -> bool:
        """True if ready to record now. If not, kicks off background credential
        resolution (never blocks the caller — pynput hook thread or pystray's
        icon thread, neither should be blocked on a console prompt) and
        returns False so the caller can swallow this trigger."""
        if self._groq_key and self._mistral_client:
            return True
        if not self._resolving_credentials:
            self._resolving_credentials = True
            threading.Thread(target=self._resolve_credentials_async, daemon=True).start()
        return False

    def _set_status(self, recording: bool) -> None:
        self._icon.icon = branding.tray_icon(recording=recording)
        self._icon.title = f"{APP_NAME} (recording)" if recording else f"{APP_NAME} (idle)"

    def _on_start_recording(self) -> None:
        self._set_status(recording=True)
        self._recorder.start()

    def _on_stop_recording(self) -> None:
        self._set_status(recording=False)
        wav_bytes = self._recorder.stop()
        threading.Thread(target=self._process, args=(wav_bytes,), daemon=True).start()

    def _on_cancel_recording(self) -> None:
        """A foreign key joined mid-press (e.g. this was Ctrl+Shift+N, not our
        hotkey) — stop and discard, do not transcribe/paste/log it."""
        self._set_status(recording=False)
        self._recorder.stop()

    def _process(self, wav_bytes: bytes) -> None:
        try:
            raw_transcript = groq_client.transcribe(wav_bytes, api_key=self._groq_key)
            if not raw_transcript.strip():
                # Accidental tap with no speech (or pure silence) — nothing to
                # clean up or paste; skip Mistral, clipboard, and history entirely.
                return
            mode, transcript = command_router.route(raw_transcript)
            output = mistral_cleanup.clean(self._mistral_client, mode, transcript)
            if mistral_cleanup.has_unclear_segment(output):
                print(
                    "SwarLekh: part of this dictation was too unclear to "
                    "transcribe confidently — look for [UNCLEAR] in the pasted text."
                )
            paste.paste_text(output)
            history.record_dictation(mode, raw_transcript, output)
        except Exception as exc:
            if _is_auth_error(exc):
                print("SwarLekh: API key was rejected — clearing cached keys, you'll be prompted next time.")
                config.logout()
                self._groq_key = None
                self._mistral_client = None
            traceback.print_exc()

    def _on_icon_click(self, icon, item) -> None:
        """Clicking the tray icon acts like a quick keyboard tap of the
        hotkey: first click starts recording (toggle mode), next click stops
        it. Reuses HotkeyStateMachine directly so click and keyboard triggers
        can't fight over inconsistent state."""
        if not self._has_credentials_or_start_resolving():
            return
        self._hotkey_sm.on_key_down()
        self._hotkey_sm.on_key_up()

    def _on_press(self, key) -> None:
        key = self._listener.canonical(key)  # normalize ctrl_l/ctrl_r etc. to one generic key
        self._held_keys.add(key)
        if not self._combo_engaged and self._held_keys == self._hotkey_combo:
            if not self._has_credentials_or_start_resolving():
                # This press is swallowed; press the hotkey again once the
                # background credential prompt (visible in the console) completes.
                return
            self._combo_engaged = True
            self._hotkey_sm.on_key_down()
        elif self._combo_engaged and key not in self._hotkey_combo:
            # A third, non-combo key joined mid-press — this was some other
            # shortcut (e.g. Ctrl+Shift+N), not a deliberate dictation trigger.
            self._combo_engaged = False
            self._hotkey_sm.cancel()

    def _on_release(self, key) -> None:
        key = self._listener.canonical(key)
        self._held_keys.discard(key)
        if self._combo_engaged and key in self._hotkey_combo and not self._hotkey_combo.issubset(self._held_keys):
            self._combo_engaged = False
            self._hotkey_sm.on_key_up()

    def run(self) -> None:
        """Runs pystray's icon loop on a background thread and the app's one
        real GUI event loop (gui_root's Tk mainloop) on the calling thread —
        the pattern pystray's own docs recommend for non-macOS platforms.
        Blocks until _quit() (or a startup failure) tears down the GUI root."""
        threading.Thread(target=self._run_icon, daemon=True).start()
        gui_root.get_root().mainloop()

    def _run_icon(self) -> None:
        if not self.ensure_credentials():
            print("SwarLekh: could not obtain API keys, exiting.")
            self._startup_failed = True
            gui_root.get_root().after(0, gui_root.get_root().destroy)
            return
        history.purge_older_than(history.DEFAULT_RETENTION_DAYS)
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()
        self._icon.run()

    @_exclusive_dialog
    def _change_history_dir(self, icon, item) -> None:
        """Tray menu: pick a new folder for saving transcripts/cleaned output
        via a normal Windows folder-picker dialog, persisted in config.json."""
        chosen = gui_root.run_on_gui_thread(self._pick_history_dir)
        if chosen:
            config.set_history_dir(chosen)
            print(f"SwarLekh: transcripts/output will now be saved to {chosen}")

    @staticmethod
    def _pick_history_dir() -> str:
        """Runs on the GUI thread (via gui_root.run_on_gui_thread) — the
        picker is parented to the app's one shared root, not a freshly
        created interpreter, so it behaves as a normal modal dialog."""
        from tkinter import filedialog

        root = gui_root.get_root()
        root.lift()
        root.focus_force()
        return filedialog.askdirectory(title="Choose where to save transcripts/output", parent=root)

    @_exclusive_dialog
    def _edit_api_keys(self, icon, item) -> None:
        """Tray menu: open the same GUI dialog used for first-run setup, with
        both fields left blank (re-enter both, rather than pre-filling a
        decrypted value into a GUI field) — saves to Credential Manager."""
        from keys_dialog import prompt_for_keys

        result = prompt_for_keys()
        if result is None:
            return
        config.save_config(result)
        self._groq_key = result["GROQ_API_KEY"]
        self._mistral_client = mistral_cleanup.make_client(result["MISTRAL_API_KEY"])
        print("SwarLekh: API keys updated.")

    @_exclusive_dialog
    def _change_hotkey(self, icon, item) -> None:
        """Tray menu: capture a new global hotkey combo via hotkey_dialog
        (needs a real pynput listener, not tkinter's own key bindings, to see
        modifier-only combos like Ctrl+Win)."""
        from hotkey_dialog import prompt_for_hotkey

        current_label = hotkey_combo.combo_label(hotkey_combo.combo_to_strs(self._hotkey_combo))
        names = prompt_for_hotkey(initial_label=current_label)
        if names is None:
            return
        config.set_hotkey(names)
        self._hotkey_combo = hotkey_combo.strs_to_combo(names)
        self._held_keys.clear()
        self._combo_engaged = False
        print(f"SwarLekh: hotkey changed to {hotkey_combo.combo_label(names)}")

    def _quit(self, icon, item) -> None:
        icon.stop()
        gui_root.get_root().after(0, gui_root.get_root().destroy)


def main() -> None:
    _ensure_output_streams()
    gui_root.init_root()
    app = DictationApp()
    app.run()  # blocks until quit, or a startup failure tears down the GUI root
    if app._startup_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
