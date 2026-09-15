"""Microphone capture — start/stop recording of arbitrary duration to WAV bytes."""

import io
import wave

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"


def _to_wav_bytes(audio: np.ndarray, sample_rate: int, channels: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return buffer.getvalue()


class Recorder:
    """Records mic audio from start() until stop(), of whatever length that spans."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS, dtype: str = DTYPE):
        self._sample_rate = sample_rate
        self._channels = channels
        self._dtype = dtype
        self._frames: list[np.ndarray] = []
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        self._frames.append(indata.copy())

    def start(self) -> None:
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype=self._dtype,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> bytes:
        """Stop recording and return the captured audio as WAV bytes."""
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if self._frames:
            audio = np.concatenate(self._frames, axis=0)
        else:
            audio = np.zeros((0, self._channels), dtype=self._dtype)
        return _to_wav_bytes(audio, self._sample_rate, self._channels)
