"""Text-to-speech: speakable text, 200-character chunks, quotas, Gemini and Orpheus, fallbacks (13.02–13.03).

VERIFIED 2026-10-16:
- Groq Orpheus (https://console.groq.com/docs/text-to-speech/orpheus): ``canopylabs/orpheus-v1-english`` (preview),
  max **200 characters** per request, WAV only, voices autumn, diana, hannah, austin, daniel, troy,
  ``[cheerful]``-style directions, $22 per 1M characters, no batch API. Free tier: 10 requests/min, 100/day,
  1.2K tokens/min, 3.6K tokens/day (https://console.groq.com/docs/rate-limits).
- Gemini 3.8 TTS (https://ai.google.dev/gemini-api/docs/speech-generation): Interactions API (``google-genai``
  >= 2.25), unary WAV 24 kHz mono (``sample_rate`` can be set), ``speech_metadata.style``, 30 prebuilt voices,
  100+ languages on ``gemini-3.8-flash-lite-tts``. Free of charge on the free tier.
"""
from __future__ import annotations

import base64
import hashlib
import re
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

__all__ = [
    "ORPHEUS_PRICE_PER_MILLION_CHARS",
    "ORPHEUS_VOICES",
    "BudgetExceeded",
    "FakeSpeaker",
    "ModelTermsRequired",
    "GeminiSpeaker",
    "OrpheusSpeaker",
    "Speaker",
    "SpeechResult",
    "TtsBudget",
    "cached_audio",
    "gemini_tts",
    "normalize_for_speech",
    "speak_with_fallback",
    "split_for_tts",
    "stitch_wavs",
]

ORPHEUS_MAX_CHARS = 200
ORPHEUS_VOICES = ("autumn", "diana", "hannah", "austin", "daniel", "troy")
ORPHEUS_PRICE_PER_MILLION_CHARS = 22.0


# --- 1. Text a voice can read ------------------------------------------------------------------

