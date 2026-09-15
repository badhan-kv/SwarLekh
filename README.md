# SwarLekh

*Swar* (voice/tone) + *Lekh* (written text) — speech becoming writing, which
is exactly what this app does.

Hotkey-driven voice dictation: press a combo, speak, get grammatically clean
text (or well-structured notes) pasted at your cursor — powered by free-tier
Groq (Whisper) and Mistral APIs, nothing runs or is stored on a server you
don't control.

## Logo

Generated programmatically by `branding.py` (a PIL-drawn soundwave badge, no
external image tool used) — `assets/swarlekh_logo.png` and
`assets/swarlekh_logo.svg` are the exportable brand mark; `assets/swarlekh_icon.ico`
is the multi-resolution icon used for the Start Menu/Startup shortcuts. The
tray icon itself is drawn at runtime by `branding.tray_icon()`: solid indigo
circle when idle, red circle with a white ring while recording — two
independent signals (color AND shape) so the state reads clearly even
without color vision.

## How it works

```
Ctrl+Win by default, tap: toggle / hold: push-to-talk (configurable — tray menu "Change hotkey...")
    -> record mic audio (audio.py)
    -> Groq Whisper transcription (groq_client.py)
    -> detect spoken command: "transcribe" vs "take notes" (command_router.py)
    -> deterministic time/number/currency normalization (normalize.py)
    -> Mistral cleanup / note-restructuring, verified + auto-retried (mistral_cleanup.py, verify.py)
    -> copy to clipboard + simulate Ctrl+V paste (paste.py)
    -> log the exchange locally, 30-day retention (history.py)
```

Say **"transcribe"** or **"voice dictation"** at the start of what you say for
word-for-word cleanup: only disfluencies (filler words, false starts, exact
repetition) are removed and punctuation is added — grammar is deliberately
**not** fixed, even if ungrammatical as spoken, and nothing is paraphrased.
Say **"take notes"** instead to have a rambling stream of thoughts reorganized
into structured plain-text notes (paragraphs/bullets grouped by topic, even
across interleaved mentions) — each point keeps its speaker's exact wording,
nothing is summarized, condensed, or blended between points. In both modes, a
misheard/garbled word is kept exactly as Whisper transcribed it rather than
"corrected" to something that merely sounds plausible, and a genuinely
unclear segment is flagged with `[UNCLEAR]` rather than invented. If you
forget the trigger phrase, it defaults to transcribe mode.

Time (both modes), numbers (≥5), and currency get normalized deterministically
by `normalize.py` — not by the LLM. See "Why code, not more prompting" below.

## Installation

There are three ways to install SwarLekh. **If you just want to run the
app, use Option A** — it's the one-click path with no Python required.
Options B and C are for building from source. Whichever you pick, you'll
need a free Groq API key (console.groq.com) and a Mistral API key
(console.mistral.ai) ready — you'll be prompted for both on first launch.

### Option A — one-click installer (recommended)

