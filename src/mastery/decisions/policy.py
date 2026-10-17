"""Turn Jev's probabilities into actions: confidence measures, calibration scores, cost-based thresholds.

Introduced in Lesson 15.02. Calibration *tables* and ECE live in :mod:`mastery.finetune.metrics`
(Module 14) and are reused here; this module adds what is specific to decision answers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

__all__ = ["Band", "BandCosts", "apply_band", "band_cost", "brier_score", "choose_band", "margin", "top_probability"]


def top_probability(answer: Any) -> float:
    """Probability of the selected label of a ``ChoiceAnswer``: the number to calibrate against accuracy."""
    return max(answer.probabilities.values())


def margin(answer: Any) -> float:
    """Top probability minus the runner-up: small when two labels compete (Lesson 15.01's T5)."""
    top = sorted(answer.probabilities.values(), reverse=True)
    return top[0] - (top[1] if len(top) > 1 else 0.0)


def brier_score(probabilities: Sequence[float], labels: Sequence[int]) -> float:
    """Mean squared error of yes-probabilities against 0/1 labels (0 = perfect, 0.25 = always saying 0.5)."""
    return round(sum((p - y) ** 2 for p, y in zip(probabilities, labels)) / len(labels), 4)


@dataclass(frozen=True)
class BandCosts:
    """What each outcome of a yes/no automation costs (any one unit: minutes, dollars, points)."""

    false_yes: float      # acted when the answer was no (e.g. paged on-call for nothing)
    false_no: float       # did nothing when the answer was yes (e.g. missed an outage)
    review: float         # sent to a human instead of deciding


@dataclass(frozen=True)
class Band:
    low: float            # p < low  → "no"
    high: float           # p ≥ high → "yes"; in between → "review"
    cost: float
    reviewed: int
    errors: int


def apply_band(p: float, low: float, high: float) -> str:
    """``"yes"`` if ``p ≥ high``, ``"no"`` if ``p < low``, else ``"review"`` (the uncertain band)."""
    return "yes" if p >= high else ("no" if p < low else "review")


def band_cost(probabilities: Sequence[float], labels: Sequence[int], low: float, high: float, costs: BandCosts) -> Band:
    cost, reviewed, errors = 0.0, 0, 0
    for p, y in zip(probabilities, labels):
        action = apply_band(p, low, high)
        if action == "review":
            cost += costs.review
            reviewed += 1
        elif (action == "yes") != bool(y):
            cost += costs.false_yes if action == "yes" else costs.false_no
            errors += 1
    return Band(low, high, round(cost, 4), reviewed, errors)


def choose_band(probabilities: Sequence[float], labels: Sequence[int], costs: BandCosts,
                grid: Sequence[float] | None = None) -> Band:
    """Cheapest ``(low, high)`` on a grid (``low ≤ high``; ``low == high`` = a single cutoff, no review).

    Ties go to the band that reviews fewer items. Choose on one half of your data, report on the other.
    """
    grid = grid if grid is not None else [round(i / 20, 2) for i in range(1, 20)]
    bands = [band_cost(probabilities, labels, lo, hi, costs) for lo in grid for hi in grid if lo <= hi]
    return min(bands, key=lambda b: (b.cost, b.reviewed, -b.high))
