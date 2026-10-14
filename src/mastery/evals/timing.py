"""Measure model latency honestly: what to time, what to leave out, how to summarize.

Introduced in Module 01 (Lessons 01.05 and 01.06, Project 01) and reused by
every later module that reports latency.

Three traps this module avoids:
    1. **Timing your own throttle.** A LangChain ``rate_limiter`` attached to a
       chat model waits *inside* ``invoke`` (after the run has started), so a
       stopwatch around ``invoke`` measures your rate limit, not the model.
       :func:`timed_invoke` waits for the limiter first and starts the clock
       after, and reports both numbers.
    2. **Calling the first chunk "time to first token".** A stream often starts
       with an empty chunk (role only), then reasoning, then the answer. A
       user who does not see the reasoning waits for the first *answer* token.
       :func:`stream_timings` records all three moments.
    3. **Averages of skewed numbers.** Latency has a long tail, so report the
       median (p50) and a high percentile (p95), not the mean.
       :func:`latency_summary` does that with the nearest-rank method.

Client time vs server time:
    The wall-clock time you measure includes the network, the SDK, any SDK
    retries and their back-off sleeps. Some providers also report their own
    timing. Groq puts ``queue_time`` and ``total_time`` (prompt + completion
    processing, in seconds) in ``response_metadata["token_usage"]`` of
    non-streamed replies; :func:`server_timing` reads it when present and
    returns None otherwise (OpenAI and Gemini replies, streams, fakes).

Pure standard library: works with any object that has ``invoke`` /
``ainvoke`` and with any rate limiter that has ``acquire`` / ``aacquire``
(LangChain's ``InMemoryRateLimiter``).
"""

from __future__ import annotations

import math
import time
import warnings
from collections.abc import AsyncIterable, Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

__all__ = [
    "LatencySummary",
    "LimiterInsideTimingWarning",
    "ServerTiming",
    "StreamTimings",
    "Timed",
    "astream_timings",
    "atimed_invoke",
    "attached_rate_limiters",
    "latency_summary",
    "nearest_rank",
    "server_timing",
    "stream_timings",
    "timed_invoke",
]

Clock = Callable[[], float]

# Below this many samples, the nearest-rank p95 is simply the maximum.
P95_MIN_SAMPLES = 20

# VERIFIED 2026-10-14: groq 0.37.1 CompletionUsage documents queue_time ("time the
# request was spent queued") and total_time ("completion time and prompt time
# combined"), in seconds; langchain-groq 1.1.3 copies the usage dict into
# response_metadata["token_usage"] for non-streamed calls.
_SERVER_FIELDS = {
    "total_s": "total_time",
    "queue_s": "queue_time",
    "prompt_s": "prompt_time",
    "completion_s": "completion_time",
}


class LimiterInsideTimingWarning(UserWarning):
    """A rate limiter attached to the model will be timed as model latency."""


# ---------------------------------------------------------------------------
# Server-reported timing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServerTiming:
    """Timing reported by the provider for one call (seconds; None if absent).

    Attributes:
        total_s: Time the provider spent processing (prompt + completion).
        queue_s: Time the request waited in the provider's queue.
        prompt_s: Time spent reading the input tokens.
        completion_s: Time spent generating output tokens.
    """

    total_s: float | None = None
    queue_s: float | None = None
    prompt_s: float | None = None
    completion_s: float | None = None


def _message_of(output: Any) -> Any:
    """Find the AIMessage in a model or structured-output result."""
    # with_structured_output(..., include_raw=True) returns {"raw": AIMessage, "parsed": ...}.
    if isinstance(output, Mapping) and "raw" in output:
        return output["raw"]
    return output


