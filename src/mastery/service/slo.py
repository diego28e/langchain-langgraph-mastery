"""Service-level indicators, objectives and error budgets for agent runs (Lesson 12.01).

An SLI is a ratio of good events to eligible events ("runs that started streaming within 3 s"
out of "runs that started"). An SLO is a target for that ratio over a window ("99% over 28 days").
The error budget is what the target allows to go wrong: ``(1 - target) * eligible`` events.

Every ratio is reported with a Wilson interval (course rule §11): 500 runs can't tell 99.0% from 99.4%.

``synthetic_runs`` generates **simulated** traffic so the math can be learned before the service
exists; Lesson 12.07 computes the same SLIs from the records the service writes.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from mastery.evals.stats import Interval, wilson_interval

__all__ = ["SLO", "RunRecord", "SLOResult", "burn_rate", "default_slos", "error_budget_policy", "evaluate_slo",
           "percentile", "synthetic_runs"]

STATUSES = ("ok", "error", "cancelled", "rejected")


@dataclass(frozen=True)
class RunRecord:
    """One agent run as the service sees it.

    Attributes:
        run_id: Unique id.
        user_id: Who started it (for per-user budgets).
        started_at: Seconds since the start of the window.
        status: ``ok``, ``error`` (the service failed), ``cancelled`` (the user stopped it) or
            ``rejected`` (refused before starting: quota, auth, busy thread).
        ttft_s: Seconds until the first streamed event (``None`` if nothing was streamed).
        duration_s: Seconds from start to the final event.
        cost_usd: Model cost of the run.
        stages: Seconds spent per stage (queue, model, tools, ...), for latency budgets.
    """

    run_id: str
    user_id: str
    started_at: float
    status: str
    ttft_s: float | None
    duration_s: float
    cost_usd: float = 0.0
    stages: dict[str, float] = field(default_factory=dict)


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile (``q`` in 0–100): the value at least ``q``% of samples are at or below.

    Nearest-rank always returns a value that was observed, which is what an SLO statement means
    ("p95 = 41 s" means one real run took 41 s).
    """
    data = sorted(v for v in values if v is not None)
    if not data:
        raise ValueError("percentile of an empty sample")
    if not 0 < q <= 100:
        raise ValueError(f"q must be in (0, 100], got {q}")
    return data[max(0, math.ceil(q / 100 * len(data)) - 1)]


@dataclass(frozen=True)
class SLO:
    """A service-level objective.

    Attributes:
        name: Short id, e.g. ``ttft``.
        description: The sentence you would put in the README.
        target: Objective for the good/eligible ratio, e.g. ``0.99``.
        good: ``f(run) -> True`` (good), ``False`` (bad) or ``None`` (not eligible: excluded from both counts).
    """

    name: str
    description: str
    target: float
    good: Callable[[RunRecord], bool | None]


@dataclass(frozen=True)
class SLOResult:
    """An SLO measured on a set of runs."""

    name: str
    target: float
    good: int
    eligible: int
    interval: Interval
    budget_total: float
    budget_used: int

    @property
    def ratio(self) -> float:
        return self.good / self.eligible

    @property
    def met(self) -> bool:
        """Point estimate at or above target. Read ``interval`` before celebrating."""
        return self.ratio >= self.target

    @property
    def budget_remaining(self) -> float:
        """Fraction of the error budget left (negative when overspent)."""
        return 1.0 - self.budget_used / self.budget_total if self.budget_total else (1.0 if not self.budget_used else -math.inf)


def evaluate_slo(slo: SLO, runs: Sequence[RunRecord]) -> SLOResult:
    """Count good and eligible runs for ``slo`` and size its error budget."""
    verdicts = [v for v in (slo.good(r) for r in runs) if v is not None]
    if not verdicts:
        raise ValueError(f"no eligible runs for SLO {slo.name!r}")
    good = sum(verdicts)
    eligible = len(verdicts)
    return SLOResult(slo.name, slo.target, good, eligible, wilson_interval(good, eligible),
                     budget_total=round((1 - slo.target) * eligible, 9), budget_used=eligible - good)


