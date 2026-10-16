"""Latency and cost budgets, and a spend ledger that enforces them before a run starts (Lesson 12.01).

A budget is a design input: write it before building, then measure against it. The latency budget
splits the SLO ("first token within 3 s") across stages so each owner knows their share. The cost
budget caps spend per request, per user per day and for the whole service per day; the ledger
checks the estimate **before** the run (so a run that can't be paid for never starts), then
records the actual cost after it.

The in-memory ledger is a teaching shortcut: Lesson 12.05 moves it to Postgres so it survives
restarts and works across replicas.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from mastery.pricing import estimate_cost

__all__ = ["BudgetDecision", "CostBudget", "LatencyBudget", "SpendLedger", "estimate_request_cost"]


@dataclass(frozen=True)
class LatencyBudget:
    """Seconds allowed per stage. ``total`` must fit inside the SLO threshold it serves."""

    stages: Mapping[str, float]

    @property
    def total(self) -> float:
        return sum(self.stages.values())

    def check(self, measured: Mapping[str, float]) -> list[dict[str, object]]:
        """Rows ``stage, budget_s, measured_s, ok`` for a table (``measured`` = e.g. p95 per stage)."""
        return [{"stage": s, "budget_s": b, "measured_s": round(measured.get(s, float("nan")), 3),
                 "ok": measured.get(s, float("inf")) <= b} for s, b in self.stages.items()]


def estimate_request_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """List-price USD for one request (``mastery.pricing``); raises if the model has no price."""
    cost = estimate_cost({"input_tokens": input_tokens, "output_tokens": output_tokens}, model)
    if cost is None:
        raise KeyError(f"no price for {model!r} in mastery.pricing")
    return cost


@dataclass(frozen=True)
class CostBudget:
    """USD caps: per request, per user per day, and for the whole service per day (the kill switch)."""

    per_request: float
    per_user_day: float
    global_day: float


@dataclass(frozen=True)
class BudgetDecision:
    """Whether a run may start, and why not."""

    allowed: bool
    reason: str
    user_left: float
    global_left: float


class SpendLedger:
    """Spend per (day, user), checked before a run and charged after it."""

    def __init__(self, budget: CostBudget) -> None:
        self.budget = budget
        self._spent: dict[tuple[str, str], float] = defaultdict(float)

    def spent(self, day: str, user: str | None = None) -> float:
        """Spend of ``user`` on ``day``, or of everyone when ``user`` is None."""
        if user is not None:
            return self._spent[(day, user)]
        return sum(v for (d, _), v in self._spent.items() if d == day)

    def check(self, day: str, user: str, estimate: float) -> BudgetDecision:
        """Decide before the run. Order matters: the global cap protects the bill even if one user is fine."""
        user_left = self.budget.per_user_day - self.spent(day, user)
        global_left = self.budget.global_day - self.spent(day)
        if estimate > self.budget.per_request:
            return BudgetDecision(False, f"request estimate ${estimate:.4f} > per-request cap ${self.budget.per_request:.4f}",
                                  user_left, global_left)
        if estimate > global_left:
            return BudgetDecision(False, "global daily cap reached (kill switch)", user_left, global_left)
        if estimate > user_left:
            return BudgetDecision(False, "user's daily budget used up", user_left, global_left)
        return BudgetDecision(True, "ok", user_left, global_left)

    def charge(self, day: str, user: str, cost: float) -> None:
        """Record the ACTUAL cost after the run (it can exceed the estimate: that's why caps have headroom)."""
        self._spent[(day, user)] += cost

    def top_users(self, day: str, n: int = 5) -> Sequence[tuple[str, float]]:
        rows = [(u, v) for (d, u), v in self._spent.items() if d == day]
        return sorted(rows, key=lambda kv: -kv[1])[:n]
