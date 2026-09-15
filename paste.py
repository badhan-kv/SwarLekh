"""Copy text to the clipboard and simulate Ctrl+V to paste it at the cursor."""

import time

import pyperclip
from pynput.keyboard import Controller, Key

PASTE_SETTLE_SECONDS = 0.05
RESTORE_SETTLE_SECONDS = 0.2


def paste_text(text: str, controller: Controller | None = None) -> None:
    """Copy `text` to the clipboard, simulate Ctrl+V into the focused window,
    then restore whatever was on the clipboard beforehand.

    Dictated text can contain anything the user happens to say — including
    something sensitive (a password read aloud, personal details) — so it
    should not sit on the clipboard indefinitely afterward: Windows Clipboard
    History (Win+V) retains it, and Cloud Clipboard sync (if the user has it
    on) would ship it to Microsoft's servers, for as long as nothing else
    overwrites the clipboard first. Restoring the previous contents limits
    the exposure window to just the paste keystroke."""
    previous = pyperclip.paste()
    pyperclip.copy(text)
    time.sleep(PASTE_SETTLE_SECONDS)  # let the clipboard settle before the keystroke
    kb = controller or Controller()
    with kb.pressed(Key.ctrl):
        kb.press("v")
        kb.release("v")
    time.sleep(RESTORE_SETTLE_SECONDS)  # let the target app finish reading the clipboard
    pyperclip.copy(previous)
