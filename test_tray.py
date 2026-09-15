import sys
from unittest.mock import MagicMock, patch

import pytest
import requests
from mistralai.client.errors import SDKError
import httpx

import tray


def _make_app():
    with patch("tray.audio.Recorder"), patch("tray.pystray.Icon"), patch("tray.config.get_hotkey", return_value=None):
        return tray.DictationApp()


def test_ensure_credentials_uses_cached_values_without_reloading():
    app = _make_app()
    app._groq_key = "already-have-one"
    app._mistral_client = MagicMock()
    with patch("tray.config.load_config") as mock_load:
        assert app.ensure_credentials() is True
        mock_load.assert_not_called()


@patch("tray.mistral_cleanup.make_client")
@patch("tray.config.load_config")
def test_ensure_credentials_loads_from_disk_when_present(mock_load, mock_make_client):
    mock_load.return_value = {"GROQ_API_KEY": "g", "MISTRAL_API_KEY": "m"}
    app = _make_app()
    assert app.ensure_credentials() is True
    assert app._groq_key == "g"
    mock_make_client.assert_called_once_with("m")


@patch("tray.mistral_cleanup.make_client")
@patch("tray.config.get_credentials")
@patch("tray.config.load_config")
def test_ensure_credentials_prompts_when_missing(mock_load, mock_get_creds, mock_make_client):
    mock_load.return_value = None
    mock_get_creds.return_value = {"GROQ_API_KEY": "g2", "MISTRAL_API_KEY": "m2"}
    app = _make_app()
    assert app.ensure_credentials() is True
    mock_get_creds.assert_called_once()
    assert app._groq_key == "g2"


@patch("tray.config.get_credentials", side_effect=EOFError)
@patch("tray.config.load_config", return_value=None)
def test_ensure_credentials_returns_false_if_prompt_fails(mock_load, mock_get_creds):
    app = _make_app()
    assert app.ensure_credentials() is False


def test_is_auth_error_detects_requests_401():
    resp = MagicMock(status_code=401)
    exc = requests.exceptions.HTTPError(response=resp)
    assert tray._is_auth_error(exc) is True


def test_is_auth_error_detects_mistral_403():
    response = httpx.Response(403, headers={}, text="{}")
    exc = SDKError("forbidden", response)
    assert tray._is_auth_error(exc) is True


def test_is_auth_error_false_for_other_errors():
    assert tray._is_auth_error(ValueError("unrelated")) is False


def test_process_clears_credentials_on_auth_error():
    app = _make_app()
    app._groq_key = "bad-key"
    app._mistral_client = MagicMock()
    resp = MagicMock(status_code=401)
    with patch("tray.groq_client.transcribe", side_effect=requests.exceptions.HTTPError(response=resp)):
        with patch("tray.config.logout") as mock_logout:
            app._process(b"fake-wav")
    mock_logout.assert_called_once()
    assert app._groq_key is None
    assert app._mistral_client is None


def test_on_press_does_not_block_when_credentials_missing():
    # Regression: ensure_credentials() must never be called synchronously from
    # _on_press — it runs on pynput's keyboard-hook thread, and a blocking
    # getpass() prompt there would stall system-wide key delivery.
    app = _make_app()
    app._listener = MagicMock()
    app._listener.canonical.side_effect = lambda k: k
    with patch("tray.threading.Thread") as mock_thread:
        for key in app._hotkey_combo:
            app._on_press(key)
    assert app._combo_engaged is False
    mock_thread.assert_called_once()
    _, kwargs = mock_thread.call_args
    assert kwargs["target"] == app._resolve_credentials_async


def test_on_press_engages_immediately_when_credentials_already_cached():
    app = _make_app()
    app._groq_key = "g"
    app._mistral_client = MagicMock()
    app._listener = MagicMock()
    app._listener.canonical.side_effect = lambda k: k
    with patch("tray.threading.Thread") as mock_thread:
        for key in app._hotkey_combo:
            app._on_press(key)
    assert app._combo_engaged is True
    mock_thread.assert_not_called()


