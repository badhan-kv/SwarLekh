from unittest.mock import MagicMock

import pytest

import retry


class _FakeHTTPError(Exception):
    def __init__(self, status_code, retry_after=None):
        super().__init__(f"status {status_code}")
        self.status_code = status_code
        self.retry_after = retry_after


def _get_status(exc):
    return getattr(exc, "status_code", None)


def _get_retry_after(exc):
    return getattr(exc, "retry_after", None)


def test_returns_result_on_first_success():
    call = MagicMock(return_value="ok")
    assert retry.with_retries(call, get_status=_get_status) == "ok"
    call.assert_called_once()


def test_retries_on_retryable_status_then_succeeds(monkeypatch):
    monkeypatch.setattr(retry.time, "sleep", MagicMock())
    call = MagicMock(side_effect=[_FakeHTTPError(503), "ok"])
    result = retry.with_retries(call, get_status=_get_status)
    assert result == "ok"
    assert call.call_count == 2


def test_raises_immediately_on_non_retryable_status():
    call = MagicMock(side_effect=_FakeHTTPError(400))
    with pytest.raises(_FakeHTTPError):
        retry.with_retries(call, get_status=_get_status)
    call.assert_called_once()


def test_raises_after_max_retries_exhausted(monkeypatch):
    monkeypatch.setattr(retry.time, "sleep", MagicMock())
    call = MagicMock(side_effect=_FakeHTTPError(429))
    with pytest.raises(_FakeHTTPError):
        retry.with_retries(call, get_status=_get_status, max_retries=2)
    assert call.call_count == 3


def test_honors_retry_after_header(monkeypatch):
    sleep_mock = MagicMock()
    monkeypatch.setattr(retry.time, "sleep", sleep_mock)
    call = MagicMock(side_effect=[_FakeHTTPError(429, retry_after=5.0), "ok"])
    retry.with_retries(call, get_status=_get_status, get_retry_after=_get_retry_after)
    sleep_mock.assert_called_once_with(5.0)


def test_retry_after_header_is_capped_at_max_backoff(monkeypatch):
    sleep_mock = MagicMock()
    monkeypatch.setattr(retry.time, "sleep", sleep_mock)
    call = MagicMock(side_effect=[_FakeHTTPError(429, retry_after=99999.0), "ok"])
    retry.with_retries(call, get_status=_get_status, get_retry_after=_get_retry_after)
    sleep_mock.assert_called_once_with(retry.MAX_BACKOFF_SECONDS)


def test_on_retry_callback_invoked_before_sleep(monkeypatch):
    monkeypatch.setattr(retry.time, "sleep", MagicMock())
    on_retry = MagicMock()
    call = MagicMock(side_effect=[_FakeHTTPError(500), "ok"])
    retry.with_retries(call, get_status=_get_status, on_retry=on_retry)
    on_retry.assert_called_once()
    args = on_retry.call_args[0]
    assert args[0] == 1  # attempt number
