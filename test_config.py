import json

import pytest

import config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Every test gets its own tmp_path for CONFIG_DIR/CONFIG_PATH and
    _OLD_CONFIG_PATH (pointed at a location that doesn't exist by default),
    plus an in-memory fake Credential Manager — without this, tests would
    write into this machine's REAL Windows Credential Manager under the
    "SwarLekh" service, and _migrate_old_config() would read this machine's
    real %LOCALAPPDATA%\\aiVoiceDictation\\config.json."""
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "SwarLekh")
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "SwarLekh" / "config.json")
    monkeypatch.setattr(config, "_OLD_CONFIG_PATH", tmp_path / "aiVoiceDictation" / "config.json")

    fake_vault: dict[str, str] = {}
    monkeypatch.setattr(config, "_get_key", lambda name: fake_vault.get(name))
    monkeypatch.setattr(config, "_set_key", lambda name, value: fake_vault.__setitem__(name, value))

    def fake_delete(name):
        if name not in fake_vault:
            import keyring.errors

            raise keyring.errors.PasswordDeleteError()
        del fake_vault[name]

    monkeypatch.setattr(config, "_delete_key", fake_delete)
    return fake_vault


def test_load_config_missing_file_returns_none():
    assert config.load_config() is None


def test_save_then_load_roundtrip():
    data = {"GROQ_API_KEY": "abc", "MISTRAL_API_KEY": "def"}
    config.save_config(data)

    loaded = config.load_config()
    assert loaded == data


def test_save_config_does_not_write_keys_to_plaintext_file(isolated_config):
    config.save_config({"GROQ_API_KEY": "abc", "MISTRAL_API_KEY": "def"})
    assert config._read_raw() == {}  # keys went to the fake vault, not the JSON file
    assert isolated_config == {"GROQ_API_KEY": "abc", "MISTRAL_API_KEY": "def"}


def test_get_credentials_uses_cache_without_prompting(monkeypatch):
    data = {"GROQ_API_KEY": "abc", "MISTRAL_API_KEY": "def"}
    config.save_config(data)

    def fail_if_called():
        raise AssertionError("should not prompt when cache exists")

    monkeypatch.setattr(config, "prompt_for_credentials", fail_if_called)

    assert config.get_credentials() == data


def test_get_credentials_prompts_and_saves_when_missing(monkeypatch):
    prompted = {"GROQ_API_KEY": "xyz", "MISTRAL_API_KEY": "uvw"}
    monkeypatch.setattr(config, "prompt_for_credentials", lambda: prompted)

    result = config.get_credentials()
    assert result == prompted
    assert config.load_config() == prompted


def test_prompt_for_credentials_raises_eof_when_dialog_cancelled(monkeypatch):
    monkeypatch.setattr("keys_dialog.prompt_for_keys", lambda initial=None: None)
    with pytest.raises(EOFError):
        config.prompt_for_credentials()


def test_logout_removes_keys():
    config.save_config({"GROQ_API_KEY": "abc", "MISTRAL_API_KEY": "def"})
    assert config.logout() is True
    assert config.load_config() is None
    assert config.logout() is False


def test_load_config_migrates_old_aiVoiceDictation_config():
    old_data = {"GROQ_API_KEY": "old-groq", "MISTRAL_API_KEY": "old-mistral"}
    config._OLD_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config._OLD_CONFIG_PATH.write_text('{"GROQ_API_KEY": "old-groq", "MISTRAL_API_KEY": "old-mistral"}', encoding="utf-8")

    assert config.load_config() == old_data


def test_load_config_does_not_overwrite_existing_keys_with_old():
    config.save_config({"GROQ_API_KEY": "new-groq", "MISTRAL_API_KEY": "new-mistral"})
    config._OLD_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config._OLD_CONFIG_PATH.write_text('{"GROQ_API_KEY": "old-groq", "MISTRAL_API_KEY": "old-mistral"}', encoding="utf-8")

    assert config.load_config() == {"GROQ_API_KEY": "new-groq", "MISTRAL_API_KEY": "new-mistral"}


def test_load_config_scrubs_keys_from_old_aiVoiceDictation_file():
    # Security regression: migrating a key into Credential Manager must not
    # leave it sitting in the old plaintext file too — that defeats the
    # entire point of moving off plaintext storage.
    config._OLD_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config._OLD_CONFIG_PATH.write_text(
        '{"GROQ_API_KEY": "old-groq", "MISTRAL_API_KEY": "old-mistral", "HISTORY_DIR": "/keep/me"}',
        encoding="utf-8",
    )

    config.load_config()

    old_data = json.loads(config._OLD_CONFIG_PATH.read_text(encoding="utf-8"))
    assert "GROQ_API_KEY" not in old_data
    assert "MISTRAL_API_KEY" not in old_data
    assert old_data.get("HISTORY_DIR") == "/keep/me"  # non-secret settings still migrated


def test_migrate_plaintext_keys_moves_keys_out_of_this_apps_own_old_file():
    # An earlier version of this app itself stored keys in plaintext config.json.
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_PATH.write_text(
        '{"GROQ_API_KEY": "plain-groq", "MISTRAL_API_KEY": "plain-mistral", "HISTORY_DIR": "/keep/me"}',
        encoding="utf-8",
    )

    data = config.load_config()

    assert data == {"GROQ_API_KEY": "plain-groq", "MISTRAL_API_KEY": "plain-mistral"}
    assert config._read_raw() == {"HISTORY_DIR": "/keep/me"}  # keys stripped, HISTORY_DIR kept


def test_get_history_dir_none_when_unset():
    assert config.get_history_dir() is None


def test_set_history_dir_then_get_returns_it():
    config.set_history_dir(r"D:\Notes\SwarLekh")
    assert config.get_history_dir() == r"D:\Notes\SwarLekh"


def test_set_history_dir_preserves_existing_settings():
    config.set_history_dir("/first")
    config.save_config({"GROQ_API_KEY": "abc", "MISTRAL_API_KEY": "def"})
    config.set_history_dir("/second")

    assert config._read_raw() == {"HISTORY_DIR": "/second"}
    assert config.load_config() == {"GROQ_API_KEY": "abc", "MISTRAL_API_KEY": "def"}


def test_get_hotkey_none_when_unset():
    assert config.get_hotkey() is None


def test_set_hotkey_then_get_returns_it():
    config.set_hotkey(["ctrl", "win"])
    assert config.get_hotkey() == ["ctrl", "win"]


def test_set_hotkey_preserves_existing_settings():
    config.set_history_dir("/notes")
    config.set_hotkey(["alt", "z"])

    assert config._read_raw() == {"HISTORY_DIR": "/notes", "HOTKEY": ["alt", "z"]}
