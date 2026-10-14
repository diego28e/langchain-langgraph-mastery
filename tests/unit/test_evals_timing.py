"""Unit tests for mastery.evals.timing (offline: fake clocks, fake models, no network)."""

from __future__ import annotations

import asyncio
import math
import time
import warnings
from collections.abc import AsyncIterator, Iterator

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.runnables import RunnableLambda

from mastery.evals.timing import (
    LatencySummary,
    LimiterInsideTimingWarning,
    ServerTiming,
    Timed,
    astream_timings,
    atimed_invoke,
    attached_rate_limiters,
    latency_summary,
    nearest_rank,
    server_timing,
    stream_timings,
    timed_invoke,
)
from mastery.testing import ScriptedChatModel

# The fields Groq returns in token_usage (shape copied from langchain-groq 1.1.3's docstring example).
GROQ_USAGE = {
    "completion_tokens": 38,
    "prompt_tokens": 28,
    "total_tokens": 66,
    "completion_time": 0.25,
    "prompt_time": 0.05,
    "queue_time": 0.1,
    "total_time": 0.3,
}


class FakeClock:
    """A clock that only moves when told to (or by ``step`` on every read)."""

    def __init__(self, step: float = 0.0) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        value = self.now
        self.now += self.step
        return value

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeLimiter:
    """Waits ``seconds`` of fake time on every acquire."""

    def __init__(self, clock: FakeClock, seconds: float) -> None:
        self.clock, self.seconds, self.calls = clock, seconds, 0

    def acquire(self, *, blocking: bool = True) -> bool:
        self.calls += 1
        self.clock.advance(self.seconds)
        return True

    async def aacquire(self, *, blocking: bool = True) -> bool:
        return self.acquire(blocking=blocking)


class FakeModel:
    """Takes ``seconds`` of fake time per call and returns a Groq-like reply."""

    def __init__(self, clock: FakeClock, seconds: float, usage: dict | None = None) -> None:
        self.clock, self.seconds, self.usage = clock, seconds, usage

    def _reply(self) -> AIMessage:
        self.clock.advance(self.seconds)
        metadata = {"token_usage": self.usage} if self.usage else {}
        return AIMessage("ok", response_metadata=metadata)

    def invoke(self, input: str, config: dict | None = None) -> AIMessage:  # noqa: A002
        return self._reply()

    async def ainvoke(self, input: str, config: dict | None = None) -> AIMessage:  # noqa: A002
        return self._reply()


# ---------------------------------------------------------------------------
# timed_invoke
# ---------------------------------------------------------------------------


def test_timed_invoke_excludes_the_limiter_wait() -> None:
    clock = FakeClock()
    limiter = FakeLimiter(clock, seconds=7.5)
    timed = timed_invoke(FakeModel(clock, seconds=0.4), "hi", limiter=limiter, clock=clock)
    assert timed.waited_s == pytest.approx(7.5)
    assert timed.latency_s == pytest.approx(0.4)
    assert limiter.calls == 1 and timed.output.text == "ok"


def test_timed_invoke_reads_server_timing() -> None:
    clock = FakeClock()
    timed = timed_invoke(FakeModel(clock, seconds=0.5, usage=GROQ_USAGE), "hi", clock=clock)
    assert (timed.server_s, timed.queue_s) == (0.3, 0.1)
    assert timed.overhead_s == pytest.approx(0.1)  # 0.5 - 0.3 - 0.1: network + SDK
    assert Timed(output=None, latency_s=1.0).overhead_s is None


def test_async_timed_invoke() -> None:
    clock = FakeClock()
    limiter = FakeLimiter(clock, seconds=2.0)
    timed = asyncio.run(atimed_invoke(FakeModel(clock, 0.25, GROQ_USAGE), "hi", limiter=limiter, clock=clock))
    assert (timed.waited_s, timed.latency_s, timed.server_s) == (2.0, 0.25, 0.3)


def test_real_rate_limiter_wait_stays_out_of_latency() -> None:
    # Fresh InMemoryRateLimiter starts with an empty bucket: the first acquire waits ~1/rps.
    limiter = InMemoryRateLimiter(requests_per_second=10, check_every_n_seconds=0.005, max_bucket_size=1)
    model = ScriptedChatModel(responses=["instant"])
    timed = timed_invoke(model, "hi", limiter=limiter)
    assert timed.waited_s >= 0.05
    assert timed.latency_s < timed.waited_s
    assert timed.output.text == "instant"


def test_naive_timing_around_a_throttled_model_measures_the_throttle() -> None:
    limiter = InMemoryRateLimiter(requests_per_second=10, check_every_n_seconds=0.005, max_bucket_size=1)
    model = ScriptedChatModel(responses=["instant"], rate_limiter=limiter)
    start = time.perf_counter()
    model.invoke("hi")
    assert time.perf_counter() - start >= 0.05  # the wait happened inside invoke


def test_attached_limiter_triggers_a_warning() -> None:
    limiter = InMemoryRateLimiter(requests_per_second=1000, check_every_n_seconds=0.001)
    model = ScriptedChatModel(responses=["a", "b"], rate_limiter=limiter)
    chain = RunnableLambda(lambda x: x) | model
    assert attached_rate_limiters(chain) == [limiter]
    with pytest.warns(LimiterInsideTimingWarning, match="timed_invoke"):
        timed_invoke(chain, "hi")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        timed_invoke(chain, "hi", warn_attached_limiter=False)
    assert not [w for w in caught if issubclass(w.category, LimiterInsideTimingWarning)]


def test_no_limiter_found_on_a_plain_model() -> None:
    assert attached_rate_limiters(ScriptedChatModel(responses=["a"])) == []


