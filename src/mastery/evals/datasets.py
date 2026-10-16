"""Datasets and offline experiments (Lesson 10.03).

A dataset is a list of examples ``{"id", "inputs", "reference", "category", "source"}``
built three ways: from traces (real failures and successes), from failure categories
(targeted examples so each category is measurable) and from **reviewed** synthetic
variations. :class:`Dataset` adds a content-hash version, a stable dev/test split, leak
checks and per-category coverage, and converts to LangSmith ``create_examples`` rows.

:func:`run_experiment` mirrors ``langsmith.evaluate(target, data, evaluators,
num_repetitions=k)`` offline: every example runs ``k`` times, every evaluator scores every
run, and :class:`Experiment` reports pass rates with intervals (via
:func:`~mastery.evals.stats.summarize_repeats`) and per-example scores for paired tests.

Example:
    >>> ds = Dataset("demo", [{"id": f"E{i}", "inputs": {"message": str(i)}, "reference": {}} for i in range(4)])
    >>> len(ds.version)
    12
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mastery.evals.meta import content_hash
from mastery.evals.stats import RepeatSummary, assert_disjoint, split_dev_test, summarize_repeats

__all__ = [
    "Dataset",
    "Experiment",
    "estimate_cost",
    "examples_from_categories",
    "examples_from_traces",
    "run_experiment",
]

Evaluator = Callable[..., Mapping[str, Any]]


def _example(record: Mapping[str, Any], category: str, source: str) -> dict[str, Any]:
    return {"id": str(record["id"]), "inputs": {"message": record["input"]},
            "reference": {"want": list(record.get("want", [])), "category": category},
            "category": category, "source": source}


def examples_from_traces(records: Iterable[Mapping[str, Any]], labels: Mapping[str, str]) -> list[dict[str, Any]]:
    """One example per labelled trace (``labels``: trace id -> category or ``"pass"``)."""
    return [_example(r, labels[str(r["id"])], "trace") for r in records if labels.get(str(r["id"]))]


def examples_from_categories(records: Iterable[Mapping[str, Any]], labels: Mapping[str, str], *,
                             per_category: int = 5, categories: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Up to ``per_category`` traces of each failure category, plus as many passes.

    Targeted coverage: a category with 3 examples in a 60-item random sample is not
    measurable; this picks every category on purpose (still from real traces).
    """
    wanted = list(categories) if categories else sorted({c for c in labels.values() if c and c != "pass"})
    picked: dict[str, list] = defaultdict(list)
    for record in records:
        cat = labels.get(str(record["id"]), "")
        if cat in wanted and len(picked[cat]) < per_category:
            picked[cat].append(_example(record, cat, "category"))
        elif cat == "pass" and len(picked["pass"]) < per_category * len(wanted):
            picked["pass"].append(_example(record, "pass", "category"))
    return [e for cat in [*wanted, "pass"] for e in picked[cat]]