def server_timing(output: Any) -> ServerTiming | None:
    """Read provider-reported timing from a reply, when the provider sends it.

    Args:
        output: An ``AIMessage``, or the dict returned by
            ``with_structured_output(..., include_raw=True)``.

    Returns:
        A :class:`ServerTiming`, or None when the reply carries no timing
        (most providers, streamed replies, offline fakes, parsed Pydantic
        objects without ``include_raw=True``).
    """
    message = _message_of(output)
    metadata = getattr(message, "response_metadata", None)
    if not isinstance(metadata, Mapping):
        return None
    usage = metadata.get("token_usage")
    if not isinstance(usage, Mapping):
        return None
    values = {}
    for name, key in _SERVER_FIELDS.items():
        raw = usage.get(key)
        values[name] = float(raw) if isinstance(raw, int | float) and not isinstance(raw, bool) else None
    if all(v is None for v in values.values()):
        return None
    return ServerTiming(**values)


# ---------------------------------------------------------------------------
# Timing one call
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Timed:
    """Result of :func:`timed_invoke`: the output plus where the time went.

    Attributes:
        output: Whatever ``invoke`` returned.
        latency_s: Wall-clock seconds of the call itself (rate-limiter wait
            excluded; network, SDK work and SDK retries included).
        waited_s: Seconds spent waiting for the client-side rate limiter.
        server_s: Provider processing time, when reported (Groq: total_time).
        queue_s: Provider queue time, when reported (Groq: queue_time).
    """

    output: Any
    latency_s: float
    waited_s: float = 0.0
    server_s: float | None = None
    queue_s: float | None = None

    @property
    def overhead_s(self) -> float | None:
        """Client time not explained by the provider: network, SDK, retries.

        None when the provider reports no timing. A large value usually means
        a slow network, a retry after an error, or a cold connection. With
        canned replies (offline mocks) it can be negative.
        """
        if self.server_s is None:
            return None
        return self.latency_s - self.server_s - (self.queue_s or 0.0)


def _children(obj: Any) -> list[Any]:
    """Runnables nested inside common LangChain wrappers (duck-typed)."""
    found: list[Any] = []
    for attr in ("bound", "first", "last", "runnable", "default"):
        child = getattr(obj, attr, None)
        if child is not None and hasattr(child, "invoke"):
            found.append(child)
    for attr in ("middle", "fallbacks", "steps"):
        group = getattr(obj, attr, None)
        if isinstance(group, list | tuple):
            found.extend(c for c in group if hasattr(c, "invoke"))
    parallel = getattr(obj, "steps__", None)
    if isinstance(parallel, Mapping):
        found.extend(c for c in parallel.values() if hasattr(c, "invoke"))
    for branch in getattr(obj, "branches", None) or []:
        if isinstance(branch, tuple):
            found.extend(c for c in branch if hasattr(c, "invoke"))
    return found


def attached_rate_limiters(runnable: Any) -> list[Any]:
    """Return the rate limiters attached to chat models inside ``runnable``.

    Looks through bindings (``.bind``, ``.with_structured_output``), sequences,
    parallels, branches and fallbacks.

    Args:
        runnable: A chat model, a chain, or any object with ``invoke``.

    Returns:
        The limiter objects found (empty when none).
    """
    limiters: list[Any] = []
    seen: set[int] = set()
    stack = [runnable]
    while stack:
        obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        limiter = getattr(obj, "rate_limiter", None)
        if limiter is not None and all(limiter is not other for other in limiters):
            limiters.append(limiter)
        stack.extend(_children(obj))
    return limiters


def _warn_if_attached(runnable: Any) -> None:
    if attached_rate_limiters(runnable):
        warnings.warn(
            "A rate limiter is attached to the model, so its waits are timed as model latency. "
            "Build the model without rate_limiter= and pass the limiter to timed_invoke(limiter=...).",
            LimiterInsideTimingWarning,
            stacklevel=3,
        )


def _finish(output: Any, latency_s: float, waited_s: float) -> Timed:
    server = server_timing(output)
    return Timed(
        output=output,
        latency_s=latency_s,
        waited_s=waited_s,
        server_s=server.total_s if server else None,
        queue_s=server.queue_s if server else None,
    )