def test_resolve_credentials_async_clears_flag_after_running():
    app = _make_app()
    app._resolving_credentials = True
    with patch.object(app, "ensure_credentials", return_value=True) as mock_ensure:
        app._resolve_credentials_async()
    mock_ensure.assert_called_once()
    assert app._resolving_credentials is False


def test_main_exits_if_startup_failed():
    # The credential check now happens inside run() (on the icon thread,
    # after the GUI root's mainloop is running — see DictationApp._run_icon),
    # not in main() directly, so a failed startup surfaces as _startup_failed
    # being set by the time run() returns.
    with patch("tray.gui_root.init_root"):
        with patch("tray.DictationApp") as mock_app_cls:
            mock_app = MagicMock()
            mock_app._startup_failed = True
            mock_app_cls.return_value = mock_app
            with pytest.raises(SystemExit):
                tray.main()
    mock_app.run.assert_called_once()


def test_icon_click_starts_then_stops_recording_like_a_tap():
    app = _make_app()
    app._groq_key = "g"
    app._mistral_client = MagicMock()
    with patch.object(app, "_recorder") as mock_recorder:
        mock_recorder.stop.return_value = b"fake-wav"
        with patch("tray.threading.Thread") as mock_thread:
            app._on_icon_click(app._icon, None)  # first click: start recording
            mock_recorder.start.assert_called_once()
            mock_recorder.stop.assert_not_called()

            app._on_icon_click(app._icon, None)  # second click: stop recording
            mock_recorder.stop.assert_called_once()
        mock_thread.assert_called_once()  # spawns _process in the background


def test_icon_click_does_not_block_when_credentials_missing():
    app = _make_app()
    with patch("tray.threading.Thread") as mock_thread:
        app._on_icon_click(app._icon, None)
    assert app._hotkey_sm.state == "idle"
    mock_thread.assert_called_once()
    _, kwargs = mock_thread.call_args
    assert kwargs["target"] == app._resolve_credentials_async


def _patch_gui_thread():
    """Bypass the real Tk mainloop/threading for tests: run the marshalled
    function synchronously and hand back a fake root."""
    return (
        patch("tray.gui_root.run_on_gui_thread", side_effect=lambda fn: fn()),
        patch("tray.gui_root.get_root", return_value=MagicMock()),
    )


def test_change_history_dir_saves_chosen_folder():
    app = _make_app()
    p1, p2 = _patch_gui_thread()
    with p1, p2, patch("tkinter.filedialog.askdirectory", return_value="/chosen/path"):
        with patch("tray.config.set_history_dir") as mock_set:
            app._change_history_dir(app._icon, None)
    mock_set.assert_called_once_with("/chosen/path")


def test_change_history_dir_does_nothing_if_dialog_cancelled():
    app = _make_app()
    p1, p2 = _patch_gui_thread()
    with p1, p2, patch("tkinter.filedialog.askdirectory", return_value=""):
        with patch("tray.config.set_history_dir") as mock_set:
            app._change_history_dir(app._icon, None)
    mock_set.assert_not_called()


@patch("keys_dialog.prompt_for_keys", return_value={"GROQ_API_KEY": "new-g", "MISTRAL_API_KEY": "new-m"})
def test_edit_api_keys_saves_and_updates_live_client(mock_prompt):
    app = _make_app()
    with patch("tray.config.save_config") as mock_save:
        with patch("tray.mistral_cleanup.make_client", return_value="client-obj") as mock_make_client:
            app._edit_api_keys(app._icon, None)
    mock_save.assert_called_once_with({"GROQ_API_KEY": "new-g", "MISTRAL_API_KEY": "new-m"})
    mock_make_client.assert_called_once_with("new-m")
    assert app._groq_key == "new-g"
    assert app._mistral_client == "client-obj"


@patch("keys_dialog.prompt_for_keys", return_value=None)
def test_edit_api_keys_does_nothing_if_dialog_cancelled(mock_prompt):
    app = _make_app()
    with patch("tray.config.save_config") as mock_save:
        app._edit_api_keys(app._icon, None)
    mock_save.assert_not_called()
    assert app._groq_key is None


def test_ensure_output_streams_noop_when_console_present():
    real_stdout, real_stderr = sys.stdout, sys.stderr
    tray._ensure_output_streams()
    assert sys.stdout is real_stdout
    assert sys.stderr is real_stderr