@dataclass
class Dataset:
    """A named list of examples with a content version, splits and coverage."""

    name: str
    examples: list[dict[str, Any]] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        ids = [e["id"] for e in self.examples]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"duplicate example ids: {dup[:5]}")

    def __len__(self) -> int:
        return len(self.examples)

    @property
    def version(self) -> str:
        """Content hash of the examples: equal data -> equal version, on every machine."""
        return content_hash([{k: e.get(k) for k in ("id", "inputs", "reference", "split")} for e in self.examples])

    def dedupe(self) -> Dataset:
        """Keep the first example of each input text (case, spacing, punctuation ignored).

        Real traffic repeats itself ("refund my last invoice please"). Two copies of one
        message on both sides of a split is a leak: the test set then rewards memorising.
        """
        seen: set[str] = set()
        kept = []
        for e in self.examples:
            norm = " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in str(e["inputs"].get("message", e["inputs"]))).split())
            if norm not in seen:
                seen.add(norm)
                kept.append(e)
        return Dataset(self.name, kept, self.description)

    def split(self, *, test_fraction: float = 0.4, salt: str = "m10") -> Dataset:
        """Return a copy with ``split`` set to ``dev`` or ``test`` (stable, hash-based)."""
        dev, test = split_dev_test(self.examples, key="id", test_fraction=test_fraction, salt=salt)
        examples = [{**e, "split": "dev"} for e in dev] + [{**e, "split": "test"} for e in test]
        order = {e["id"]: i for i, e in enumerate(self.examples)}
        return Dataset(self.name, sorted(examples, key=lambda e: order[e["id"]]), self.description)

    def where(self, split: str) -> list[dict[str, Any]]:
        return [e for e in self.examples if e.get("split") == split]

    def check_no_leaks(self) -> None:
        """Raise :class:`~mastery.evals.stats.LeakageError` if a test input also sits in dev."""
        assert_disjoint(self.where("dev"), self.where("test"), key="id", text=lambda e: e["inputs"]["message"])

    def coverage(self) -> dict[str, dict[str, int]]:
        """``{category: {"dev": n, "test": n}}``: which categories each split can measure."""
        table: dict[str, Counter] = defaultdict(Counter)
        for e in self.examples:
            table[e.get("category", "")][e.get("split", "unsplit")] += 1
        return {cat: dict(counts) for cat, counts in sorted(table.items())}

    def to_jsonl(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in self.examples), encoding="utf-8")
        return path

    @classmethod
    def from_jsonl(cls, name: str, path: str | Path) -> Dataset:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        return cls(name, [json.loads(line) for line in lines if line.strip()])

    def to_langsmith(self) -> list[dict[str, Any]]:
        """Rows for ``client.create_examples(dataset_id=..., examples=rows)`` (LangSmith SDK)."""
        return [{"inputs": e["inputs"], "outputs": e["reference"],
                 "metadata": {"example_id": e["id"], "category": e.get("category"), "source": e.get("source"),
                              "dataset_version": self.version},
                 **({"split": e["split"]} if e.get("split") else {})} for e in self.examples]


@dataclass
class Experiment:
    """Results of :func:`run_experiment`: ``runs[r][example_id] = {"outputs", "scores"}``."""

    name: str
    dataset_version: str
    runs: list[dict[str, dict[str, Any]]]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def keys(self) -> list[str]:
        return sorted({k for run in self.runs for row in run.values() for k in row["scores"]})

    def scores(self, key: str) -> list[dict[str, float]]:
        """One mapping per repetition: example id -> score for ``key`` (for summarize_repeats)."""
        return [{i: float(row["scores"][key]) for i, row in run.items()} for run in self.runs]

    def summary(self, key: str) -> RepeatSummary:
        return summarize_repeats(self.scores(key))

    def per_example(self, key: str) -> dict[str, float]:
        """Mean score per example across repetitions (input for ``paired_compare``)."""
        runs = self.scores(key)
        return {i: sum(run[i] for run in runs) / len(runs) for i in runs[0]}


def run_experiment(target: Callable[[Mapping[str, Any]], Mapping[str, Any]], examples: Sequence[Mapping[str, Any]],
                   evaluators: Sequence[Evaluator], *, repetitions: int = 1, name: str = "experiment",
                   dataset_version: str = "", metadata: Mapping[str, Any] | None = None) -> Experiment:
    """Offline twin of ``langsmith.evaluate(..., num_repetitions=repetitions)``.

    ``target(inputs) -> outputs``; each evaluator is called as
    ``evaluator(inputs=..., outputs=..., reference_outputs=...)`` and returns
    ``{"key": str, "score": bool | float}`` (the openevals / LangSmith shape).
    """
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    runs = []
    for _ in range(repetitions):
        run = {}
        for example in examples:
            outputs = target(example["inputs"])
            scores = {}
            for evaluator in evaluators:
                result = evaluator(inputs=example["inputs"], outputs=outputs, reference_outputs=example["reference"])
                scores[result["key"]] = result["score"]
            run[example["id"]] = {"outputs": outputs, "scores": scores}
        runs.append(run)
    return Experiment(name, dataset_version, runs, dict(metadata or {}))


def estimate_cost(n_examples: int, *, repetitions: int = 3, calls_per_example: float = 3,
                  tokens_per_call: float = 1500, usd_per_million_tokens: float = 0.0,
                  judge_calls_per_example: float = 0) -> dict[str, float]:
    """Budget one experiment before you run it: calls, tokens and dollars.

    Judges count too: a judge on every run doubles the calls of a one-call target.
    """
    calls = n_examples * repetitions * (calls_per_example + judge_calls_per_example)
    tokens = calls * tokens_per_call
    return {"calls": calls, "tokens": tokens, "usd": round(tokens / 1e6 * usd_per_million_tokens, 4)}
