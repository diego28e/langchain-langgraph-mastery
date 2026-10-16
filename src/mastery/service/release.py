"""Safe releases for the agent service: shadow comparison, canary decisions, rollback criteria (Lesson 12.09).

A release changes code, prompt, model or config. Before all users get it:

* **shadow**: replay the same inputs through the stable and the candidate version, compare outcomes
  (no user sees the candidate's answers): :func:`shadow_compare`;
* **canary**: send a small, sticky share of users to the candidate (:class:`CanaryRouter`) and compare
  its SLIs with the stable version's: :func:`canary_decision` says promote, hold or roll back;
* **rollback criteria** are written *before* the release (:class:`RollbackCriteria`), so nobody argues
  about them at 2 a.m.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from mastery.service.slo import RunRecord, default_slos, evaluate_slo

__all__ = ["CanaryDecision", "CanaryRouter", "RollbackCriteria", "canary_decision", "shadow_compare"]


@dataclass(frozen=True)
class CanaryRouter:
    """Send ``weight`` (0..1) of users to the canary, the same users every time (hash of user and salt).

    Sticky routing matters for agents: a conversation that switches versions mid-thread mixes two
    prompts in one checkpoint. Change ``salt`` to pick a different slice of users for the next release.
    """

    weight: float
    salt: str = "canary"

    def __post_init__(self) -> None:
        if not 0 <= self.weight <= 1:
            raise ValueError("weight must be between 0 and 1")

    def route(self, user_id: str) -> str:
        digest = hashlib.sha256(f"{self.salt}:{user_id}".encode()).digest()
        bucket = int.from_bytes(digest[:8], "big") / 2**64
        return "canary" if bucket < self.weight else "stable"


@dataclass(frozen=True)
class RollbackCriteria:
    """Written before the release. Any breach rolls back; fewer than ``min_runs`` canary runs holds.

    An SLI breaches only when we are *confident* it is worse: the top of the canary's 95% interval is
    below both the target and stable's ratio minus ``max_sli_drop``. One error in 60 canary runs is
    noise; 15 errors are not. ``max_cost_ratio`` caps the canary's mean cost per run relative to stable
    (a prompt that doubles tokens is a regression too).
    """

    min_runs: int = 50
    max_sli_drop: float = 0.01
    max_cost_ratio: float = 1.5
    slos: Sequence[Any] = field(default_factory=default_slos)


@dataclass(frozen=True)
class CanaryDecision:
    action: str                      # "promote", "hold" or "rollback"
    reasons: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]


def canary_decision(stable: Sequence[RunRecord], canary: Sequence[RunRecord],
                    criteria: RollbackCriteria | None = None) -> CanaryDecision:
    """Compare the canary's SLIs and cost with stable's under ``criteria``."""
    criteria = criteria or RollbackCriteria()
    rows, breaches = [], []
    for slo in criteria.slos:
        s, c = evaluate_slo(slo, stable), evaluate_slo(slo, canary)
        breached = c.interval.high < min(slo.target, s.ratio - criteria.max_sli_drop)
        rows.append({"sli": slo.name, "stable": round(s.ratio, 4), "canary": round(c.ratio, 4),
                     "canary_high": round(c.interval.high, 4), "target": slo.target, "breach": breached})
        if breached:
            breaches.append(f"{slo.name}: canary {c.ratio:.3f} (at most {c.interval.high:.3f}) vs stable {s.ratio:.3f}")
    mean = lambda runs: sum(r.cost_usd for r in runs) / max(1, len(runs))  # noqa: E731
    ratio = mean(canary) / mean(stable) if mean(stable) else 1.0
    rows.append({"sli": "cost/run", "stable": round(mean(stable), 6), "canary": round(mean(canary), 6),
                 "target": f"≤ {criteria.max_cost_ratio}× stable", "breach": ratio > criteria.max_cost_ratio})
    if ratio > criteria.max_cost_ratio:
        breaches.append(f"cost: canary {ratio:.2f}× stable")
    if breaches:
        return CanaryDecision("rollback", tuple(breaches), tuple(rows))
    if len(canary) < criteria.min_runs:
        return CanaryDecision("hold", (f"only {len(canary)} canary runs; need {criteria.min_runs}",), tuple(rows))
    return CanaryDecision("promote", ("no criterion breached",), tuple(rows))


def shadow_compare(stable: Any, candidate: Any, cases: Sequence[dict[str, Any]], *,
                   attacks: Sequence[dict[str, Any]] = (), model_for: Any = None) -> dict[str, Any]:
    """Replay ``cases`` (and ``attacks``) through two desk versions (``release_suite.Candidate``).

    Returns counts (``both_pass``, ``regressions``, ``fixes``, ``both_fail``), the regressed cases, and
    ``newly_unblocked``: attacks stable blocked and the candidate lets through. Shadow traffic must not
    have side effects: each version gets its own fake backend.
    """
    from mastery.agents.release_suite import run_suite

    ra = run_suite(stable, cases, redteam=attacks, model_for=model_for)
    rb = run_suite(candidate, cases, redteam=attacks, model_for=model_for)
    a, b = ra["runs"][0], rb["runs"][0]
    unblocked = sorted(i for i, ok in ra["redteam"].items() if ok and not rb["redteam"].get(i, False))
    counts = {"both_pass": 0, "regressions": 0, "fixes": 0, "both_fail": 0}
    regressed = []
    for case_id, old in a.items():
        new = b[case_id]
        key = {(True, True): "both_pass", (True, False): "regressions",
               (False, True): "fixes", (False, False): "both_fail"}[(old["passed"], new["passed"])]
        counts[key] += 1
        if key == "regressions":
            regressed.append({"id": case_id, "input": old["input"][:80], "stable": old["label"], "candidate": new["label"]})
    return {"cases": len(a), **counts, "attacks": len(ra["redteam"]), "newly_unblocked": unblocked,
            "regressed": regressed, "ship": counts["regressions"] == 0 and not unblocked}
