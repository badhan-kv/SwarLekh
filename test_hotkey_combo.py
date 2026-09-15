from pynput import keyboard

import hotkey_combo


def test_default_combo_is_ctrl_win():
    assert hotkey_combo.DEFAULT_COMBO == ["ctrl", "win"]


def test_key_to_str_modifiers():
    assert hotkey_combo.key_to_str(keyboard.Key.ctrl) == "ctrl"
    assert hotkey_combo.key_to_str(keyboard.Key.alt) == "alt"
    assert hotkey_combo.key_to_str(keyboard.Key.shift) == "shift"
    assert hotkey_combo.key_to_str(keyboard.Key.cmd) == "win"


def test_key_to_str_character_key():
    assert hotkey_combo.key_to_str(keyboard.KeyCode.from_char("z")) == "z"


def test_key_to_str_unsupported_key_returns_none():
    assert hotkey_combo.key_to_str(keyboard.Key.f5) is None


def test_str_to_key_roundtrip_modifiers():
    for name in ("ctrl", "alt", "shift", "win"):
        key = hotkey_combo.str_to_key(name)
        assert hotkey_combo.key_to_str(key) == name


def test_str_to_key_roundtrip_char():
    key = hotkey_combo.str_to_key("z")
    assert hotkey_combo.key_to_str(key) == "z"


def test_combo_to_strs_orders_modifiers_first():
    keys = {keyboard.KeyCode.from_char("z"), keyboard.Key.alt, keyboard.Key.ctrl}
    assert hotkey_combo.combo_to_strs(keys) == ["ctrl", "alt", "z"]


def test_combo_to_strs_drops_unsupported_keys():
    keys = {keyboard.Key.ctrl, keyboard.Key.f5}
    assert hotkey_combo.combo_to_strs(keys) == ["ctrl"]


def test_strs_to_combo_roundtrip():
    names = ["ctrl", "win"]
    combo = hotkey_combo.strs_to_combo(names)
    assert combo == {keyboard.Key.ctrl, keyboard.Key.cmd}
    assert hotkey_combo.combo_to_strs(combo) == names


def test_combo_label_formats_display_names():
    assert hotkey_combo.combo_label(["ctrl", "win"]) == "Ctrl+Win"
    assert hotkey_combo.combo_label(["alt", "z"]) == "Alt+Z"
