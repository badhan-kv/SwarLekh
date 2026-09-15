# SwarLekh

Hotkey-driven voice dictation for Windows: press a combo, speak, and get
clean text (or well-structured notes) pasted at your cursor — powered by
Groq (Whisper) for transcription and Mistral for cleanup.

## What it does

Say **"transcribe"** or **"voice dictation"** at the start of what you say
for word-for-word cleanup: filler words, false starts, and exact repetition
are removed and punctuation is added, but grammar is left exactly as
spoken and nothing is paraphrased. Say **"take notes"** instead to have a
rambling stream of thoughts reorganized into structured plain-text notes,
grouped by topic — each point keeps your exact wording, nothing is
summarized or blended together. If you forget the trigger phrase, it
defaults to transcribe mode.

A misheard or garbled word is kept exactly as transcribed rather than
"corrected" to something that merely sounds plausible, and a genuinely
unclear segment is flagged with `[UNCLEAR]` rather than guessed at. Times,
numbers, and currency amounts are converted to a consistent format
(24-hour time, digits, `$`/`€`/`£`) using fixed rules rather than left to
the AI to guess.

## Installation

You'll need a free Groq API key (console.groq.com) and a Mistral API key
(console.mistral.ai) — you'll be prompted for both on first launch.

### Option A — one-click installer (recommended)

1. Download `SwarLekh-Setup.exe` from the
   [latest release](https://github.com/badhan-kv/SwarLekh/releases/latest).
2. Run it. No admin rights needed, no Python required. It installs to
   your user profile, adds a Start Menu entry, and offers optional
   Desktop and "launch at login" shortcuts.
3. Launch SwarLekh from the Start Menu.

**Uninstalling**: run the uninstaller from Add/Remove Programs. Your
saved hotkey, save location, and dictation history survive a reinstall.

### Option B — from source (Python required)

```
pip install -r requirements.txt
python tray.py
```

A small window pops up asking for your API keys the first time. To have
SwarLekh start automatically, create a shortcut pointing at `pythonw.exe`
(not `python.exe`) with argument `tray.py`, and place it in
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\` (for Start Menu
access) and/or its `Startup\` subfolder (to auto-start at login).

### Option C — build the standalone exe yourself

```
pip install -r requirements-build.txt
nuitka --onefile --standalone --zig --enable-plugin=tk-inter ^
  --windows-console-mode=disable --windows-icon-from-ico=assets/swarlekh_icon.ico ^
  --include-module=keyring.backends.Windows --include-package=mistralai ^
  --output-filename=SwarLekh.exe --output-dir=dist_nuitka tray.py
```
Then build the installer with `ISCC.exe installer.iss` (requires
[Inno Setup](https://jrsoftware.org/isinfo.php)).

## Using it

Tap your hotkey (**Ctrl+Win** by default) to toggle recording on/off
hands-free, or hold it to record only while held (push-to-talk). Clicking
the tray icon does the same as a quick tap. Change the hotkey any time via
the tray menu's **"Change hotkey..."** — press and hold your desired
combination, release, and it's saved immediately.

Other tray menu options: **"Edit API Keys..."** to update your Groq/Mistral
keys, and **"Change save location..."** to choose where transcripts are
saved.

## Where your data lives

- **API keys**: Windows Credential Manager, never a plaintext file. Each
  Windows account's keys are private to that login. View or remove them
  under Control Panel → Credential Manager → Windows Credentials → entries
  named "SwarLekh".
- **Settings** (hotkey, save location): `%LOCALAPPDATA%\SwarLekh\config.json`.
- **Dictation history**: saved locally as JSON records, kept for 30 days
  by default, in the folder you choose (or a default `history/` folder).
- Nothing is uploaded anywhere except the two API calls per dictation —
  Groq for transcription, Mistral for cleanup.

## Privacy & security notes

- Keys are sent only as an `Authorization` header to Groq's and Mistral's
  official API endpoints over HTTPS — never logged or written anywhere else.
- The clipboard briefly holds your dictated text to paste it, then is
  restored to whatever it held before — dictated text doesn't linger in
  Windows Clipboard History or Cloud Clipboard sync.
- A rejected API key is cleared automatically rather than retried
  indefinitely, and you'll simply be prompted again.
- Dependencies are version-pinned for reproducible installs.
- The global hotkey listener only tracks which keys are currently held, to
  detect your combo — it does not log or store keystrokes anywhere.

## Known limitations

- The hotkey → microphone → paste flow requires a live desktop session
  (it can't run in a headless environment).

## Planned / possible future features

- A phone/mobile client — the transcription/cleanup pipeline itself is
  plain Python with no Windows-specific code, so it could be reused by a
  client on another platform.

## License

Copyright (c) 2026 Khushaldas Vasant Badhan. All rights reserved.