1. Download `SwarLekh-Setup.exe` from the
   [latest release](https://github.com/badhan-kv/SwarLekh/releases/latest).
2. Run it. No admin rights needed, no Python, nothing to build or
   compile — it walks through the same install wizard as any other
   Windows program. It installs to `%LOCALAPPDATA%\Programs\SwarLekh`,
   adds a Start Menu entry, and offers optional Desktop and "launch at
   login" shortcuts.
3. Launch SwarLekh from the Start Menu.

Fully tested end-to-end on the machine that built it (install → uninstall
→ reinstall, including reinstalling over a running instance) — this is
the intended path for anyone who just wants to run the app.

**Uninstalling**: run the uninstaller from Add/Remove Programs.
`%LOCALAPPDATA%\SwarLekh` (your cached API keys' Credential Manager
entries aside, that folder only holds non-secret settings) is **never**
touched by uninstall — your saved hotkey, save location, and dictation
history survive a reinstall (verified live, not just by reading the
script).

### Option B — from source (Python required)

1. Install dependencies (pinned versions, for reproducible/reviewable
   installs):
   ```
   pip install -r requirements.txt
   ```
2. Launch it once to confirm it works and enter your keys:
   ```
   python tray.py
   ```
   A small GUI window pops up asking for your Groq and Mistral API keys the
   first time (or whenever cached keys are missing/rejected) — no console
   input needed.
3. **Set up auto-start / Start Menu access** (optional, recommended). Create
   a shortcut with:
   - **Target**: your `pythonw.exe` (same folder as `python.exe` —
     find it with `where python`), **not** `python.exe` and **not**
     `run.bat`. `pythonw.exe` runs without any console window at all, which
     is what you want for a background tray app — pointing a shortcut at
     `run.bat` instead leaves a blank console window open for the app's
     entire lifetime.
   - **Arguments**: `tray.py`
   - **Start in**: this project's folder (so `tray.py` and its config files
     resolve correctly)

   Place a copy of that shortcut in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\`
   for Start Menu access, and another in
   `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\` to auto-start
   at login. Delete either `.lnk` file to remove it.

   `run.bat` still exists for **manual debugging only** — it keeps a
   console window open so you can see `[UNCLEAR]`/verification warnings
   print live. Never point a permanent shortcut at it.

### Option C — standalone `.exe`, built yourself (no Python needed to run it)

SwarLekh compiles to a single native Windows executable via
[Nuitka](https://nuitka.net) (not a bundler — see "Packaging status" below
for why PyInstaller was ruled out). To build it:
```
pip install -r requirements-build.txt
nuitka --onefile --standalone --zig --enable-plugin=tk-inter ^
  --windows-console-mode=disable --windows-icon-from-ico=assets/swarlekh_icon.ico ^
  --include-module=keyring.backends.Windows --include-package=mistralai ^
  --output-filename=SwarLekh.exe --output-dir=dist_nuitka tray.py
