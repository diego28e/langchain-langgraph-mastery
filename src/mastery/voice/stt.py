"""Speech-to-text with Groq Whisper, plus the checks a transcript needs (Lesson 13.02).

VERIFIED 2026-10-16 (https://console.groq.com/docs/speech-to-text):
- ``whisper-large-v3-turbo``: $0.04 per hour, transcription only. ``whisper-large-v3``: $0.111 per hour,
  transcription **and** translation to English. Billed per request with a 10-second minimum.
- Files up to 25 MB (free tier) or 100 MB (dev tier); ``prompt`` up to 224 tokens.
- ``verbose_json`` adds segments (``avg_logprob``, ``no_speech_prob``, ``compression_ratio``) and, with
  ``timestamp_granularities``, word timestamps. No streaming transcription is documented.
- Free tier: 20 requests/minute, 2,000/day, 7,200 audio seconds/hour, 28,800/day
  (https://console.groq.com/docs/rate-limits).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from mastery.voice.audio import AudioClip, chunk, read_wav

__all__ = [
    "FakeTranscriber",
    "GroqTranscriber",
    "Segment",
    "Transcriber",
    "Transcript",
    "WHISPER_PRICE_PER_HOUR",
    "flag_segments",
    "normalize_words",
    "parse_verbose_json",
    "transcribe_long",
    "wer",
    "whisper_cost",
]

WHISPER_PRICE_PER_HOUR = {"whisper-large-v3-turbo": 0.04, "whisper-large-v3": 0.111}
MIN_BILLED_SECONDS = 10.0
MAX_UPLOAD_MB = {"free": 25, "dev": 100}


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0
    compression_ratio: float = 1.0


@dataclass
class Transcript:
    text: str
    language: str | None = None
    duration: float | None = None
    segments: list[Segment] = field(default_factory=list)
    words: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    simulated: bool = False


class Transcriber(Protocol):
    def transcribe(self, audio: Any, *, key: str | None = None, prompt: str | None = None,
                   language: str | None = None) -> Transcript: ...


def parse_verbose_json(data: dict[str, Any], model: str = "") -> Transcript:
    """Turn a Whisper ``verbose_json`` response (dict) into a :class:`Transcript`."""
    segs = [
        Segment(float(s.get("start", 0)), float(s.get("end", 0)), str(s.get("text", "")).strip(),
                float(s.get("avg_logprob", 0.0)), float(s.get("no_speech_prob", 0.0)),
                float(s.get("compression_ratio", 1.0)))
        for s in data.get("segments") or []
    ]
    return Transcript(text=str(data.get("text", "")).strip(), language=data.get("language"),
                      duration=data.get("duration"), segments=segs, words=list(data.get("words") or []), model=model)


def flag_segments(t: Transcript, *, max_no_speech: float = 0.6, min_logprob: float = -1.0,
                  max_compression: float = 2.4) -> list[tuple[Segment, str]]:
    """Segments a human should check, with the reason (Whisper's own decoding thresholds).

    - ``no_speech_prob`` high **and** ``avg_logprob`` low: probably text invented over silence/noise.
    - ``compression_ratio`` above 2.4: repetitive text, the classic Whisper loop.
    - ``avg_logprob`` below -1: low confidence.
    """
    flagged = []
    for s in t.segments:
        if s.no_speech_prob > max_no_speech and s.avg_logprob < min_logprob:
            flagged.append((s, f"likely no speech (no_speech_prob {s.no_speech_prob:.2f})"))
        elif s.compression_ratio > max_compression:
            flagged.append((s, f"repetitive (compression_ratio {s.compression_ratio:.1f})"))
        elif s.avg_logprob < min_logprob:
            flagged.append((s, f"low confidence (avg_logprob {s.avg_logprob:.2f})"))
    return flagged


def normalize_words(text: str) -> list[str]:
    """Lowercase, drop punctuation, split hyphens: 'C-1002,' and 'c 1002' compare equal."""
    text = text.casefold().replace("-", " ")
    return re.findall(r"[\w']+", text)


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate: (substitutions + deletions + insertions) / reference words."""
    ref, hyp = normalize_words(reference), normalize_words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, start=1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return round(prev[-1] / len(ref), 4)


def whisper_cost(seconds: float, model: str = "whisper-large-v3-turbo") -> float:
    """USD for one request: per-hour price, at least 10 seconds billed."""
    return max(seconds, MIN_BILLED_SECONDS) / 3600 * WHISPER_PRICE_PER_HOUR[model]


def _as_upload(audio: Any) -> tuple[str, bytes, float | None]:
    if isinstance(audio, AudioClip):
        return "audio.wav", audio.to_wav(16_000), audio.seconds
    if isinstance(audio, bytes):
        return "audio.wav", audio, None
    path = Path(audio)
    seconds = read_wav(path).seconds if path.suffix.lower() == ".wav" else None
    return path.name, path.read_bytes(), seconds


class GroqTranscriber:
    """Groq Whisper through the ``groq`` SDK (``langchain-groq`` has no speech-to-text class).

    ``translate=True`` uses the translations endpoint (English output, ``whisper-large-v3`` only).
    """

    def __init__(self, model: str | None = None, *, translate: bool = False, temperature: float = 0.0,
                 timeout: float = 120.0, client: Any = None) -> None:
        from mastery.config import load_settings

        self.model = model or load_settings().model_stt
        if translate and self.model != "whisper-large-v3":
            raise ValueError("translation needs whisper-large-v3 (turbo only transcribes)")
        self.translate, self.temperature = translate, temperature
        if client is None:
            from groq import Groq

            client = Groq(timeout=timeout, max_retries=2)
        self.client = client

    def transcribe(self, audio: Any, *, key: str | None = None, prompt: str | None = None,
                   language: str | None = None) -> Transcript:
        name, data, seconds = _as_upload(audio)
        if len(data) > MAX_UPLOAD_MB["free"] * 1024 * 1024:
            raise ValueError(f"{len(data) / 1e6:.0f} MB is over the free tier's 25 MB: chunk it (transcribe_long)")
        params: dict[str, Any] = {"model": self.model, "file": (name, data), "response_format": "verbose_json",
                                  "temperature": self.temperature}
        if prompt:
            params["prompt"] = prompt
        if self.translate:
            resp = self.client.audio.translations.create(**params)
        else:
            if language:
                params["language"] = language
            params["timestamp_granularities"] = ["word", "segment"]
            resp = self.client.audio.transcriptions.create(**params)
        data_out = resp.to_dict() if hasattr(resp, "to_dict") else resp.model_dump()
        t = parse_verbose_json(data_out, self.model)
        if t.duration is None:
            t.duration = seconds
        return t


class FakeTranscriber:
    """Offline stand-in: returns scripted transcripts by ``key`` (marked ``simulated=True``).

    ``responses[key]`` is a dict like a ``verbose_json`` response; an optional ``"with_prompt"``
    variant is used when a ``prompt`` is passed, to show what spelling hints change.
    """

    def __init__(self, responses: dict[str, dict[str, Any]] | Callable[[str], dict[str, Any]],
                 model: str = "simulated-whisper") -> None:
        self.responses, self.model, self.calls = responses, model, 0

    def transcribe(self, audio: Any = None, *, key: str | None = None, prompt: str | None = None,
                   language: str | None = None) -> Transcript:
        self.calls += 1
        data = self.responses(key) if callable(self.responses) else self.responses[key]
        if prompt and "with_prompt" in data:
            data = {**data, **data["with_prompt"]}
        t = parse_verbose_json(data, self.model)
        t.simulated = True
        return t


def transcribe_long(clip: AudioClip, transcriber: Transcriber, *, max_seconds: float = 600.0,
                    overlap_seconds: float = 2.0, key: str | None = None, **kwargs: Any) -> Transcript:
    """Transcribe a clip of any length in overlapping chunks and stitch the segments.

    Each chunk's timestamps are shifted by its start. A segment that starts before the previous kept
    segment ended was already transcribed in the overlap and is dropped, so words are not duplicated.
    """
    merged: list[Segment] = []
    for i, (start, part) in enumerate(chunk(clip, max_seconds, overlap_seconds)):
        t = transcriber.transcribe(part, key=f"{key}#{i}" if key else None, **kwargs)
        for s in t.segments:
            shifted = Segment(s.start + start, s.end + start, s.text, s.avg_logprob, s.no_speech_prob, s.compression_ratio)
            # A segment that starts before the last kept one ended was already heard in the overlap.
            if not merged or shifted.start >= merged[-1].end - 0.25:
                merged.append(shifted)
    return Transcript(text=" ".join(s.text for s in merged), duration=clip.seconds, segments=merged,
                      model=getattr(transcriber, "model", ""),
                      simulated=isinstance(transcriber, FakeTranscriber))