def test_ensure_output_streams_redirects_to_log_file_when_none(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(tray.config, "CONFIG_DIR", tmp_path)
    try:
        tray._ensure_output_streams()
        assert sys.stdout is not None
        print("hello")  # must not raise
    finally:
        sys.stdout.close()
    assert (tmp_path / "swarlekh.log").read_text(encoding="utf-8").strip() == "hello"


def test_process_skips_pipeline_on_empty_transcript():
    app = _make_app()
    app._groq_key = "k"
    app._mistral_client = MagicMock()
    with patch("tray.groq_client.transcribe", return_value="   "):
        with patch("tray.mistral_cleanup.clean") as mock_clean:
            with patch("tray.paste.paste_text") as mock_paste:
                with patch("tray.history.record_dictation") as mock_record:
                    app._process(b"fake-wav")
    mock_clean.assert_not_called()
    mock_paste.assert_not_called()
    mock_record.assert_not_called()


def test_change_hotkey_updates_combo_and_persists(monkeypatch):
    import hotkey_combo

    app = _make_app()
    assert app._hotkey_combo == hotkey_combo.strs_to_combo(hotkey_combo.DEFAULT_COMBO)
    with patch("hotkey_dialog.prompt_for_hotkey", return_value=["alt", "z"]) as mock_prompt:
        with patch("tray.config.set_hotkey") as mock_set:
            app._change_hotkey(app._icon, None)
    mock_prompt.assert_called_once()
    mock_set.assert_called_once_with(["alt", "z"])
    assert app._hotkey_combo == hotkey_combo.strs_to_combo(["alt", "z"])


def test_change_hotkey_does_nothing_on_cancel():
    import hotkey_combo

    app = _make_app()
    original = app._hotkey_combo
    with patch("hotkey_dialog.prompt_for_hotkey", return_value=None):
        with patch("tray.config.set_hotkey") as mock_set:
            app._change_hotkey(app._icon, None)
    mock_set.assert_not_called()
    assert app._hotkey_combo == original


def test_dialog_reentrancy_guard_blocks_stacked_dialogs():
    # Regression: pystray's message pump can re-enter a menu-item callback
    # while a previous one's nested tkinter mainloop is still running (both
    # pump the same Windows message queue) — without the guard, rapid
    # re-clicks stack multiple dialogs that each need dismissing separately.
    app = _make_app()

    def fake_prompt(*args, **kwargs):
        # Simulate a re-click arriving while this dialog's mainloop is still
        # "running" — the nested call must be a no-op, not a second dialog.
        app._change_hotkey(app._icon, None)
        return None

    with patch("hotkey_dialog.prompt_for_hotkey", side_effect=fake_prompt) as mock_prompt:
        app._change_hotkey(app._icon, None)
    mock_prompt.assert_called_once()
    assert app._dialog_open is False


def test_dialog_reentrancy_guard_blocks_stacked_key_dialogs():
    app = _make_app()

    def fake_prompt(*args, **kwargs):
        app._edit_api_keys(app._icon, None)  # simulated re-click mid-dialog
        return None

    with patch("keys_dialog.prompt_for_keys", side_effect=fake_prompt) as mock_prompt:
        app._edit_api_keys(app._icon, None)
    mock_prompt.assert_called_once()
    assert app._dialog_open is False


def test_dialog_reentrancy_guard_blocks_stacked_folder_dialogs():
    app = _make_app()
    call_count = {"n": 0}

    def fake_askdirectory(*args, **kwargs):
        call_count["n"] += 1
        app._change_history_dir(app._icon, None)  # simulated re-click mid-dialog
        return ""

    p1, p2 = _patch_gui_thread()
    with p1, p2, patch("tkinter.filedialog.askdirectory", side_effect=fake_askdirectory):
        app._change_history_dir(app._icon, None)
    assert call_count["n"] == 1  # the nested re-click never reached askdirectory
    assert app._dialog_open is False


def test_dialog_open_guard_cleared_even_if_dialog_raises():
    app = _make_app()
    with patch("keys_dialog.prompt_for_keys", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            app._edit_api_keys(app._icon, None)
    assert app._dialog_open is False
