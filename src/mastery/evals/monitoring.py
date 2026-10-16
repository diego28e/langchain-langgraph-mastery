"""Online monitoring helpers (Lesson 10.06): sampling, judge budgets, feedback, review queues, alerts.

Everything works offline. The shapes match LangSmith's: :func:`feedback_payload` returns the
keyword arguments of ``Client.create_feedback``; :class:`ReviewQueue` mirrors an annotation
queue (runs in, labels out) and turns labelled items into dataset examples, which closes the
loop back to Lesson 10.01's taxonomy and Lesson 10.03's datasets.

Example:
    >>> sample_size(0.05, p=0.1)
    139
    >>> should_sample("run-1", 1.0)
    True
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from mastery.evals.stats import Interval, wilson_interval

__all__ = ["ReviewQueue", "feedback_payload", "judge_budget", "rate_alert", "sample_size", "should_sample"]

_Z95 = 1.959963984540054


def sample_size(margin: float, *, p: float = 0.5, confidence_z: float = _Z95) -> int:
    """Traces to judge for a ±``margin`` 95% interval on a rate near ``p`` (normal approximation)."""
    if not 0 < margin < 1:
        raise ValueError("margin must be between 0 and 1")
    return math.ceil(confidence_z ** 2 * p * (1 - p) / margin ** 2)


def should_sample(trace_id: str, rate: float, *, salt: str = "online") -> bool:
    """Deterministic sampling by id: the same trace is always in (or out), on every worker."""
    if rate >= 1:
        return True
    digest = hashlib.sha256(f"{salt}:{trace_id}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF < rate


def judge_budget(traces_per_day: float, sample_rate: float, *, judges: int = 1, tokens_per_call: float = 1500,
                 usd_per_million_tokens: float = 0.10) -> dict[str, float]:
    """Daily calls, tokens and dollars of online judges at a sampling rate."""
    calls = traces_per_day * sample_rate * judges
    tokens = calls * tokens_per_call
    return {"judged_per_day": round(traces_per_day * sample_rate, 1), "calls": round(calls, 1),
            "tokens": round(tokens), "usd": round(tokens / 1e6 * usd_per_million_tokens, 4)}


def feedback_payload(run_id: str, key: str, score: float | bool, *, comment: str = "",
                     source: str = "model", extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Keyword arguments for ``Client().create_feedback(**payload)``.

    ``source`` is who gave it: ``"model"`` (an online judge), ``"user"`` (thumbs up/down in the
    app) or ``"human"`` (a reviewer in a queue). It lands in ``source_info`` for filtering.
    """
    return {"run_id": run_id, "key": key, "score": float(score), "comment": comment or None,
            "source_info": {"source": source, **dict(extra or {})}}


def rate_alert(flags: Sequence[bool], baseline_rate: float) -> tuple[bool, Interval]:
    """Alert when the failure rate's LOWER bound is above the baseline: worse beyond noise."""
    interval = wilson_interval(sum(map(bool, flags)), len(flags))
    return interval.low > baseline_rate, interval


@dataclass
class ReviewQueue:
    """An annotation queue, offline: runs go in with a reason, a person labels them, examples come out."""

    name: str
    items: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, record: Mapping[str, Any], reason: str) -> None:
        """Queue a trace once (re-adding the same id keeps the first reason)."""
        self.items.setdefault(str(record["id"]), {"record": dict(record), "reason": reason, "label": None, "note": ""})

    def pending(self) -> list[dict[str, Any]]:
        return [i for i in self.items.values() if i["label"] is None]

    def label(self, trace_id: str, label: str, note: str = "") -> None:
        if trace_id not in self.items:
            raise KeyError(f"{trace_id} is not in queue {self.name!r}")
        self.items[trace_id].update(label=label, note=note)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for item in self.items.values():
            key = item["label"] or "unlabelled"
            out[key] = out.get(key, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    def to_examples(self) -> list[dict[str, Any]]:
        """Labelled items as dataset examples (``source: "production"``), ready for ``Dataset``."""
        return [{"id": f"P-{tid}", "inputs": {"message": i["record"]["input"]},
                 "reference": {"want": list(i["record"].get("want", [])), "category": i["label"]},
                 "category": i["label"], "source": "production", "note": i["note"]}
                for tid, i in self.items.items() if i["label"] is not None]
