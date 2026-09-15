import wave
import io

import numpy as np

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