_MD = [(re.compile(r"```.*?```", re.S), " "), (re.compile(r"`([^`]*)`"), r"\1"), (re.compile(r"\*\*|__|\*|#+ "), ""),
       (re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)"), r"\1"), (re.compile(r"^\s*[-•]\s+", re.M), "")]


def normalize_for_speech(text: str) -> str:
    """Make chat text speakable: strip Markdown and URLs, spell IDs, say currencies.

    - ``C-1002`` → ``C-1-0-0-2`` (Orpheus reads hyphenated digits one by one; "one thousand and two" is wrong
      for an ID).  ``INV-88412`` likewise.
    - ``US$349`` / ``$349.00`` → ``349 dollars``; ``COP 47.600`` → ``47600 pesos``.
    - Bare URLs → "the link in our message" (nobody wants a URL read aloud).
    """
    for pattern, repl in _MD:
        text = pattern.sub(repl, text)
    text = re.sub(r"https?://\S+", "the link in our message", text)
    text = re.sub(r"\b([A-Z]{1,4})-(\d{3,})\b", lambda m: m.group(1) + "-" + "-".join(m.group(2)), text)
    text = re.sub(r"(?:US)?\$\s?(\d[\d,]*)(?:\.(\d\d))?", lambda m: m.group(1).replace(",", "")
                  + (f" dollars and {int(m.group(2))} cents" if m.group(2) and m.group(2) != "00" else " dollars"), text)
    text = re.sub(r"COP\s?(\d{1,3}(?:\.\d{3})+)", lambda m: m.group(1).replace(".", "") + " pesos", text)
    return re.sub(r"\s+", " ", text).strip()


def split_for_tts(text: str, max_chars: int = ORPHEUS_MAX_CHARS, direction: str | None = None) -> list[str]:
    """Split into chunks of at most ``max_chars`` (direction included), at sentence, then clause, then word ends.

    ``direction`` (e.g. ``"[friendly]"``) is prefixed to **every** chunk: each request is synthesized on its own,
    so a direction in chunk 1 does not carry over to chunk 2.
    """
    prefix = f"{direction} " if direction else ""
    room = max_chars - len(prefix)
    if room < 20:
        raise ValueError("direction leaves too little room in a chunk")
    pieces: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        if len(sentence) <= room:
            pieces.append(sentence)
            continue
        for clause in re.split(r"(?<=[,;:])\s+", sentence):
            while len(clause) > room:
                cut = clause.rfind(" ", 0, room)
                cut = cut if cut > 0 else room
                pieces.append(clause[:cut].strip())
                clause = clause[cut:].strip()
            if clause:
                pieces.append(clause)
    chunks: list[str] = []
    for piece in filter(None, pieces):
        if chunks and len(chunks[-1]) + 1 + len(piece) <= room:
            chunks[-1] += " " + piece
        else:
            chunks.append(piece)
    return [prefix + c for c in chunks]


# --- 2. Quotas -------------------------------------------------------------------------------------

ORPHEUS_TERMS_URL = "https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english"


class ModelTermsRequired(RuntimeError):
    """Groq ``400 model_terms_required``: an org admin must accept the model's terms once in the playground."""

    def __init__(self, model: str, url: str = ORPHEUS_TERMS_URL) -> None:
        super().__init__(f"model_terms_required: {model} needs its terms accepted once by your Groq org admin. "
                         f"Open {url}, accept, then re-run.")
        self.model, self.url = model, url


class BudgetExceeded(RuntimeError):
    """A TTS request would break a rate limit; ``wait_s`` says when it would fit (``inf`` = tomorrow)."""

    def __init__(self, message: str, wait_s: float) -> None:
        super().__init__(message)
        self.wait_s = wait_s


@dataclass
class TtsBudget:
    """Client-side guard for a provider's request and token limits (defaults: Orpheus free tier).

    Groq does not document how Orpheus counts tokens, so ``tokens_per_char`` defaults to a cautious 1.0:
    measure it from the ``x-ratelimit-remaining-tokens`` response header and adjust.
    """

    rpm: int = 10
    rpd: int = 100
    tpm: int = 1_200
    tpd: int = 3_600
    tokens_per_char: float = 1.0
    clock: Callable[[], float] = time.time
    _log: deque = field(default_factory=deque, repr=False)

    def _window(self, seconds: float) -> list[tuple[float, int]]:
        now = self.clock()
        return [(t, n) for t, n in self._log if now - t < seconds]

    def tokens(self, text: str) -> int:
        return max(1, int(len(text) * self.tokens_per_char + 0.5))

    def check(self, chunks: list[str]) -> None:
        """Raise :class:`BudgetExceeded` if sending all ``chunks`` now would break a limit."""
        need = sum(self.tokens(c) for c in chunks)
        day, minute = self._window(86_400), self._window(60)
        if len(day) + len(chunks) > self.rpd or sum(n for _, n in day) + need > self.tpd:
            raise BudgetExceeded(f"daily TTS budget: {len(day)}/{self.rpd} requests, "
                                 f"{sum(n for _, n in day)}/{self.tpd} tokens used, {need} more needed", float("inf"))
        if len(chunks) > self.rpm or need > self.tpm:
            raise BudgetExceeded(f"{len(chunks)} chunks / {need} tokens can never fit one minute "
                                 f"({self.rpm} requests, {self.tpm} tokens)", float("inf"))
        if len(minute) + len(chunks) > self.rpm or sum(n for _, n in minute) + need > self.tpm:
            oldest = minute[0][0] if minute else self.clock()
            raise BudgetExceeded("per-minute TTS limit: wait", max(0.0, 60 - (self.clock() - oldest)))

    def record(self, text: str) -> None:
        self._log.append((self.clock(), self.tokens(text)))
        while self._log and self.clock() - self._log[0][0] > 86_400:
            self._log.popleft()

    def remaining(self) -> dict[str, int]:
        day = self._window(86_400)
        return {"requests_today": self.rpd - len(day), "tokens_today": self.tpd - sum(n for _, n in day)}


# --- 3. Speakers -----------------------------------------------------------------------------------

@dataclass
class SpeechResult:
    """What a speaker produced. ``wav`` is ``None`` for a text-only fallback."""

    wav: bytes | None
    provider: str
    chunks: int
    chars: int
    first_audio_s: float
    total_s: float
    text: str = ""
    errors: list[str] = field(default_factory=list)
    from_cache: bool = False
    simulated: bool = False

    @property
    def cost_usd(self) -> float:
        return self.chars / 1e6 * ORPHEUS_PRICE_PER_MILLION_CHARS if self.provider.startswith("groq") else 0.0


class Speaker(Protocol):
    name: str

    def speak(self, text: str) -> SpeechResult: ...


def stitch_wavs(parts: list[bytes], gap_s: float = 0.12) -> bytes:
    """Join WAV chunks into one WAV (resampled to the first chunk's rate) with a short gap between them."""
    from mastery.voice.audio import concat, read_wav, silence

    clips = [read_wav(p) for p in parts]
    rate = clips[0].rate
    joined = []
    for i, c in enumerate(clips):
        joined.append(c.resample(rate))
        if i < len(clips) - 1:
            joined.append(silence(gap_s, rate))
    return concat(*joined).to_wav()


def _timed_chunks(name: str, chunks: list[str], synth: Callable[[str], bytes], budget: TtsBudget | None,
                  text: str) -> SpeechResult:
    if budget:
        budget.check(chunks)
    start, first, parts = time.perf_counter(), None, []
    for c in chunks:
        parts.append(synth(c))
        if budget:
            budget.record(c)
        if first is None:
            first = time.perf_counter() - start
    total = time.perf_counter() - start
    return SpeechResult(stitch_wavs(parts) if len(parts) > 1 else parts[0], name, len(chunks),
                        sum(len(c) for c in chunks), round(first or 0, 3), round(total, 3), text)


class OrpheusSpeaker:
    """Groq Orpheus (preview): splits into 200-character chunks, checks the budget, stitches the WAVs."""

    def __init__(self, model: str | None = None, voice: str | None = None, *, direction: str | None = None,
                 budget: TtsBudget | None = None, client: Any = None) -> None:
        from mastery.config import load_settings

        settings = load_settings()
        self.model, self.voice = model or settings.model_tts, voice or settings.tts_voice
        if self.voice not in ORPHEUS_VOICES:
            raise ValueError(f"Orpheus English voices: {ORPHEUS_VOICES}")
        self.direction, self.budget = direction, budget if budget is not None else TtsBudget()
        if client is None:
            from groq import Groq

            client = Groq(timeout=60, max_retries=2)
        self.client, self.name = client, f"groq:{self.model}"

    def _one(self, chunk: str) -> bytes:
        try:
            resp = self.client.audio.speech.create(model=self.model, voice=self.voice, input=chunk, response_format="wav")
        except Exception as error:
            # VERIFIED 2026-10-16: Groq answers 400 with code "model_terms_required" until the org accepts
            # Orpheus's terms in the playground. Say so plainly instead of a raw 400.
            if "model_terms_required" in str(error) or "terms acceptance" in str(error):
                url = ORPHEUS_TERMS_URL.replace("canopylabs%2Forpheus-v1-english", self.model.replace("/", "%2F"))
                raise ModelTermsRequired(self.model, url) from error
            raise
        return resp.read() if hasattr(resp, "read") else bytes(resp)

    def speak(self, text: str) -> SpeechResult:
        return _timed_chunks(self.name, split_for_tts(text, direction=self.direction), self._one, self.budget, text)


class GeminiSpeaker:
    """Gemini TTS: one request for a whole answer (no 200-character limit), any of 100+ languages."""

    def __init__(self, model: str | None = None, voice: str | None = None, *, style: str | None = None,
                 sample_rate: int = 24_000, max_chars: int = 2_000, client: Any = None) -> None:
        from mastery.config import load_settings

        settings = load_settings()
        self.model, self.voice = model or settings.model_tts_gemini, voice or settings.tts_voice_gemini
        self.style, self.sample_rate, self.max_chars, self.client = style, sample_rate, max_chars, client
        self.name = f"google_genai:{self.model}"

    def _one(self, chunk: str) -> bytes:
        return gemini_tts(chunk, model=self.model, voice=self.voice, style=self.style,
                          sample_rate=self.sample_rate, client=self.client)

    def speak(self, text: str) -> SpeechResult:
        return _timed_chunks(self.name, split_for_tts(text, self.max_chars), self._one, None, text)


class FakeSpeaker:
    """Offline stand-in: a soft tone per chunk, about 15 characters per second; can be told to fail."""

    def __init__(self, name: str = "simulated-tts", *, max_chars: int = ORPHEUS_MAX_CHARS, fail: str | None = None,
                 seconds_per_request: float = 0.0, seconds_per_char: float = 0.0, budget: TtsBudget | None = None) -> None:
        self.name, self.max_chars, self.fail, self.delay, self.budget = name, max_chars, fail, seconds_per_request, budget
        self.per_char = seconds_per_char

    def _one(self, chunk: str) -> bytes:
        from mastery.voice.audio import tone

        if self.fail:
            raise RuntimeError(self.fail)
        if self.delay or self.per_char:
            time.sleep(self.delay + self.per_char * len(chunk))
        return tone(220 + 10 * (len(chunk) % 7), max(0.3, len(chunk) / 15), rate=24_000, amplitude=0.05).to_wav()

    def speak(self, text: str) -> SpeechResult:
        result = _timed_chunks(self.name, split_for_tts(text, self.max_chars), self._one, self.budget, text)
        result.simulated = True
        return result


def speak_with_fallback(text: str, speakers: list[Any], *, cache_dir: str | Path | None = None) -> SpeechResult:
    """Try each speaker in order; cache successes by (speaker, text); end with a text-only answer.

    A voice answer that fails must still be an answer: the last resort returns ``wav=None`` with the text,
    so the UI shows it instead of an error.
    """
    errors: list[str] = []
    for spk in speakers:
        path = None
        if cache_dir:
            digest = hashlib.sha256(f"{spk.name}|{getattr(spk, 'voice', '')}|{text}".encode()).hexdigest()[:16]
            path = Path(cache_dir) / f"{digest}.wav"
            if path.is_file():
                return SpeechResult(path.read_bytes(), spk.name, 0, 0, 0.0, 0.0, text, errors, from_cache=True)
        try:
            result = spk.speak(text)
        except Exception as error:  # noqa: BLE001 - any provider failure falls through to the next speaker
            errors.append(f"{spk.name}: {type(error).__name__}: {error}"[:200])
            continue
        result.errors = errors
        if path and result.wav and not result.simulated:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(result.wav)
        return result
    return SpeechResult(None, "text-only", 0, 0, 0.0, 0.0, text, errors)


# --- 4. Gemini call and cache (used since Lesson 13.02) -------------------------------------------

def gemini_tts(text: str, *, model: str | None = None, voice: str | None = None, style: str | None = None,
               sample_rate: int = 24_000, client: Any = None) -> bytes:
    """Synthesize ``text`` with Gemini TTS and return WAV bytes. Needs ``GOOGLE_API_KEY``."""
    from mastery.config import load_settings

    settings = load_settings()
    if client is None:
        from google import genai

        client = genai.Client()
    item: dict[str, Any] = {"type": "text", "text": text}
    if style:
        item["annotations"] = [{"type": "speech_metadata", "style": style}]
    interaction = client.interactions.create(
        model=model or settings.model_tts_gemini,
        input=[{"type": "user_input", "content": [item]}],
        response_format={"type": "audio", "mime_type": "audio/wav", "sample_rate": sample_rate},
        generation_config={"speech_config": [{"voice": voice or settings.tts_voice_gemini}]},
    )
    return base64.b64decode(interaction.output_audio.data)


def cached_audio(path: str | Path, make: Any) -> tuple[bytes, bool]:
    """Return ``(bytes, from_cache)``: read ``path`` if it exists, else call ``make()`` and save it.

    Synthesized test audio is deterministic enough to reuse: re-running a lesson costs no quota.
    """
    path = Path(path)
    if path.is_file() and path.stat().st_size > 44:
        return path.read_bytes(), True
    data = make()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data, False
