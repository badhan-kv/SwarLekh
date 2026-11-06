import wave
import io

import numpy as np

from unittest.mock import MagicMock, patch

import pytest
import sounddevice as sd

import audio
from audio import _to_wav_bytes


def test_to_wav_bytes_round_trips_samples():
    samples = np.array([[0], [100], [-100], [32000]], dtype="int16")
    wav_bytes = _to_wav_bytes(samples, sample_rate=16000, channels=1)

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        frames = wf.readframes(wf.getnframes())
        decoded = np.frombuffer(frames, dtype="int16")
        assert list(decoded) == [0, 100, -100, 32000]


def test_to_wav_bytes_handles_empty_audio():
    samples = np.zeros((0, 1), dtype="int16")
    wav_bytes = _to_wav_bytes(samples, sample_rate=16000, channels=1)
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnframes() == 0


def test_start_retries_transient_device_unavailable_then_succeeds():
    good = MagicMock()
    with patch("audio.sd.InputStream", side_effect=[sd.PortAudioError("Device unavailable"), good]) as ctor,             patch("audio.time.sleep"):
        rec = audio.Recorder()
        rec.start()
    assert ctor.call_count == 2
    good.start.assert_called_once()


def test_start_raises_after_all_attempts_fail():
    with patch("audio.sd.InputStream", side_effect=sd.PortAudioError("Device unavailable")) as ctor,             patch("audio.time.sleep"):
        rec = audio.Recorder()
        with pytest.raises(sd.PortAudioError):
            rec.start(attempts=3)
    assert ctor.call_count == 3


def test_stop_after_failed_start_returns_empty_audio_instead_of_crashing():
    with patch("audio.sd.InputStream", side_effect=sd.PortAudioError("x")), patch("audio.time.sleep"):
        rec = audio.Recorder()
        with pytest.raises(sd.PortAudioError):
            rec.start()
    wav = rec.stop()
    assert wav[:4] == b"RIFF"
