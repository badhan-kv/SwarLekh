from unittest.mock import MagicMock, patch

import requests

import groq_client


def _fake_response(status_code=200, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        error = requests.exceptions.HTTPError(response=resp)
        resp.raise_for_status.side_effect = error
    else:
        resp.raise_for_status.return_value = None
    return resp


@patch("groq_client.requests.post")
def test_transcribe_returns_text_on_success(mock_post):
    mock_post.return_value = _fake_response(200, {"text": "hello world"})
    result = groq_client.transcribe(b"fake-wav-bytes", api_key="key123")
    assert result == "hello world"
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer key123"
    assert kwargs["data"]["model"] == groq_client.DEFAULT_MODEL


@patch("retry.time.sleep")
@patch("groq_client.requests.post")
def test_transcribe_retries_on_503_then_succeeds(mock_post, mock_sleep):
    mock_post.side_effect = [
        _fake_response(503),
        _fake_response(200, {"text": "recovered"}),
    ]
    result = groq_client.transcribe(b"fake-wav-bytes", api_key="key123")
    assert result == "recovered"
    assert mock_post.call_count == 2


@patch("retry.time.sleep")
@patch("groq_client.requests.post")
def test_transcribe_raises_on_non_retryable_status(mock_post, mock_sleep):
    mock_post.return_value = _fake_response(400)
    try:
        groq_client.transcribe(b"fake-wav-bytes", api_key="key123")
        assert False, "expected HTTPError"
    except requests.exceptions.HTTPError:
        pass
    mock_post.assert_called_once()
