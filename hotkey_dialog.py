"""tkinter dialog for capturing a new global hotkey combo.

Uses a temporary pynput listener (not tkinter's own key bindings) because
tkinter can't reliably see modifier-only combos like Ctrl+Win — the Windows
key in particular isn't delivered to normal widget key bindings the way a
low-level keyboard hook sees it.

Runs as a Toplevel of the app's single shared gui_root (see gui_root.py) so
it behaves as a normal modal dialog instead of an independent, separately-
interpreted top-level window.
"""

from pynput import keyboard

import gui_root
from hotkey_combo import combo_label, combo_to_strs


def prompt_for_hotkey(initial_label: str = "") -> list[str] | None:
    """Blocks until the user captures a combo (releases all keys after
    holding at least 2) or cancels. Returns a list of key-name strings, or
    None if cancelled. Safe to call from any thread (marshalled onto the
    GUI thread internally)."""
    return gui_root.run_on_gui_thread(lambda: _show(initial_label))


def _show(initial_label: str) -> list[str] | None:
    import tkinter

    result: dict = {"combo": None}
    held: set = set()
    max_held: set = set()
    finished = {"done": False}  # guards against re-entrant finish (e.g. two
    # keys of the combo releasing in quick succession each scheduling their
    # own after(_finish) before the first one runs)

    root = gui_root.get_root()
    top = tkinter.Toplevel(root)
    top.title("SwarLekh — Change Hotkey")
    top.attributes("-topmost", True)
    top.resizable(False, False)

    tkinter.Label(
        top,
        text="Press and hold your new hotkey combination,\nthen release all keys.",
        padx=24,
        pady=12,
    ).pack()
    preview = tkinter.StringVar(value=initial_label or "(waiting...)")
    tkinter.Label(top, textvariable=preview, font=("Segoe UI", 14, "bold"), padx=24, pady=8).pack()
    status = tkinter.StringVar(value="")
    tkinter.Label(top, textvariable=status, fg="gray", padx=24, pady=4).pack()

    listener_holder: dict = {}

    def _canonical(key):
        listener = listener_holder.get("listener")
        return listener.canonical(key) if listener else key

    def _update_preview():
        preview.set(combo_label(combo_to_strs(max_held)))

    def _on_press(key):
        if finished["done"]:
            return
        k = _canonical(key)
        held.add(k)
        max_held.update(held)
        try:
            top.after(0, _update_preview)
        except tkinter.TclError:
            pass  # window already closed

    def _finish():
        if finished["done"]:
            return  # already finished by an earlier queued call
        if len(max_held) < 2:
            status.set("Pick at least 2 keys (e.g. Ctrl+Win) and try again.")
            max_held.clear()
            preview.set("(waiting...)")
            return
        finished["done"] = True
        result["combo"] = combo_to_strs(max_held)
        listener_holder["listener"].stop()
        top.destroy()

    def _on_release(key):
        if finished["done"]:
            return
        k = _canonical(key)
        held.discard(k)
        if not held and max_held:
            try:
                top.after(0, _finish)
            except tkinter.TclError:
                pass

    listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
    listener_holder["listener"] = listener
    listener.start()

    def _on_cancel():
        if finished["done"]:
            return
        finished["done"] = True
        result["combo"] = None
        listener_holder["listener"].stop()
        top.destroy()

    button_frame = tkinter.Frame(top, pady=12)
    button_frame.pack()
    tkinter.Button(button_frame, text="Cancel", command=_on_cancel).pack()

    top.protocol("WM_DELETE_WINDOW", _on_cancel)
    top.lift()
    top.focus_force()
    top.grab_set()
    top.wait_window(top)
    listener.stop()
    return result["combo"]