```
This produces `dist_nuitka\SwarLekh.exe` (~44.5MB) — double-click it, or
point a Start Menu/Startup shortcut straight at it (no `pythonw.exe` needed;
it's already windowed, so it never opens a console). This is the exe
packaged into the Option A installer's release; to build the installer
itself:
```
ISCC.exe installer.iss
```
producing `installer_output\SwarLekh-Setup.exe`.

### Where your keys live

Windows Credential Manager (via the `keyring` library), never a plaintext
file — this app is meant to be shared with other people, so plaintext JSON
wasn't an acceptable place to keep secrets. Each user's keys are private to
their own Windows login. You can view/remove them yourself under Control
Panel → Credential Manager → Windows Credentials → look for entries named
"SwarLekh". To change keys later, use the tray icon's **"Edit API Keys..."**
menu item — no need to dig through Credential Manager by hand.

If an API ever rejects a cached key (401/403), it's cleared automatically and
you're prompted again next time. If you have an old plaintext config from an
earlier version of this app (or its pre-rename `aiVoiceDictation` name), your
keys are migrated into Credential Manager automatically, once, the first time
this version runs — and the old plaintext copy is deleted immediately
after migrating, not left sitting on disk (an earlier version of this
migration left the old file's plaintext keys behind indefinitely; fixed).

## Hotkey: Ctrl+Win by default (or click the tray icon), fully configurable

Tap to toggle recording on/off (hands-free); hold to record only while held
(push-to-talk). Clicking the tray icon does the same thing as a quick tap —
first click starts recording, next click stops it (no push-to-talk
equivalent for clicking, since a click has no "hold duration"). Both
triggers share the same `HotkeyStateMachine`, so they can't get out of sync
with each other. If a different shortcut fires while you're mid-press (e.g.
an unrelated app shortcut sharing one of your combo's keys), dictation
aborts cleanly instead of misfiring — see `hotkey.py`'s
`HotkeyStateMachine.cancel()`.

Change it any time via the tray menu's **"Change hotkey..."** — press and
hold your desired combination (2+ keys, e.g. Ctrl+Win, Ctrl+Alt+Z), release,
and it's captured and persisted immediately (`hotkey_combo.py` serializes
the combo to/from `config.json`; `hotkey_dialog.py` captures it via a real
global keyboard listener, since tkinter's own key bindings can't see
modifier-only combos like Ctrl+Win).

### Hotkey history

Combos rejected along the way, and why:

| Combo | Rejected because |
|---|---|
| Ctrl+Alt+Space | Word/editors already use it for a non-breaking space |
| Ctrl+Shift+Space | Same, Word's actual default for non-breaking space |
| Right Ctrl+Right Shift | Right Ctrl doesn't physically exist — replaced by the Copilot key on this keyboard |
| Bare Ctrl+Shift | Can collide with Windows' input-language switcher (Settings > language hotkeys) |
| Bare Ctrl+Alt | Literal prefix of Ctrl+Alt+Del — Windows' Secure Attention Sequence strips the Del keystroke before any app-level hook sees it, so our foreign-key-cancel logic can never catch it |

The original default, Ctrl+Alt+Z, avoided all of the above (no Shift, no
Space, not left/right-specific, and Z makes it an ordinary combo the OS
treats no differently from any other shortcut). The current default,
**Ctrl+Win**, is more comfortable to hold one-handed — no bare-combo OS
reservation applies to it either (Windows only intercepts Win+`<key>` when
a third key joins, e.g. Win+D, not a bare Ctrl+Win press/release).

## Modules

| File | Responsibility |
|---|---|
| `config.py` | Load/save/prompt for API keys (Credential Manager via `keyring`) + settings (`config.json`) |
| `branding.py` | Programmatic logo/tray-icon generation (PIL, no external assets) |
| `audio.py` | Mic capture (start/stop, arbitrary duration) |
| `groq_client.py` | Groq Whisper transcription, with retry/backoff |
| `normalize.py` | Deterministic regex-based time/number/currency conversion (not LLM) |
| `mistral_cleanup.py` | Grammar cleanup / note restructuring via Mistral, with verify-and-retry |
| `verify.py` | Post-hoc check that cleanup output didn't drop/substitute source content |
| `command_router.py` | Detects the spoken "transcribe"/"take notes" trigger |
| `retry.py` | Shared exponential-backoff retry helper |
| `history.py` | One JSON record per dictation, 30-day purge |
| `hotkey.py` | Tap-toggle vs hold-to-talk state machine (pure logic) |
| `hotkey_combo.py` | Serializes the configurable hotkey combo to/from `config.json` |
| `gui_root.py` | Single persistent Tk root + `run_on_gui_thread()` — see "GUI architecture" below |
| `keys_dialog.py` | API key entry dialog (Toplevel of the shared root) |
| `hotkey_dialog.py` | Hotkey-capture dialog (Toplevel of the shared root, real pynput listener) |
| `paste.py` | Clipboard copy + simulated Ctrl+V |
| `tray.py` | Wires everything into a background tray app |
| `smoke_test.py` | Runs the real pipeline against recorded WAV files (no live paste) |

### GUI architecture: one shared Tk root, not one per dialog

Each dialog used to create its own `tkinter.Tk()`. That broke badly once
there were three of them: a fresh `Tk()` is a fully independent Tcl
interpreter, and creating
one from inside pystray's own hand-rolled Windows message loop produced
dialogs that rendered but never processed input, plus a separate taskbar
entry per dialog. Fixed per pystray's own recommended pattern for non-macOS
platforms: `gui_root.py` creates one `Tk()` root at startup; pystray's icon
loop runs on a background thread while that root's `mainloop()` is the
app's one real GUI event loop; every dialog is a `Toplevel` of the shared
root; cross-thread calls go through `gui_root.run_on_gui_thread()`.

### Why code, not more prompting

An earlier version asked the LLM to also handle time/number/currency
formatting via prompt instructions. As the prompt grew to cover more rules,
the model (`ministral-8b-latest`, the only one this free tier allows) started
corrupting unrelated content — "before Thursday" became "before 16:00" once
it was juggling a long formatting-rules section. Two structural fixes
replaced further prompt tweaking:

1. **`normalize.py`** converts time/number/currency deterministically via
   regex, before the LLM ever sees the text. It only converts patterns it's
   certain about, and deliberately leaves genuinely ambiguous cases (e.g. bare
   "1500 hours" — clock time or a duration?) untouched rather than guessing.
2. **`verify.py`** checks after the fact, rather than hoping the prompt
   worked: `missing_words()` confirms every non-filler source word survived
   into the cleaned output. A dropped or silently-substituted word (a
   substitution makes the original go missing too) triggers an automatic
   retry in `mistral_cleanup.clean()` with a corrective follow-up naming
   exactly what was lost, up to `MAX_VERIFY_RETRIES` extra attempts.

Known limit: the word-presence check can't catch a substitution when the
substituted word already exists elsewhere in the same document (e.g. a
pronoun swapped for a name that's also used in another sentence) — that
needs per-sentence alignment to catch reliably, a materially bigger project
than this app currently needs.

## Testing

```
python -m pytest -q
```

145 unit tests cover config (including the plaintext-key-scrub migrations),
retry/backoff, the Groq and Mistral clients, `normalize.py`'s
time/number/currency conversion, `verify.py`'s missing-word detection (and
`mistral_cleanup.clean()`'s retry loop around it), the command router,
history retention, the hotkey state machine (including the
foreign-key-cancel path), hotkey-combo serialization, `paste.py`'s
clipboard-restore behavior, and the tray-menu dialog reentrancy guard — all
with mocked network/SDK/GUI calls, no live API calls or real audio needed.
`audio.py`'s WAV encoding is tested directly; the live hotkey/mic/tray-icon
path is not unit-tested (pure I/O against the OS). The GUI dialogs (`keys_dialog.py`/`hotkey_dialog.py`)
*are* additionally covered by a real end-to-end script —
`scratchpad/verify_gui_architecture.py` (not part of the pytest suite; it
drives real Tk widgets and real simulated keystrokes from a separate thread,
proving the dialog-freeze fix rather than just asserting it).

`smoke_test.py` runs the *real* Groq → router → Mistral pipeline against WAV
files in the project root, using your cached credentials — printing raw vs.
cleaned output for review. It deliberately skips the clipboard-paste step so
it never disturbs whatever window has focus on your screen.

## Packaging status (done)

A one-click installer (`installer.iss`, Inno Setup — per-user install,
Start Menu + optional Desktop/Startup shortcuts, proper uninstaller, never
touches `%LOCALAPPDATA%\SwarLekh` user data) for sharing with others who
shouldn't need Python installed or see the source — see Option A above.

PyInstaller was tried first and ruled out: on this machine, Windows Defender
blocks the icon-embedding step of any PyInstaller Windows build with a
false-positive ML-heuristic detection (`Wacatac.B!ml`) — a well-documented
PyInstaller issue (pyinstaller/pyinstaller#8320), not something fixable by
changing icons, and not something to work around via a Defender exclusion or
disabling real-time protection on a corporate machine. Switched to
**Nuitka** (a true compiler, not a self-extracting bundler) instead.

**Nuitka build works and is Defender-clean**, verified via
`Get-MpThreatDetection` (the actual detection log, not just a successful
exit code) after every build attempt — zero detections across all of them.
Build command:
```
nuitka --onefile --standalone --zig --enable-plugin=tk-inter \
  --windows-console-mode=disable --windows-icon-from-ico=assets/swarlekh_icon.ico \
  --include-module=keyring.backends.Windows --include-package=mistralai \
  --output-filename=SwarLekh.exe --output-dir=dist_nuitka tray.py
