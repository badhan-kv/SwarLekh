"""Groq Whisper transcription calls."""

import requests

from retry import get_status, with_retries

DEFAULT_MODEL = "whisper-large-v3-turbo"
DEFAULT_TIMEOUT_SECONDS = 30
TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def _get_retry_after(exc):
    response = getattr(exc, "response", None)
    if response is None:
        return None
    try:
        return float(response.headers.get("retry-after"))
    except (AttributeError, TypeError, ValueError):
        return None


def transcribe(
    audio_wav_bytes: bytes,
    api_key: str,
    model: str = DEFAULT_MODEL,
    on_retry=None,
) -> str:
    """Send a WAV clip to Groq's Whisper endpoint, return the transcript text."""

    def call():
        response = requests.post(
            TRANSCRIPTIONS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("clip.wav", audio_wav_bytes, "audio/wav")},
            data={"model": model},
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["text"]

    return with_retries(call, get_status=get_status, get_retry_after=_get_retry_after, on_retry=on_retry)
