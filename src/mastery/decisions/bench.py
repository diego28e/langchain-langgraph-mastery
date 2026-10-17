"""Lesson 15.07: a small, honest latency and cost benchmark for decision calls.

:func:`benchmark` times one callable over inputs (after warm-up) and reports p50 / p95 / mean in ms,
plus cost per 1,000 decisions from a ``cost_of(result)`` function. :func:`monthly_cost` projects that
to traffic volumes. Replayed calls measure only client overhead: label them, never quote them as Jev's latency.
"""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile (q in 0..100) of a non-empty sequence."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    rank = max(1, min(len(ordered), round(q / 100 * len(ordered) + 0.5)))
    return ordered[rank - 1]


@dataclass(frozen=True)
class BenchResult:
    name: str
    n: int
    p50_ms: float
    p95_ms: float
    mean_ms: float
    usd_per_1k: float | None
    source: str = ""

    def row(self) -> dict[str, Any]:
        cost = "n/a" if self.usd_per_1k is None else f"{self.usd_per_1k:.4f}"
        return {"setup": self.name, "n": self.n, "p50 ms": f"{self.p50_ms:.1f}", "p95 ms": f"{self.p95_ms:.1f}",
                "mean ms": f"{self.mean_ms:.1f}", "$ per 1k": cost, "source": self.source}


def benchmark(name: str, fn: Callable[[Any], Any], inputs: Iterable[Any], *, warmup: int = 1,
              cost_of: Callable[[Any], float | None] | None = None, source: str = "",
              clock: Callable[[], float] = time.perf_counter) -> BenchResult:
    """Call ``fn`` on each input once (after ``warmup`` untimed calls on the first input)."""
    items = list(inputs)
    if not items:
        raise ValueError("benchmark needs at least one input")
    for _ in range(warmup):
        fn(items[0])
    times, costs = [], []
    for item in items:
        start = clock()
        result = fn(item)
        times.append((clock() - start) * 1000)
        if cost_of is not None:
            costs.append(cost_of(result))
    known = [c for c in costs if c is not None]
    usd = (sum(known) / len(known) * 1000) if known else None
    return BenchResult(name, len(items), percentile(times, 50), percentile(times, 95), statistics.fmean(times), usd, source)


def monthly_cost(usd_per_1k: float, decisions_per_day: float, days: int = 30) -> float:
    return usd_per_1k * decisions_per_day / 1000 * days


def llm_cost_per_1k(model: str, input_tokens: float, output_tokens: float) -> float | None:
    """Paid-tier USD per 1,000 calls of an LLM from :mod:`mastery.pricing` (None if unpriced)."""
    from mastery.pricing import estimate_cost

    one = estimate_cost({"input_tokens": input_tokens, "output_tokens": output_tokens}, model)
    return None if one is None else one * 1000