```
`--zig` (installed via `pip install ziglang`) is the C backend — MSVC on
this machine is too old for Python 3.14 and MinGW64 doesn't support Python
3.13+. `--enable-plugin=tk-inter` is required (not optional) once the app
uses tkinter this heavily — without it the exe *builds* successfully but
fails at launch. Result: ~44.5MB `dist_nuitka\SwarLekh.exe`, launches
cleanly, no console window, correct icon.

The installer is built (`ISCC.exe installer.iss`) and has been run
end-to-end on this machine, including install → uninstall → reinstall over
a running instance, verifying user data survives and no leftover files or
broken shortcuts remain.

## Security notes

- **API keys live in Windows Credential Manager** (via `keyring`), never a
  plaintext file — each user's keys are private to their own Windows login.
  Only non-secret settings (hotkey, save location) live in the small
  `%LOCALAPPDATA%\SwarLekh\config.json` file, protected by that folder's
  standard per-user Windows ACLs (owner + Administrators + SYSTEM only).
- Keys are sent only as `Authorization: Bearer <key>` headers to Groq's and
  Mistral's official API endpoints (`api.groq.com`, via the official
  `mistralai` SDK) — never logged, printed, or written anywhere else. Grepped
  the whole codebase to confirm no `print`/log statement includes a key value.
- A rejected key (401/403) is cleared from Credential Manager automatically
  (`config.logout()`) rather than retried indefinitely.
- **Migrating from an old plaintext config now scrubs the source file**, not
  just this app's own storage — a real bug found and fixed during a
  security review: the pre-rename `aiVoiceDictation` app's old
  `config.json` kept both real API keys in plaintext indefinitely even after
  they'd been copied into Credential Manager, silently defeating the whole
  point of that move. If you're upgrading from an older version and that
  old file still exists on disk with keys in it, running this version once
  will migrate-and-scrub it automatically.
- **Dictated text no longer lingers on the clipboard.** `paste.py` restores
  whatever was on the clipboard before your dictation, right after the
  paste keystroke — since this is a general dictation tool, the clipboard
  could otherwise hold anything you happened to say (a password read aloud,
  personal details) for as long as nothing else overwrote it, feeding
  Windows Clipboard History (Win+V) and, if you have it on, Cloud Clipboard
  sync to Microsoft's servers.
- No `eval`/`exec`/`os.system`/`subprocess`/`shell=True`/pickle/YAML-load
  anywhere in the app's own codebase (verified by grep) — no code-injection
  surface.
- A server-supplied `Retry-After` header is capped at 30s before it's ever
  passed to `time.sleep()`, so a malformed or malicious value from Groq or
  Mistral can't hang the app indefinitely.
- Credential prompting never blocks pynput's low-level keyboard-hook thread:
  an earlier version called a blocking prompt directly from the hotkey's
  key-press callback, which could stall system-wide keyboard input while
  waiting for input. It now resolves credentials on a background thread and
  through a GUI dialog instead.
- **Dependencies are version-pinned** (`requirements.txt`,
  `requirements-build.txt`) rather than left open-ended — an unpinned
  install silently takes whatever the latest release of every dependency
  happens to be at install time, with no review point before it lands.
- The global keyboard hook (`tray.py`'s hotkey-matching logic) only ever
  holds currently-pressed keys in an in-memory set to detect your combo — it
  does not log or persist keystrokes anywhere; it is not a keylogger despite
  needing a system-wide hook to see modifier-only combos like Ctrl+Win.
- Recorded audio and transcripts are stored locally only (`history/`, 30-day
  retention); nothing is uploaded anywhere except the two API calls per
  dictation (Groq for STT, Mistral for cleanup).
- `.gitignore` excludes `history/`, `*.wav`, `dist_nuitka/`, and
  `CHECKPOINT.md` — no personal recordings, transcripts, or credentials are
  ever committed to git. Verified against the full commit history (not just
  the current working tree) before this repo was ever made public — no real
  API key, WAV file, or personal data appears in any past commit either.

## Known limitations / not yet built

- No phone/mobile client yet. A future direction: the core pipeline modules
  are plain Python with no Windows-specific code, so a future client could
  reuse the same Groq/Mistral call shape.
- The live hotkey → mic → paste path can only be verified by hand — it
  can't be exercised headlessly.

## License

Copyright (c) 2026 Khushaldas Vasant Badhan. All rights reserved.