def default_slos(ttft_s: float = 3.0, duration_s: float = 60.0) -> list[SLO]:
    """The three SLOs the course service promises (Lesson 12.01). Rejected runs count only for availability."""
    started = lambda r: r.status != "rejected"  # noqa: E731
    return [
        SLO("availability", "99% of accepted runs finish without a service error (cancelled by the user counts as fine)",
            0.99, lambda r: (r.status != "error") if started(r) else None),
        SLO("ttft", f"99% of runs start streaming within {ttft_s:g} s", 0.99,
            lambda r: (r.ttft_s is not None and r.ttft_s <= ttft_s) if started(r) else None),
        SLO("duration", f"95% of successful runs finish within {duration_s:g} s", 0.95,
            lambda r: (r.duration_s <= duration_s) if r.status == "ok" else None),
    ]


def burn_rate(slo: SLO, runs: Sequence[RunRecord], *, since: float) -> float:
    """How fast the budget burns in a recent window: bad-ratio / allowed-bad-ratio.

    1.0 spends the budget exactly over the SLO window; 14.4 over one hour spends 2% of a 30-day
    budget (the SRE workbook's fast-burn page). Returns 0.0 when the window has no eligible runs.
    """
    recent = [r for r in runs if r.started_at >= since]
    verdicts = [v for v in (slo.good(r) for r in recent) if v is not None]
    if not verdicts:
        return 0.0
    bad_ratio = 1 - sum(verdicts) / len(verdicts)
    return bad_ratio / (1 - slo.target)


def error_budget_policy(result: SLOResult) -> str:
    """The written policy: what the team does at each budget level (Lesson 12.01, Part 3)."""
    left = result.budget_remaining
    if left > 0.5:
        return "normal: ship features"
    if left > 0:
        return "caution: only low-risk releases, prioritise reliability fixes"
    return "freeze: no feature releases until the SLO is back; fix the top cause first"


def synthetic_runs(n: int = 500, *, seed: int = 12, users: int = 25, incident: bool = False,
                   window_s: float = 7 * 24 * 3600, model: str = "openai/gpt-oss-20b") -> list[RunRecord]:
    """SIMULATED traffic for the support desk: realistic shapes, not real measurements.

    Stage times: queue (usually ~0, sometimes seconds under load), model time-to-first-token
    (log-normal around 0.6 s), tool calls (0–3 lookups), streaming of the answer. About 1% of runs
    error, 2% are cancelled and 1% are rejected by quotas. With ``incident=True`` the last 10% of
    the window has a provider slowdown: TTFT ×6 and 8% errors. Costs use ``model``'s list price.
    """
    from mastery.service.budgets import estimate_request_cost

    rng = random.Random(seed)
    runs: list[RunRecord] = []
    for i in range(n):
        t = window_s * i / n
        in_incident = incident and t >= 0.9 * window_s
        user = f"u{rng.randrange(users):02d}"
        roll = rng.random()
        if roll < 0.01:
            runs.append(RunRecord(f"r{i:04d}", user, t, "rejected", None, 0.0))
            continue
        queue = rng.expovariate(1 / 0.05) if rng.random() < 0.95 else rng.uniform(1.0, 4.0)
        ttft_model = rng.lognormvariate(math.log(0.6), 0.45) * (6 if in_incident else 1)
        tools = sum(rng.uniform(0.15, 0.6) for _ in range(rng.choice((0, 1, 1, 2, 3))))
        stream = rng.uniform(1.0, 6.0) + (rng.uniform(20, 70) if rng.random() < 0.04 else 0.0)
        stages = {"queue": queue, "model_ttft": ttft_model, "tools": tools, "stream": stream}
        error_p = 0.08 if in_incident else 0.01
        roll = rng.random()
        status = "error" if roll < error_p else "cancelled" if roll < error_p + 0.02 else "ok"
        tokens_in = rng.randint(1200, 4200)
        tokens_out = rng.randint(80, 600)
        cost = estimate_request_cost(model, tokens_in, tokens_out)
        runs.append(RunRecord(f"r{i:04d}", user, t, status, queue + ttft_model, sum(stages.values()),
                              round(cost, 8), {k: round(v, 3) for k, v in stages.items()}))
    return runs
