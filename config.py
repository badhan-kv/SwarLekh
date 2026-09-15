"""Credential storage: API keys live in Windows Credential Manager via
`keyring` — not plaintext — since this app is shared with other users.
Non-secret settings (e.g. HISTORY_DIR) stay in a small JSON file. Migrates
automatically from the old plaintext-JSON key storage (this app's own
earlier version, and the pre-rename aiVoiceDictation app) on first load.
"""

import json
import os
from pathlib import Path

import keyring
import keyring.errors

_LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home()))
CONFIG_DIR = _LOCALAPPDATA / "SwarLekh"
CONFIG_PATH = CONFIG_DIR / "config.json"

_OLD_CONFIG_PATH = _LOCALAPPDATA / "aiVoiceDictation" / "config.json"

KEYRING_SERVICE = "SwarLekh"
REQUIRED_KEYS = ("GROQ_API_KEY", "MISTRAL_API_KEY")


def _read_raw() -> dict:
    """Non-secret settings only (e.g. HISTORY_DIR) — API keys never live here."""
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def _write_raw(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _get_key(name: str) -> str | None:
    return keyring.get_password(KEYRING_SERVICE, name)


def _set_key(name: str, value: str) -> None:
    keyring.set_password(KEYRING_SERVICE, name, value)


def _delete_key(name: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass


def _migrate_plaintext_keys(raw: dict) -> None:
    """Move any API keys found in this app's own plaintext file into
    Credential Manager, then strip them from the JSON — one-time, idempotent.
    (An earlier version of this app stored keys in this same file.)"""
    changed = False
    for key_name in REQUIRED_KEYS:
        if raw.get(key_name) and not _get_key(key_name):
            _set_key(key_name, raw[key_name])
        if key_name in raw:
            del raw[key_name]
            changed = True
    if changed:
        _write_raw(raw)


def _migrate_old_config() -> None:
    """Pull keys (and any other settings) from the pre-rename aiVoiceDictation
    config into this app's storage, without overwriting anything already set.
    Once a key is safely in Credential Manager, it is scrubbed from the old
    plaintext file (same as _migrate_plaintext_keys does for this app's own
    file) — leaving it there would defeat the entire point of moving off
    plaintext storage."""
    if not _OLD_CONFIG_PATH.exists():
        return
    try:
        old_data = json.loads(_OLD_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    old_changed = False
    for key_name in REQUIRED_KEYS:
        if old_data.get(key_name) and not _get_key(key_name):
            _set_key(key_name, old_data[key_name])
        if key_name in old_data:
            del old_data[key_name]
            old_changed = True
    if old_changed:
        try:
            _OLD_CONFIG_PATH.write_text(json.dumps(old_data, indent=2), encoding="utf-8")
        except OSError:
            pass
    raw = _read_raw()
    changed = False
    for k, v in old_data.items():
        if k not in REQUIRED_KEYS and k not in raw:
            raw[k] = v
            changed = True
    if changed:
        _write_raw(raw)


def load_config() -> dict | None:
    """Return {"GROQ_API_KEY": ..., "MISTRAL_API_KEY": ...} if both are set
    (in Credential Manager), else None. Runs one-time migrations first."""
    _migrate_old_config()
    _migrate_plaintext_keys(_read_raw())
    data = {name: _get_key(name) for name in REQUIRED_KEYS}
    if not all(data.values()):
        return None
    return data


def save_config(data: dict) -> None:
    """Save API keys into Credential Manager. Any other field (e.g.
    HISTORY_DIR, if a caller passes it alongside) is preserved in the JSON."""
    for key_name in REQUIRED_KEYS:
        if data.get(key_name):
            _set_key(key_name, data[key_name])
    extras = {k: v for k, v in data.items() if k not in REQUIRED_KEYS}
    if extras:
        raw = _read_raw()
        raw.update(extras)
        _write_raw(raw)


def prompt_for_credentials() -> dict:
    """GUI prompt (tkinter dialog) — no console dependency, since the
    packaged .exe runs windowed with no console attached at all."""
    from keys_dialog import prompt_for_keys

    result = prompt_for_keys()
    if result is None:
        raise EOFError("credential entry cancelled")
    return result


def get_credentials() -> dict:
    """Load cached credentials, or prompt (GUI) and cache them if missing."""
    data = load_config()
    if data is not None:
        return data
    data = prompt_for_credentials()
    save_config(data)
    return data


def logout() -> bool:
    """Delete cached credentials from Credential Manager. Returns True if
    anything was actually removed."""
    removed = False
    for key_name in REQUIRED_KEYS:
        if _get_key(key_name) is not None:
            _delete_key(key_name)
            removed = True
    return removed


def get_history_dir() -> str | None:
    """Custom folder for saving transcripts/cleaned output, if the user set
    one via set_history_dir() or the tray menu. None means use the app's
    default (history.py's HISTORY_DIR)."""
    return _read_raw().get("HISTORY_DIR")


def set_history_dir(path) -> None:
    """Persist a custom folder for saving transcripts/cleaned output."""
    raw = _read_raw()
    raw["HISTORY_DIR"] = str(path)
    _write_raw(raw)


def get_hotkey() -> list | None:
    """Custom global hotkey combo (list of key-name strings, see
    hotkey_combo.py), if the user changed it via the tray menu. None means
    use the app's default."""
    return _read_raw().get("HOTKEY")


def set_hotkey(names) -> None:
    """Persist a custom global hotkey combo."""
    raw = _read_raw()
    raw["HOTKEY"] = list(names)
    _write_raw(raw)