def timed_invoke(
    runnable: Any,
    input: Any,  # noqa: A002 - same name as Runnable.invoke
    *,
    config: Mapping[str, Any] | None = None,
    limiter: Any = None,
    clock: Clock = time.perf_counter,
    warn_attached_limiter: bool = True,
) -> Timed:
    """Invoke ``runnable`` and time only the call, not your own throttling.

    Step 1 waits for ``limiter`` (if any) with the clock stopped, Step 2 times
    ``runnable.invoke``, Step 3 reads the provider's own timing when present.

    Args:
        runnable: A chat model or chain. Build it WITHOUT ``rate_limiter=``.
        input: The input for ``invoke``.
        config: Optional ``RunnableConfig`` (tags, metadata, callbacks...).
        limiter: A rate limiter such as ``InMemoryRateLimiter`` (share one
            per provider/model across threads). None means no throttling.
        clock: Time source; ``time.perf_counter`` by default (tests pass a fake).
        warn_attached_limiter: Warn with :class:`LimiterInsideTimingWarning`
            if a chat model inside ``runnable`` still has a ``rate_limiter``.

    Returns:
        A :class:`Timed` with the output and the timings.

    Raises:
        Exception: Whatever ``invoke`` raises is re-raised unchanged.
    """
    if warn_attached_limiter:
        _warn_if_attached(runnable)
    waited_s = 0.0
    if limiter is not None:
        before = clock()
        limiter.acquire(blocking=True)
        waited_s = clock() - before
    start = clock()
    output = runnable.invoke(input, config=config)
    return _finish(output, clock() - start, waited_s)


async def atimed_invoke(
    runnable: Any,
    input: Any,  # noqa: A002 - same name as Runnable.ainvoke
    *,
    config: Mapping[str, Any] | None = None,
    limiter: Any = None,
    clock: Clock = time.perf_counter,
    warn_attached_limiter: bool = True,
) -> Timed:
    """Async version of :func:`timed_invoke` (uses ``aacquire`` and ``ainvoke``).

    Args:
        runnable: A chat model or chain. Build it WITHOUT ``rate_limiter=``.
        input: The input for ``ainvoke``.
        config: Optional ``RunnableConfig``.
        limiter: A rate limiter with ``aacquire``, or None.
        clock: Time source.
        warn_attached_limiter: Warn if a model inside still has a limiter.

    Returns:
        A :class:`Timed`.
    """
    if warn_attached_limiter:
        _warn_if_attached(runnable)
    waited_s = 0.0
    if limiter is not None:
        before = clock()
        await limiter.aacquire(blocking=True)
        waited_s = clock() - before
    start = clock()
    output = await runnable.ainvoke(input, config=config)
    return _finish(output, clock() - start, waited_s)


# ---------------------------------------------------------------------------
# Timing a stream
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StreamTimings:
    """When each kind of output first appeared in a stream (seconds from start).

    Attributes:
        first_chunk_s: First chunk of any kind, often empty (role or metadata
            only). This is what naive "time to first token" code measures.
        first_visible_s: First non-empty text OR reasoning: what a UI that
            shows the model's thinking would display first.
        first_answer_s: First non-empty answer text: what users wait for when
            reasoning is hidden.
        total_s: Until the stream ended.
        n_chunks: Number of chunks received.
        waited_s: Seconds spent waiting for the rate limiter (not included above).
        output: The chunks added together (an ``AIMessageChunk`` for chat
            models, a string for string streams), or a list when they
            cannot be added.
    """

    first_chunk_s: float | None
    first_visible_s: float | None
    first_answer_s: float | None
    total_s: float
    n_chunks: int
    waited_s: float = 0.0
    output: Any = None

    def __str__(self) -> str:
        def fmt(value: float | None) -> str:
            return "n/a" if value is None else f"{value:.3f} s"

        return (
            f"first chunk {fmt(self.first_chunk_s)} | first visible {fmt(self.first_visible_s)} | "
            f"first answer {fmt(self.first_answer_s)} | total {fmt(self.total_s)} ({self.n_chunks} chunks)"
        )


