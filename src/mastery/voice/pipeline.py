"""The batch voice "sandwich": speech-to-text → agent → text-to-speech, timed per stage (Lesson 13.04).

Simplified on purpose: the caller's whole question is recorded first, then transcribed. The one overlap the
batch version allows is on the way out: with ``mode="sentences"`` the agent's reply is streamed, and each
finished sentence goes to TTS while the agent keeps writing, so the first audio is ready much sooner.
Real-time agents stream every stage (Lesson 13.05).
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from mastery.voice.stt import Transcriber, Transcript
from mastery.voice.tts import SpeechResult, normalize_for_speech, speak_with_fallback, stitch_wavs

__all__ = ["GraphAgent", "ScriptedAgent", "VoicePipeline", "VoiceTurn", "fix_ids", "for_voice", "sentences"]

_CITATION = re.compile(r"\[[^\]]*(?:/|\.md|\.pdf)[^\]]*\]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def for_voice(text: str, max_sentences: int = 3) -> str:
    """Shorten an agent reply for listening: drop file citations and headings, keep the first sentences.

    Listeners can't skim: three sentences is about 15 seconds of speech.
    """
    text = _CITATION.sub("", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"^#+ .*$", "", text, flags=re.M)
    text = normalize_for_speech(text)
    parts = [p for p in _SENTENCE_END.split(text) if p.strip()]
    return " ".join(parts[:max_sentences]).strip()


def fix_ids(text: str, prefixes: tuple[str, ...] = ("C", "INV")) -> str:
    """Restore ID formats Whisper often loses: ``C1002`` / ``c 1002`` / ``C. 1002`` → ``C-1002``."""
    for p in prefixes:
        text = re.sub(rf"\b{p}[\s.\-]*(\d{{4,}})\b", f"{p}-\\1", text, flags=re.I)
    return text


def sentences(tokens: Iterator[str], min_chars: int = 20) -> Iterator[str]:
    """Group a token stream into sentences as soon as each one ends (at least ``min_chars`` long)."""
    buf = ""
    for tok in tokens:
        buf += tok
        while True:
            m = _SENTENCE_END.search(buf, min_chars)
            if not m:
                break
            yield buf[:m.start()].strip()
            buf = buf[m.end():]
    if buf.strip():
        yield buf.strip()


class GraphAgent:
    """Wrap a LangGraph/``create_agent`` app as ``invoke(text) -> str`` and ``stream(text) -> tokens``.

    One thread per caller (``thread_id``), the signed-in customer as runtime ``context``.
    """

    def __init__(self, app: Any, *, context: Any = None, thread_id: str | None = None) -> None:
        self.app, self.context = app, context
        self.config = {"configurable": {"thread_id": thread_id or f"voice-{uuid.uuid4().hex[:8]}"}}

    def invoke(self, text: str) -> str:
        out = self.app.invoke({"messages": [{"role": "user", "content": text}]}, self.config, context=self.context)
        return out["messages"][-1].text if hasattr(out["messages"][-1], "text") else str(out["messages"][-1].content)

    def stream(self, text: str) -> Iterator[str]:
        """Yield the text of the final answer as it is generated (tool-call chunks are skipped)."""
        for chunk, meta in self.app.stream({"messages": [{"role": "user", "content": text}]}, self.config,
                                           context=self.context, stream_mode="messages"):
            if getattr(chunk, "type", "") in ("AIMessageChunk", "ai") and not getattr(chunk, "tool_call_chunks", None) \
                    and not getattr(chunk, "tool_calls", None):
                piece = chunk.text if hasattr(chunk, "text") else chunk.content
                if isinstance(piece, str) and piece:
                    yield piece


class ScriptedAgent:
    """Offline stand-in for a streaming agent: a fixed reply per question, emitted at ``tokens_per_s``.

    ``think_s`` is the wait before the first token (tool calls, reasoning). Used to show what sentence
    streaming changes without a key; its timings are SIMULATED.
    """

    def __init__(self, reply: str | Callable[[str], str], *, think_s: float = 0.6, tokens_per_s: float = 60.0) -> None:
        self.reply, self.think_s, self.tokens_per_s = reply, think_s, tokens_per_s

    def _text(self, question: str) -> str:
        return self.reply(question) if callable(self.reply) else self.reply

    def stream(self, question: str) -> Iterator[str]:
        time.sleep(self.think_s)
        for word in re.findall(r"\S+\s*", self._text(question)):
            time.sleep(1 / self.tokens_per_s)
            yield word

    def invoke(self, question: str) -> str:
        return "".join(self.stream(question))


@dataclass
class VoiceTurn:
    transcript: Transcript
    reply: str
    spoken: str
    speech: SpeechResult
    timings: dict[str, float] = field(default_factory=dict)
    mode: str = "sequential"

    @property
    def first_audio_s(self) -> float:
        """Seconds from the end of the caller's question to the first playable audio."""
        return self.timings["first_audio"]


