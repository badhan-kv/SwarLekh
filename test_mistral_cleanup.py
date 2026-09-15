from unittest.mock import MagicMock, patch

import httpx
import pytest
from mistralai.client.errors import SDKError

import command_router as cr
import mistral_cleanup


def _rate_limit_error(retry_after: str | None = None, limit_req_minute: str = "60") -> SDKError:
    headers = {"x-ratelimit-limit-req-minute": limit_req_minute}
    if retry_after is not None:
        headers["retry-after"] = retry_after
    response = httpx.Response(429, headers=headers, text='{"code":"1300"}')
    return SDKError("API error occurred", response)


def _response(reply_text: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=reply_text))]
    return response


def _fake_client(reply_text: str) -> MagicMock:
    client = MagicMock()
    client.chat.complete.return_value = _response(reply_text)
    return client


def test_clean_returns_reply_text():
    client = _fake_client("some text, cleaned.")
    result = mistral_cleanup.clean(client, cr.MODE_TRANSCRIBE, "uh, some text")
    assert result == "some text, cleaned."


def test_clean_uses_transcribe_prompt_for_transcribe_mode():
    client = _fake_client("hello there")
    mistral_cleanup.clean(client, cr.MODE_TRANSCRIBE, "hello")
    _, kwargs = client.chat.complete.call_args
    assert kwargs["messages"][0]["content"] == mistral_cleanup.TRANSCRIBE_PROMPT
    assert kwargs["messages"][1]["content"] == "hello"
    assert kwargs["model"] == mistral_cleanup.DEFAULT_MODEL


def test_clean_uses_notes_prompt_for_notes_mode():
    client = _fake_client("hello there")
    mistral_cleanup.clean(client, cr.MODE_NOTES, "hello")
    _, kwargs = client.chat.complete.call_args
    assert kwargs["messages"][0]["content"] == mistral_cleanup.NOTES_PROMPT


def test_clean_fails_fast_on_zero_allowance():
    client = MagicMock()
    client.chat.complete.side_effect = _rate_limit_error(limit_req_minute="0")
    with pytest.raises(RuntimeError, match="0 requests/minute"):
        mistral_cleanup.clean(client, cr.MODE_TRANSCRIBE, "hello")
    client.chat.complete.assert_called_once()


@patch("retry.time.sleep")
def test_clean_retries_then_succeeds(mock_sleep):
    client = MagicMock()
    client.chat.complete.side_effect = [_rate_limit_error(retry_after="1"), _response("hello recovered")]

    result = mistral_cleanup.clean(client, cr.MODE_TRANSCRIBE, "hello")

    assert result == "hello recovered"
    assert client.chat.complete.call_count == 2


def test_has_unclear_segment_true_when_marker_present():
    assert mistral_cleanup.has_unclear_segment("Some text [UNCLEAR] more text") is True


def test_has_unclear_segment_false_when_absent():
    assert mistral_cleanup.has_unclear_segment("Perfectly clean text.") is False


def test_clean_retries_when_output_drops_a_word():
    client = MagicMock()
    client.chat.complete.side_effect = [
        _response("I think we should rewrite that module."),  # missing "Honestly"
        _response("Honestly, I think we should rewrite that module."),
    ]
    result = mistral_cleanup.clean(client, cr.MODE_TRANSCRIBE, "Honestly, I think we should rewrite that module.")
    assert result == "Honestly, I think we should rewrite that module."
    assert client.chat.complete.call_count == 2
    # the retry's follow-up message names the dropped word
    _, kwargs = client.chat.complete.call_args
    assert "honestly" in kwargs["messages"][-1]["content"].lower()


def test_clean_stops_retrying_after_max_attempts_and_returns_last(capsys):
    client = MagicMock()
    client.chat.complete.return_value = _response("still missing it")
    result = mistral_cleanup.clean(client, cr.MODE_TRANSCRIBE, "Honestly, keep it.", max_verify_retries=2)
    assert result == "still missing it"
    assert client.chat.complete.call_count == 3  # 1 initial + 2 verify-retries
    assert "honestly" in capsys.readouterr().out.lower()


def test_clean_no_retry_when_output_already_preserves_everything():
    client = _fake_client("Honestly, keep it exactly.")
    mistral_cleanup.clean(client, cr.MODE_TRANSCRIBE, "Honestly, keep it exactly.")
    client.chat.complete.assert_called_once()
