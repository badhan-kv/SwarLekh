"""Generic retry-with-backoff helper shared by groq_client.py and mistral_cleanup.py."""

import random
import time

DEFAULT_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 4
MAX_BACKOFF_SECONDS = 30


def get_status(exc: Exception) -> int | None:
    """Extract an HTTP status code from an exception, trying the two shapes
    used across this codebase: a direct `.status_code` (Mistral SDK errors)
    or a nested `.response.status_code` (requests' HTTPError)."""
    status = getattr(exc, "status_code", None)
    if status is not None:
        return status
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) if response is not None else None


def with_retries(
    call,
    *,
    get_status,
    get_retry_after=None,
    retryable_status=DEFAULT_RETRYABLE_STATUS,
    max_retries=MAX_RETRIES,
    on_retry=None,
):
    """Run `call()`, retrying transient HTTP errors with exponential backoff.

    `get_status(exc) -> int | None` extracts an HTTP status code from a caught
    exception; a status not in `retryable_status` (or None) re-raises immediately.
    `get_retry_after(exc) -> float | None` may honor a Retry-After header.
    `on_retry(attempt, delay, exc)` is invoked before each sleep so callers can
    surface a "rate limited, retrying" notice.
    """
    for attempt in range(max_retries + 1):
        try:
            return call()
        except Exception as exc:
            status = get_status(exc)
            if status not in retryable_status or attempt == max_retries:
                raise
            delay = get_retry_after(exc) if get_retry_after else None
            if delay is None:
                delay = min(2**attempt, MAX_BACKOFF_SECONDS) + random.uniform(0, 0.5)
            else:
                # Cap a server-supplied Retry-After too — an unexpectedly huge
                # value (malformed or malicious) shouldn't hang the app.
                delay = min(delay, MAX_BACKOFF_SECONDS)
            if on_retry is not None:
                on_retry(attempt + 1, delay, exc)
            time.sleep(delay)