def _chunk_kinds(chunk: Any) -> set[str]:
    """Which kinds of visible output a chunk carries: "text" and/or "reasoning"."""
    if isinstance(chunk, str):
        return {"text"} if chunk.strip() else set()
    kinds: set[str] = set()
    try:
        blocks = chunk.content_blocks  # langchain-core 1.x standard blocks
    except Exception:  # noqa: BLE001 - any object may be streamed; fall back below
        blocks = None
    if isinstance(blocks, list):
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            if block.get("type") == "text" and str(block.get("text") or "").strip():
                kinds.add("text")
            elif block.get("type") == "reasoning" and str(block.get("reasoning") or "").strip():
                kinds.add("reasoning")
        return kinds
    content = getattr(chunk, "content", None)
    if isinstance(content, str) and content.strip():
        kinds.add("text")
    extra = getattr(chunk, "additional_kwargs", None) or {}
    if isinstance(extra, Mapping) and str(extra.get("reasoning_content") or "").strip():
        kinds.add("reasoning")
    return kinds


class _StreamRecorder:
    """Shared bookkeeping for the sync and async stream timers."""

    def __init__(self, start: float) -> None:
        self.start = start
        self.first_chunk: float | None = None
        self.first_visible: float | None = None
        self.first_answer: float | None = None
        self.n_chunks = 0
        self.output: Any = None
        self.parts: list[Any] | None = None

    def add(self, chunk: Any, now: float) -> None:
        elapsed = now - self.start
        self.n_chunks += 1
        if self.first_chunk is None:
            self.first_chunk = elapsed
        kinds = _chunk_kinds(chunk)
        if kinds and self.first_visible is None:
            self.first_visible = elapsed
        if "text" in kinds and self.first_answer is None:
            self.first_answer = elapsed
        # Aggregate like LangChain does (chunk + chunk); fall back to a list.
        if self.parts is not None:
            self.parts.append(chunk)
        elif self.output is None:
            self.output = chunk
        else:
            try:
                self.output = self.output + chunk
            except TypeError:
                self.parts = [self.output, chunk]
                self.output = None

    def result(self, now: float, waited_s: float) -> StreamTimings:
        return StreamTimings(
            first_chunk_s=self.first_chunk,
            first_visible_s=self.first_visible,
            first_answer_s=self.first_answer,
            total_s=now - self.start,
            n_chunks=self.n_chunks,
            waited_s=waited_s,
            output=self.parts if self.parts is not None else self.output,
        )


def stream_timings(
    chunks: Iterable[Any],
    *,
    start: float | None = None,
    limiter: Any = None,
    clock: Clock = time.perf_counter,
) -> StreamTimings:
    """Consume a stream and record first chunk, first visible output, first answer.

    Pass the stream object itself: ``stream_timings(model.stream(prompt))``.
    LangChain streams are lazy, so the request starts on the first read,
    after this function has started the clock.

    Args:
        chunks: The stream (``model.stream(...)``, ``chain.stream(...)``).
        start: A ``clock()`` value to measure from; by default the clock starts
            just before the first read (after any limiter wait).
        limiter: Optional rate limiter to wait for before the clock starts.
            Attach no ``rate_limiter`` to the model itself: ``stream`` would
            wait inside the timed window.
        clock: Time source; ``time.perf_counter`` by default.

    Returns:
        A :class:`StreamTimings`. The whole stream is read, so the connection
        is closed cleanly; ``output`` holds the combined message.

    Note:
        Reasoning is detected from standard content blocks (or Groq's
        ``reasoning_content``). With ``reasoning_format="raw"`` the thinking
        arrives as plain text inside ``<think>`` tags and counts as answer text.
    """
    waited_s = 0.0
    if limiter is not None:
        before = clock()
        limiter.acquire(blocking=True)
        waited_s = clock() - before
    recorder = _StreamRecorder(clock() if start is None else start)
    for chunk in chunks:
        recorder.add(chunk, clock())
    return recorder.result(clock(), waited_s)


