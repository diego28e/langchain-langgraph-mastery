"""Classifier metrics for the ticket router: accuracy with a CI, macro-F1, confusion, calibration, routing cost.

Accuracy intervals come from :func:`mastery.evals.stats.wilson_interval` (Module 10); paired comparisons
between two routers use :func:`mastery.evals.stats.paired_compare` directly on per-ticket 0/1 scores.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from mastery.evals.stats import Interval, wilson_interval

__all__ = ["accuracy", "macro_f1", "confusion", "top_confusions", "calibration", "expected_calibration_error",
           "RoutePoint", "route_curve", "best_threshold", "correct_map"]


def correct_map(predicted: Mapping[str, str], gold: Mapping[str, str]) -> dict[str, int]:
    """``{id: 1 if right else 0}`` for every id in ``gold`` (a missing prediction counts as wrong)."""
    return {i: int(predicted.get(i) == g) for i, g in gold.items()}


def accuracy(predicted: Mapping[str, str], gold: Mapping[str, str]) -> Interval:
    right = sum(correct_map(predicted, gold).values())
    return wilson_interval(right, len(gold))


def macro_f1(predicted: Mapping[str, str], gold: Mapping[str, str], labels: Sequence[str]) -> float:
    """Mean per-class F1: every queue counts the same, however many tickets it has."""
    scores = []
    for lab in labels:
        tp = sum(1 for i, g in gold.items() if g == lab and predicted.get(i) == lab)
        fp = sum(1 for i, g in gold.items() if g != lab and predicted.get(i) == lab)
        fn = sum(1 for i, g in gold.items() if g == lab and predicted.get(i) != lab)
        scores.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(scores) / len(scores)


def confusion(predicted: Mapping[str, str], gold: Mapping[str, str], labels: Sequence[str]) -> dict[str, dict[str, int]]:
    """``m[gold][predicted]`` counts; predictions outside ``labels`` go to ``"other"``."""
    m = {g: {p: 0 for p in [*labels, "other"]} for g in labels}
    for i, g in gold.items():
        p = predicted.get(i)
        m[g][p if p in labels else "other"] += 1
    return m


def top_confusions(predicted: Mapping[str, str], gold: Mapping[str, str], k: int = 5) -> list[tuple[str, str, int]]:
    """The ``k`` most frequent ``(gold, predicted, count)`` mistakes."""
    pairs: dict[tuple[str, str], int] = {}
    for i, g in gold.items():
        p = predicted.get(i, "missing")
        if p != g:
            pairs[(g, p)] = pairs.get((g, p), 0) + 1
    return [(g, p, n) for (g, p), n in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]


def calibration(confidence: Sequence[float], correct: Sequence[int], bins: int = 5) -> list[dict[str, float]]:
    """Reliability table: per confidence bin, how many tickets, mean confidence, actual accuracy."""
    rows = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(confidence) if lo <= c < hi or (b == bins - 1 and c == 1.0)]
        if idx:
            rows.append({"bin": f"{lo:.1f}–{hi:.1f}", "n": len(idx),
                         "confidence": round(sum(confidence[i] for i in idx) / len(idx), 3),
                         "accuracy": round(sum(correct[i] for i in idx) / len(idx), 3)})
    return rows


def expected_calibration_error(confidence: Sequence[float], correct: Sequence[int], bins: int = 10) -> float:
    """Weighted mean gap between confidence and accuracy over ``bins`` (0 = perfectly calibrated)."""
    n = len(confidence)
    return round(sum(r["n"] / n * abs(r["confidence"] - r["accuracy"]) for r in calibration(confidence, correct, bins)), 4)


@dataclass(frozen=True)
class RoutePoint:
    """One threshold of a local-first router: keep tickets with confidence ≥ ``threshold``, escalate the rest."""

    threshold: float
    kept: int
    escalated: int
    accuracy: float           # overall, after escalation
    cost: float               # total cost of the policy on this set
    cost_per_ticket: float


def route_curve(confidence: Sequence[float], local_correct: Sequence[int], escalated_correct: Sequence[int], *,
                cost_wrong: float, cost_escalate: float, thresholds: Sequence[float] | None = None) -> list[RoutePoint]:
    """Cost and accuracy of "local if confident, else the big model" for each threshold.

    ``cost_wrong``: what a misrouted ticket costs (an agent re-routing it, a slower answer); ``cost_escalate``:
    what one call to the big model costs (tokens, latency, data leaving the machine). Same units for both.
    """
    n = len(confidence)
    thresholds = thresholds if thresholds is not None else [round(t / 20, 2) for t in range(0, 21)]
    out = []
    for t in thresholds:
        keep = [c >= t for c in confidence]
        right = sum(lc if k else ec for k, lc, ec in zip(keep, local_correct, escalated_correct))
        esc = n - sum(keep)
        cost = (n - right) * cost_wrong + esc * cost_escalate
        out.append(RoutePoint(t, n - esc, esc, round(right / n, 4), round(cost, 4), round(cost / n, 4)))
    return out


def best_threshold(points: Sequence[RoutePoint]) -> RoutePoint:
    """Cheapest policy (ties → the one that escalates less)."""
    return min(points, key=lambda p: (p.cost, p.escalated))
