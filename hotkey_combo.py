"""Serialization between pynput Key/KeyCode objects and JSON-friendly hotkey
strings, shared by tray.py (combo matching) and hotkey_dialog.py (capture UI).
Keeping this separate from tray.py lets both import it without pulling in
pystray/audio/etc.
"""

from pynput import keyboard

DEFAULT_COMBO = ["ctrl", "win"]
# Two single-hand-reachable modifiers, no third key needed. Bare Ctrl+Alt was
# ruled out for the old default (literal prefix of Ctrl+Alt+Del, which Windows'
# Secure Attention Sequence strips before any app-level hook sees it) — Ctrl+Win
# has no equivalent OS-reserved bare combo: Windows only intercepts Win+<X> when
# a third key joins (Win+D, Win+L, etc.), not a bare Ctrl+Win press/release.

_MODIFIER_ORDER = ["ctrl", "alt", "shift", "win"]

_NAME_TO_KEY = {
    "ctrl": keyboard.Key.ctrl,
    "alt": keyboard.Key.alt,
    "shift": keyboard.Key.shift,
    "win": keyboard.Key.cmd,
}
_KEY_TO_NAME = {v: k for k, v in _NAME_TO_KEY.items()}

_DISPLAY_NAME = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
}


def key_to_str(key) -> str | None:
    """Convert a pynput Key/KeyCode to a JSON-friendly name. None for keys we
    don't support in a combo (e.g. media keys, function keys)."""
    if key in _KEY_TO_NAME:
        return _KEY_TO_NAME[key]
    char = getattr(key, "char", None)
    if char and char.isprintable():
        return char.lower()
    return None


def str_to_key(name: str):
    if name in _NAME_TO_KEY:
        return _NAME_TO_KEY[name]
    return keyboard.KeyCode.from_char(name)


def combo_to_strs(keys) -> list[str]:
    """Deterministic ordering: modifiers first (Ctrl, Alt, Shift, Win), then
    any other key. Drops keys we can't serialize."""
    names = {n for n in (key_to_str(k) for k in keys) if n}
    ordered = [n for n in _MODIFIER_ORDER if n in names]
    ordered += sorted(names - set(_MODIFIER_ORDER))
    return ordered


def strs_to_combo(names) -> set:
    return {str_to_key(n) for n in names}


# Windows virtual-key codes for each side of every modifier (GetAsyncKeyState
# distinguishes left/right, so a modifier counts as down if either side is).
_MODIFIER_VKS = {
    "ctrl": (0xA2, 0xA3),
    "alt": (0xA4, 0xA5),
    "shift": (0xA0, 0xA1),
    "win": (0x5B, 0x5C),
}


def _default_is_down(vk: int) -> bool:
    import ctypes

    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def prune_released(held_keys, is_down=None) -> set:
    """Return `held_keys` minus any key the OS reports as not physically down.

    The listener's own held-key bookkeeping can go stale when a key-up is never
    delivered to the hook (Win+L / Win+D, UAC or lock-screen focus, the Start
    menu consuming the Win release). A stale 'win' would make a bare Ctrl press
    look like Ctrl+Win. Only modifiers and letters/digits are checked; any other
    key is kept as-is. If the OS query fails, the set is returned unchanged.
    """
    is_down = is_down or _default_is_down
    kept = set()
    for key in held_keys:
        name = key_to_str(key)
        if name in _MODIFIER_VKS:
            vks = _MODIFIER_VKS[name]
        elif name and len(name) == 1 and name.isascii() and name.isalnum():
            vks = (ord(name.upper()),)
        else:
            kept.add(key)
            continue
        try:
            down = any(is_down(vk) for vk in vks)
        except Exception:
            return set(held_keys)
        if down:
            kept.add(key)
    return kept


def combo_label(names) -> str:
    return "+".join(_DISPLAY_NAME.get(n, n.upper()) for n in names)
