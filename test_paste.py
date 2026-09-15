from unittest.mock import MagicMock, call, patch

import paste


def test_paste_text_copies_then_restores_previous_clipboard():
    with patch("paste.pyperclip") as mock_pyperclip, patch("paste.time.sleep"):
        mock_pyperclip.paste.return_value = "previous clipboard contents"
        controller = MagicMock()

        paste.paste_text("dictated secret", controller=controller)

        mock_pyperclip.copy.assert_has_calls([call("dictated secret"), call("previous clipboard contents")])
        assert mock_pyperclip.copy.call_args_list[-1] == call("previous clipboard contents")


def test_paste_text_sends_ctrl_v():
    with patch("paste.pyperclip"), patch("paste.time.sleep"):
        controller = MagicMock()

        paste.paste_text("some text", controller=controller)

        controller.press.assert_called_once_with("v")
        controller.release.assert_called_once_with("v")


def test_paste_text_restores_even_if_clipboard_was_empty():
    with patch("paste.pyperclip") as mock_pyperclip, patch("paste.time.sleep"):
        mock_pyperclip.paste.return_value = ""
        controller = MagicMock()

        paste.paste_text("dictated text", controller=controller)

        assert mock_pyperclip.copy.call_args_list[-1] == call("")
