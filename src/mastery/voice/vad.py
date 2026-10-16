"""Turn-taking building blocks for real-time voice (Lesson 13.05).

Offline and dependency-free (numpy only):

* ``frame_energy`` / ``EnergyVad``: is this 20 ms frame speech? (loudness against an adaptive noise floor)
* ``Endpointer``: has the caller *finished* their turn? (speech, then ``silence_ms`` of silence)
* ``PartialTranscripts``: what a streaming STT shows while the caller is still talking
* ``Playback``: agent audio that a caller can interrupt (barge-in) and that is cancelled cleanly
* ``LatencyBudget``: targets per stage against measured times

Production systems use a trained VAD (Silero, WebRTC VAD) or the provider's server-side
endpointing; the energy VAD here is for understanding the knobs, not for noisy phone lines.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

import numpy as np

from .audio import AudioClip

__all__ = [
    "EnergyVad",
    "Endpointer",
    "TurnEvent",
    "LatencyBudget",
    "PartialTranscripts",
    "Playback",
    "frame_energy",
    "frames",
    "speech_clip",
]


def frames(clip: AudioClip, frame_ms: int = 20) -> Iterator[np.ndarray]:
    """Yield consecutive frames of ``frame_ms`` (the last partial frame is dropped)."""
    n = int(clip.rate * frame_ms / 1000)
    for start in range(0, len(clip.samples) - n + 1, n):
        yield clip.samples[start:start + n]


def frame_energy(frame: np.ndarray) -> float:
    """Frame loudness in dBFS (-120 for digital silence)."""
    rms = float(np.sqrt(np.mean(np.square(frame)))) if len(frame) else 0.0
    return 20 * float(np.log10(rms)) if rms > 0 else -120.0


@dataclass
class EnergyVad:
    """Speech if a frame is ``margin_db`` above the noise floor (and above ``min_db``).

    The first ``calibrate_frames`` frames (200 ms) are assumed to be background and set the floor;
    after that the floor follows non-speech frames, so steady line noise is ignored.
    """

    margin_db: float = 12.0
    min_db: float = -45.0
    floor_db: float = -60.0
    adapt: float = 0.05
    calibrate_frames: int = 10
    _seen: int = 0

    def is_speech(self, frame: np.ndarray) -> bool:
        db = frame_energy(frame)
        if self._seen < self.calibrate_frames:
            self._seen += 1
            self.floor_db = db if self._seen == 1 else self.floor_db + (db - self.floor_db) / self._seen
            return False
        speech = db > max(self.floor_db + self.margin_db, self.min_db)
        if not speech:  # learn the floor only from non-speech frames
            self.floor_db += self.adapt * (db - self.floor_db)
        return speech


@dataclass(frozen=True)
class TurnEvent:
    kind: str  # "speech_start" | "end_of_turn"
    at_s: float


@dataclass
class Endpointer:
    """Turns per-frame VAD decisions into turn events.

    * ``min_speech_ms``: ignore blips shorter than this (a cough, a click)
    * ``silence_ms``: silence after speech that ends the turn. Short = snappy but cuts callers
      who pause to think; long = polite but slow. Every ms here is added to response latency.
    """

    vad: EnergyVad = field(default_factory=EnergyVad)
    frame_ms: int = 20
    min_speech_ms: int = 100
    silence_ms: int = 600

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.vad._seen = 0
        self._t = 0.0
        self._speech_run = 0
        self._silence_run = 0
        self.in_speech = False

    def feed(self, frame: np.ndarray) -> TurnEvent | None:
        self._t += self.frame_ms / 1000
        if self.vad.is_speech(frame):
            self._speech_run += self.frame_ms
            self._silence_run = 0
            if not self.in_speech and self._speech_run >= self.min_speech_ms:
                self.in_speech = True
                return TurnEvent("speech_start", round(self._t - self._speech_run / 1000, 3))
        else:
            self._speech_run = 0
            if self.in_speech:
                self._silence_run += self.frame_ms
                if self._silence_run >= self.silence_ms:
                    self.in_speech = False
                    self._silence_run = 0
                    return TurnEvent("end_of_turn", round(self._t, 3))
        return None

    def run(self, clip: AudioClip) -> list[TurnEvent]:
        """All events for a whole clip (the streaming loop, replayed offline)."""
        self.reset()
        events = []
        for frame in frames(clip, self.frame_ms):
            event = self.feed(frame)
            if event:
                events.append(event)
        return events


@dataclass
class PartialTranscripts:
    """Simulates streaming STT: growing *partial* hypotheses, then one *final* at end of turn.

    ``words_per_s`` is speaking rate; partials may revise the last word (``revise``), which is why
    an agent must act only on the final transcript.
    """

    text: str
    words_per_s: float = 2.5
    revise: dict[str, str] = field(default_factory=dict)

    def stream(self, step_s: float = 0.5) -> Iterator[tuple[float, str, bool]]:
        words = self.text.split()
        t, shown = 0.0, 0
        while shown < len(words):
            t += step_s
            shown = min(len(words), int(t * self.words_per_s))
            if not shown:
                continue
            partial = words[:shown]
            last = partial[-1]
            if shown < len(words) and last in self.revise:
                partial = partial[:-1] + [self.revise[last]]
            yield round(t, 2), " ".join(partial), False
        yield round(t, 2), self.text, True


@dataclass
class Playback:
    """Agent audio played in chunks; ``barge_in`` stops it and records what the caller heard."""

    chunks: list[str]
    seconds_per_chunk: float = 1.0
    played: list[str] = field(default_factory=list)
    cancelled_at_s: float | None = None

    def play(self, interrupt_at_s: float | None = None) -> list[str]:
        """Play until the end or until the caller starts talking at ``interrupt_at_s``."""
        t = 0.0
        for c in self.chunks:
            if interrupt_at_s is not None and t >= interrupt_at_s:
                self.cancelled_at_s = round(t, 3)
                break
            self.played.append(c)
            t += self.seconds_per_chunk
        return self.played

    @property
    def unheard(self) -> list[str]:
        return self.chunks[len(self.played):]


@dataclass
class LatencyBudget:
    """Target ms per stage; ``report(measured)`` shows over/under and the end-to-end total."""

    targets: dict[str, int]

    def report(self, measured: dict[str, float]) -> list[dict[str, object]]:
        rows = []
        for stage, target in self.targets.items():
            got = measured.get(stage)
            rows.append({"stage": stage, "target ms": target,
                         "measured ms": None if got is None else round(got),
                         "ok": None if got is None else got <= target})
        total_t = sum(self.targets.values())
        total_m = sum(v for k, v in measured.items() if k in self.targets)
        rows.append({"stage": "TOTAL", "target ms": total_t, "measured ms": round(total_m), "ok": total_m <= total_t})
        return rows


def speech_clip(segments: Iterable[tuple[str, float]], rate: int = 16_000, noise_db: float = -60.0,
                seed: int = 0) -> AudioClip:
    """Synthetic 'speech' (modulated tones) and silences: [("speech", 1.2), ("silence", 0.3), ...]."""
    rng = np.random.default_rng(seed)
    parts = []
    for kind, seconds in segments:
        n = int(rate * seconds)
        t = np.arange(n) / rate
        if kind == "speech":
            env = 0.5 + 0.5 * np.sin(2 * np.pi * 4 * t)  # ~4 syllables per second
            x = 0.25 * env * np.sin(2 * np.pi * 180 * t)
        else:
            x = np.zeros(n)
        parts.append(x)
    x = np.concatenate(parts) if parts else np.zeros(0)
    x = x + rng.normal(0, 10 ** (noise_db / 20), len(x))
    return AudioClip(x.astype(np.float32), rate)