async def astream_timings(
    chunks: AsyncIterable[Any],
    *,
    start: float | None = None,
    limiter: Any = None,
    clock: Clock = time.perf_counter,
) -> StreamTimings:
    """Async version of :func:`stream_timings` for ``model.astream(...)``.

    Args:
        chunks: The async stream.
        start: A ``clock()`` value to measure from (default: now).
        limiter: Optional rate limiter (``aacquire``) to wait for first.
        clock: Time source.

    Returns:
        A :class:`StreamTimings`.
    """
    waited_s = 0.0
    if limiter is not None:
        before = clock()
        await limiter.aacquire(blocking=True)
        waited_s = clock() - before
    recorder = _StreamRecorder(clock() if start is None else start)
    async for chunk in chunks:
        recorder.add(chunk, clock())
    return recorder.result(clock(), waited_s)


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------


def nearest_rank(values: Iterable[float], q: float) -> float:
    """The ``q``-th percentile by the nearest-rank method.

    Sort the values and take the one at rank ``ceil(q/100 * n)`` (1-based).
    The result is always one of the observed values, never an interpolation,
    which makes it easy to explain: "95% of calls took this long or less".

    Args:
        values: Observations (at least one).
        q: Percentile, ``0 < q <= 100``.

    Returns:
        The observed value at that rank.

    Raises:
        ValueError: If ``values`` is empty or ``q`` is out of range.
    """
    ordered = sorted(float(v) for v in values)
    if not ordered:
        raise ValueError("no values: a percentile needs at least one observation")
    if not 0 < q <= 100:
        raise ValueError(f"q must be in (0, 100], got {q}")
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


@dataclass(frozen=True)
class LatencySummary:
    """Median and tail latency of a set of calls (seconds; None when no data).

    Attributes:
        n: Number of usable values.
        missing: Values dropped because they were None or NaN (for example
            server timing from providers that do not report it).
        p50: Median, nearest-rank.
        p95: 95th percentile, nearest-rank. Equal to ``max`` when ``n < 20``.
        max: Slowest call.
        min: Fastest call.
        mean: Arithmetic mean (pulled up by slow outliers; prefer p50).
    """

    n: int
    missing: int
    p50: float | None
    p95: float | None
    max: float | None
    min: float | None
    mean: float | None

    @property
    def p95_is_max(self) -> bool:
        """True when there are too few values for p95 to differ from the max."""
        return 0 < self.n < P95_MIN_SAMPLES

    def as_dict(self) -> dict[str, Any]:
        """Return the fields as a plain dict (one row of a results table)."""
        return asdict(self)

    def __str__(self) -> str:
        if self.n == 0:
            return f"no latency data (n=0, missing={self.missing})"
        note = f"; with n < {P95_MIN_SAMPLES} the p95 is the max" if self.p95_is_max else ""
        missing = f", {self.missing} missing" if self.missing else ""
        return f"p50 {self.p50:.3f} s | p95 {self.p95:.3f} s | max {self.max:.3f} s (n={self.n}{missing}{note})"


def latency_summary(values: Iterable[float | None]) -> LatencySummary:
    """Summarize latencies with the median and the 95th percentile.

    Uses the nearest-rank method (see :func:`nearest_rank`): with 5 values the
    p50 is the 3rd fastest and the p95 the slowest. None and NaN values are
    skipped and counted in ``missing``, so a column of server timings with
    gaps can be summarized directly.

    Args:
        values: Latencies in seconds (None/NaN allowed).

    Returns:
        A :class:`LatencySummary`. With no usable values every statistic is
        None and ``n`` is 0.

    Example:
        >>> s = latency_summary([1, 2, 3, 4, 100])
        >>> (s.p50, s.p95, s.mean)
        (3.0, 100.0, 22.0)
    """
    usable: list[float] = []
    missing = 0
    for value in values:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            missing += 1
        else:
            usable.append(float(value))
    if not usable:
        return LatencySummary(0, missing, None, None, None, None, None)
    return LatencySummary(
        n=len(usable),
        missing=missing,
        p50=nearest_rank(usable, 50),
        p95=nearest_rank(usable, 95),
        max=max(usable),
        min=min(usable),
        mean=sum(usable) / len(usable),
    )
