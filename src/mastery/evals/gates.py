"""Eval gates for CI (introduced in Lesson 10.03, used by Lesson 10.08 and Project 10).

A gate turns eval results into a yes/no a CI job can enforce:

- :func:`pass_rate_gate`: the **lower bound** of the pass rate's 95% interval must clear
  the threshold (a lucky run can't sneak a regression through; a point estimate could).
- :func:`redteam_gate`: every attack the baseline blocked must still be blocked.
- :func:`cost_gate`: cost (or calls/tokens) per run must stay within budget.

:class:`GateReport` collects them, prints a Markdown summary for the CI log and gives an
exit code (0 = all gates passed).

Example:
    >>> report = GateReport([pass_rate_gate("desk", 55, 60, min_lower_bound=0.8), cost_gate("calls", 3.1, 4)])
    >>> report.passed, report.exit_code()
    (True, 0)
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from mastery.evals.stats import Interval, RepeatSummary, wilson_interval

__all__ = ["GateReport", "GateResult", "cost_gate", "pass_rate_gate", "redteam_gate", "summary_gate"]


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    detail: str

    def __str__(self) -> str:
        return f"{'✅' if self.passed else '❌'} {self.name}: {self.detail}"


def _interval_gate(name: str, interval: Interval, min_lower_bound: float) -> GateResult:
    ok = interval.low >= min_lower_bound
    return GateResult(name, ok, f"{interval:.1%}; lower bound {'≥' if ok else '<'} {min_lower_bound:.0%}")


def pass_rate_gate(name: str, successes: int, n: int, *, min_lower_bound: float) -> GateResult:
    """Pass when the Wilson lower bound of ``successes / n`` is at least ``min_lower_bound``."""
    return _interval_gate(name, wilson_interval(successes, n), min_lower_bound)


def summary_gate(name: str, summary: RepeatSummary, *, min_lower_bound: float) -> GateResult:
    """Same rule on repeated runs (``summarize_repeats``): uses the cluster-bootstrap interval."""
    return _interval_gate(name, summary.mean, min_lower_bound)


def redteam_gate(name: str, blocked: Mapping[str, bool], baseline: Mapping[str, bool] | None = None) -> GateResult:
    """Fail if an attack is not blocked (``blocked[id] = True`` means it was stopped).

    With ``baseline``, only regressions fail (blocked before, not now), so a red-team
    suite can contain known, documented gaps; without it, every attack must be blocked.
    Missing ids count as not blocked: deleting a test never makes the gate greener.
    """
    ids = sorted(set(blocked) | set(baseline or {}))
    if baseline is None:
        failing = [i for i in ids if not blocked.get(i, False)]
    else:
        failing = [i for i in ids if baseline.get(i, False) and not blocked.get(i, False)]
    held = sum(bool(blocked.get(i, False)) for i in ids)
    detail = f"{held}/{len(ids)} attacks blocked" + (f"; regressed: {failing[:5]}" if failing else "")
    return GateResult(name, not failing, detail)


def cost_gate(name: str, value: float, budget: float, *, unit: str = "") -> GateResult:
    """Pass when ``value`` (cost, calls or tokens per run) is at most ``budget``."""
    ok = value <= budget
    return GateResult(name, ok, f"{value:g}{unit} per run vs budget {budget:g}{unit}")


@dataclass
class GateReport:
    results: list[GateResult] = field(default_factory=list)

    def add(self, *results: GateResult) -> GateReport:
        self.results.extend(results)
        return self

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(r.passed for r in self.results)

    def exit_code(self) -> int:
        return 0 if self.passed else 1

    def to_markdown(self) -> str:
        lines = ["| Gate | Result | Detail |", "|---|---|---|"]
        lines += [f"| {r.name} | {'✅ pass' if r.passed else '❌ fail'} | {r.detail} |" for r in self.results]
        verdict = "✅ all gates passed" if self.passed else "❌ blocked by: " + ", ".join(r.name for r in self.results if not r.passed)
        return "\n".join([*lines, "", verdict])

    def __iter__(self) -> Iterable[GateResult]:
        return iter(self.results)