class VoicePipeline:
    """STT → agent → TTS with per-stage timings and a text-only fallback.

    ``agent`` needs ``invoke(text) -> str`` (and ``stream(text)`` for ``mode="sentences"``), e.g. :class:`GraphAgent`.
    ``clean_transcript`` fixes known STT slips before the agent sees the text (e.g. :func:`fix_ids`).
    ``speakers`` are tried in order (:func:`speak_with_fallback`); if all fail the turn still has the text.
    """

    def __init__(self, stt: Transcriber, agent: Any, speakers: list[Any], *, max_sentences: int = 3,
                 stt_options: dict[str, Any] | None = None, clean_transcript: Callable[[str], str] | None = None,
                 clock: Callable[[], float] = time.perf_counter) -> None:
        self.stt, self.agent, self.speakers, self.clean = stt, agent, speakers, clean_transcript
        self.max_sentences, self.stt_options, self.clock = max_sentences, stt_options or {}, clock

    def run(self, audio: Any, *, key: str | None = None, mode: str = "sequential") -> VoiceTurn:
        if mode not in ("sequential", "sentences"):
            raise ValueError("mode must be 'sequential' or 'sentences'")
        t0 = self.clock()
        transcript = self.stt.transcribe(audio, key=key, **self.stt_options)
        if self.clean:
            transcript.text = self.clean(transcript.text)
        t_stt = self.clock()
        if mode == "sequential":
            reply = self.agent.invoke(transcript.text)
            t_agent = self.clock()
            spoken = for_voice(reply, self.max_sentences)
            speech = speak_with_fallback(spoken, self.speakers)
            t_end = self.clock()
            first = (t_agent - t0) + (speech.first_audio_s if speech.wav else 0.0)
            timings = {"stt": t_stt - t0, "agent": t_agent - t_stt, "tts": t_end - t_agent, "first_audio": first, "total": t_end - t0}
        else:
            parts, said, reply_parts, first, errors = [], [], [], None, []
            t_first_sentence = None
            for sentence in sentences(self.agent.stream(transcript.text)):
                reply_parts.append(sentence)
                if len(said) >= self.max_sentences:
                    continue                       # keep reading the reply, stop speaking it
                if t_first_sentence is None:
                    t_first_sentence = self.clock()
                spoken_s = for_voice(sentence, 1)
                if not spoken_s:
                    continue
                result = speak_with_fallback(spoken_s, self.speakers)
                errors += result.errors
                said.append(spoken_s)
                if result.wav:
                    parts.append(result.wav)
                    if first is None:
                        first = self.clock() - t0
            t_end = self.clock()
            reply, spoken = " ".join(reply_parts), " ".join(said)
            speech = SpeechResult(stitch_wavs(parts) if parts else None, "+".join(sorted({s.name for s in self.speakers})) or "text-only",
                                  len(parts), len(spoken), 0.0, 0.0, spoken, errors)
            t_first_sentence = t_first_sentence or t_end
            timings = {"stt": t_stt - t0, "agent": t_first_sentence - t_stt, "tts": t_end - t_first_sentence,
                       "first_audio": first if first is not None else t_end - t0, "total": t_end - t0}
        return VoiceTurn(transcript, reply, spoken, speech, {k: round(v, 3) for k, v in timings.items()}, mode)
