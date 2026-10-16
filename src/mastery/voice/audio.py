"""Audio basics without extra dependencies: WAV in and out, mono, resampling, chunking (Lesson 13.02).

Only the standard library ``wave`` module and numpy. Production pipelines use ffmpeg (any format in,
16 kHz mono FLAC out) or a proper resampler such as soxr; this module is enough to learn the ideas and
to prepare WAV files for speech-to-text, which is all the course needs.
"""
from __future__ import annotations

import io
import math
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

__all__ = [
    "AudioClip",
    "chunk",
    "concat",
    "read_wav",
    "silence",
    "tone",
    "wav_size_bytes",
    "with_noise",
]


@dataclass(frozen=True)
class AudioClip:
    """Mono float32 samples in [-1, 1] at ``rate`` Hz."""

    samples: np.ndarray
    rate: int

    @property
    def seconds(self) -> float:
        return len(self.samples) / self.rate

    def resample(self, rate: int) -> "AudioClip":
        """Linear-interpolation resampling with a simple anti-alias average when downsampling.

        Good enough for speech-to-text (Whisper works at 16 kHz internally); not for music.
        """
        if rate == self.rate:
            return self
        x = self.samples
        if rate < self.rate:
            k = max(1, int(round(self.rate / rate)))
            if k > 1:
                x = np.convolve(x, np.ones(k, dtype=np.float32) / k, mode="same")
        n = int(round(len(x) * rate / self.rate))
        t_old = np.arange(len(x)) / self.rate
        t_new = np.arange(n) / rate
        return AudioClip(np.interp(t_new, t_old, x).astype(np.float32), rate)

    def slice(self, start_s: float, end_s: float) -> "AudioClip":
        a, b = int(start_s * self.rate), int(end_s * self.rate)
        return AudioClip(self.samples[max(a, 0):max(b, 0)], self.rate)

    def rms_db(self) -> float:
        """Loudness in dBFS (0 = full scale; speech is typically -30 to -15, silence below -50)."""
        rms = float(np.sqrt(np.mean(np.square(self.samples)))) if len(self.samples) else 0.0
        return 20 * math.log10(rms) if rms > 0 else -120.0

    def to_wav(self, rate: int | None = None) -> bytes:
        """16-bit PCM mono WAV bytes, optionally resampled first."""
        clip = self.resample(rate) if rate else self
        pcm = (np.clip(clip.samples, -1, 1) * 32767).astype("<i2").tobytes()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(clip.rate)
            w.writeframes(pcm)
        return buf.getvalue()


def read_wav(source: str | Path | bytes) -> AudioClip:
    """Read a PCM WAV (8/16/32-bit, any channels) and mix it down to mono float32."""
    with wave.open(io.BytesIO(source) if isinstance(source, bytes) else str(source), "rb") as w:
        channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(frames)
    if width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128
    elif width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648
    else:
        raise ValueError(f"unsupported sample width {width} bytes (convert with ffmpeg first)")
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return AudioClip(data.astype(np.float32), rate)


def wav_size_bytes(seconds: float, rate: int = 16_000, channels: int = 1, bits: int = 16) -> int:
    """Size of an uncompressed PCM WAV (44-byte header + samples)."""
    return 44 + int(seconds * rate) * channels * bits // 8


def tone(freq: float = 440.0, seconds: float = 1.0, rate: int = 16_000, amplitude: float = 0.3) -> AudioClip:
    t = np.arange(int(seconds * rate)) / rate
    return AudioClip((amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32), rate)


def silence(seconds: float, rate: int = 16_000) -> AudioClip:
    return AudioClip(np.zeros(int(seconds * rate), dtype=np.float32), rate)


def with_noise(clip: AudioClip, snr_db: float, seed: int = 0) -> AudioClip:
    """Add white noise at a signal-to-noise ratio (pure noise if the clip is silent)."""
    rng = np.random.default_rng(seed)
    power = float(np.mean(np.square(clip.samples))) or 1e-4
    noise = rng.normal(0, math.sqrt(power / 10 ** (snr_db / 10)), len(clip.samples)).astype(np.float32)
    return AudioClip(np.clip(clip.samples + noise, -1, 1).astype(np.float32), clip.rate)


def concat(*clips: AudioClip) -> AudioClip:
    rates = {c.rate for c in clips}
    if len(rates) != 1:
        raise ValueError(f"resample first: clips have rates {sorted(rates)}")
    return AudioClip(np.concatenate([c.samples for c in clips]).astype(np.float32), rates.pop())


def chunk(clip: AudioClip, max_seconds: float, overlap_seconds: float = 1.0) -> list[tuple[float, AudioClip]]:
    """Split into windows of at most ``max_seconds`` that overlap by ``overlap_seconds``.

    Returns ``(start_seconds, clip)`` pairs; the start is what you add to each chunk's timestamps.
    The overlap keeps a word cut at a boundary whole in at least one chunk.
    """
    if max_seconds <= overlap_seconds:
        raise ValueError("max_seconds must be larger than overlap_seconds")
    out, start, step = [], 0.0, max_seconds - overlap_seconds
    while start < clip.seconds:
        out.append((round(start, 3), clip.slice(start, min(start + max_seconds, clip.seconds))))
        if start + max_seconds >= clip.seconds:
            break
        start += step
    return out