def test_timed_invoke_re_raises_errors() -> None:
    def boom(_: str) -> str:
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError, match="provider down"):
        timed_invoke(RunnableLambda(boom), "hi")


# ---------------------------------------------------------------------------
# server_timing
# ---------------------------------------------------------------------------


def test_server_timing_from_message_and_include_raw_dict() -> None:
    message = AIMessage("ok", response_metadata={"token_usage": GROQ_USAGE})
    expected = ServerTiming(total_s=0.3, queue_s=0.1, prompt_s=0.05, completion_s=0.25)
    assert server_timing(message) == expected
    assert server_timing({"raw": message, "parsed": None, "parsing_error": None}) == expected


def test_server_timing_missing_fields() -> None:
    assert server_timing(AIMessage("ok")) is None  # OpenAI/Gemini replies, fakes
    assert server_timing({"parsed": "no raw"}) is None
    assert server_timing("plain text") is None
    usage = {"total_time": 0.2, "queue_time": None, "prompt_tokens": 3}
    timing = server_timing(AIMessage("ok", response_metadata={"token_usage": usage}))
    assert timing == ServerTiming(total_s=0.2)


# ---------------------------------------------------------------------------
# stream_timings
# ---------------------------------------------------------------------------


def _reasoning_stream() -> Iterator[AIMessageChunk]:
    yield AIMessageChunk(content="")  # role-only first chunk
    yield AIMessageChunk(content="", additional_kwargs={"reasoning_content": "Let me think."})
    yield AIMessageChunk(content="Hel")
    yield AIMessageChunk(content="lo")


def test_stream_timings_separates_first_chunk_visible_and_answer() -> None:
    clock = FakeClock(step=1.0)  # every clock read advances 1 s
    timings = stream_timings(_reasoning_stream(), clock=clock)
    assert timings.first_chunk_s < timings.first_visible_s < timings.first_answer_s
    assert (timings.first_chunk_s, timings.first_visible_s, timings.first_answer_s) == (1.0, 2.0, 3.0)
    assert timings.total_s == 5.0 and timings.n_chunks == 4
    assert timings.output.text == "Hello"
    assert "first answer 3.000 s" in str(timings)


def test_stream_timings_waits_for_limiter_before_the_clock() -> None:
    clock = FakeClock()
    limiter = FakeLimiter(clock, seconds=3.0)
    timings = stream_timings(iter(["a"]), limiter=limiter, clock=clock)
    assert timings.waited_s == 3.0 and timings.total_s == 0.0


def test_stream_timings_handles_strings_blocks_and_non_addable_chunks() -> None:
    clock = FakeClock(step=1.0)
    text = stream_timings(iter(["", "  ", "Hi"]), clock=clock)
    assert text.first_chunk_s == 1.0 and text.first_visible_s == text.first_answer_s == 3.0
    assert text.output == "  Hi"

    blocks = [AIMessageChunk(content=[{"type": "reasoning", "reasoning": "hmm"}]), AIMessageChunk(content="ok")]
    timed = stream_timings(iter(blocks), clock=FakeClock(step=1.0))
    assert (timed.first_visible_s, timed.first_answer_s) == (1.0, 2.0)

    dicts = stream_timings(iter([{"a": 1}, {"b": 2}]), clock=FakeClock(step=1.0))
    assert dicts.output == [{"a": 1}, {"b": 2}] and dicts.first_answer_s is None


def test_stream_timings_with_a_real_chat_model_stream() -> None:
    model = ScriptedChatModel(responses=["Hello world"])
    timings = stream_timings(model.stream("hi"))
    assert timings.n_chunks >= 1 and timings.first_answer_s is not None
    assert timings.output.text == "Hello world"


def test_astream_timings() -> None:
    async def chunks() -> AsyncIterator[AIMessageChunk]:
        for chunk in _reasoning_stream():
            yield chunk

    timings = asyncio.run(astream_timings(chunks(), clock=FakeClock(step=1.0)))
    assert (timings.first_chunk_s, timings.first_visible_s, timings.first_answer_s) == (1.0, 2.0, 3.0)


# ---------------------------------------------------------------------------
# Percentiles
# ---------------------------------------------------------------------------


def test_latency_summary_nearest_rank() -> None:
    summary = latency_summary([1, 2, 3, 4, 100])
    assert (summary.p50, summary.p95, summary.max, summary.min) == (3.0, 100.0, 100.0, 1.0)
    assert summary.mean == pytest.approx(22.0)
    assert summary.p95_is_max and "p95 is the max" in str(summary)


def test_latency_summary_skips_missing_values() -> None:
    summary = latency_summary([0.5, None, math.nan, 1.5])
    assert (summary.n, summary.missing, summary.p50) == (2, 2, 0.5)
    empty = latency_summary([None, None])
    assert empty == LatencySummary(0, 2, None, None, None, None, None)
    assert "no latency data" in str(empty)
    assert latency_summary([]).n == 0


def test_p95_differs_from_max_from_twenty_values() -> None:
    values = list(range(1, 21))
    summary = latency_summary(values)
    assert summary.p95 == 19.0 and summary.max == 20.0 and not summary.p95_is_max
    assert summary.as_dict()["p50"] == 10.0


def test_nearest_rank_validates_input() -> None:
    assert nearest_rank([5.0], 1) == 5.0
    assert nearest_rank([3, 1, 2], 100) == 3.0
    with pytest.raises(ValueError):
        nearest_rank([], 50)
    with pytest.raises(ValueError):
        nearest_rank([1.0], 0)
