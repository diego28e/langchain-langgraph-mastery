"""Error analysis as data: label sheets, failure taxonomies, counts with intervals.

Introduced in Lesson 10.01. You read traces, write one free-form note per trace about the
**first** thing that went wrong (open coding), then group the notes into 5-10 named
categories (axial coding). This module keeps both steps honest:

- :class:`LabelSheet` is the CSV you fill in while reading traces (one row per trace).
- :class:`Category` / :class:`Taxonomy` hold each category's definition, a real example,
  a "not this" counter-example, a severity and the decision (fix / code check / judge).
- :meth:`Taxonomy.rank` orders categories by frequency x severity, every frequency with a
  Wilson interval, so "18% of traces" always comes with how sure you can be.
- :meth:`LabelSheet.saturation` shows when new traces stopped adding categories.

Example:
    >>> sheet = LabelSheet([{"trace_id": "T1", "category": "pass"},
    ...                     {"trace_id": "T2", "category": "dropped_request"}])
    >>> print(f"{sheet.failure_rate():.0%}")
    50% [9%, 91%] (wilson, n=2)
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mastery.evals.stats import Interval, wilson_interval

__all__ = ["ACTIONS", "PASS", "Category", "LabelSheet", "RankedCategory", "Taxonomy"]

PASS = "pass"
#: What to do with a category once it is named (Lesson 10.01, "fix it or measure it").
ACTIONS = ("fix", "code_check", "judge")


class LabelSheet:
    """One row per trace you read: ``trace_id``, ``note`` (open coding), ``category`` (axial).

    ``category`` is ``"pass"`` for a trace with no failure and ``""`` while not labelled
    yet. Any other columns (input, tools, answer...) are kept as they are.
    """

    def __init__(self, rows: Iterable[Mapping[str, Any]]):
        self.rows = [dict(row) for row in rows]
        ids = [row.get("trace_id") for row in self.rows]
        if any(not i for i in ids):
            raise ValueError("every row needs a trace_id")
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate trace_id(s): {duplicates[:5]}")
        for row in self.rows:
            row["category"] = str(row.get("category") or "").strip()
            row["note"] = str(row.get("note") or "").strip()

    # -- files -----------------------------------------------------------------------
    @classmethod
    def from_csv(cls, path: str | Path) -> LabelSheet:
        with open(path, newline="", encoding="utf-8") as handle:
            return cls(csv.DictReader(handle))

    def to_csv(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        columns = list(dict.fromkeys(["trace_id", "note", "category", *(k for r in self.rows for k in r)]))
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(self.rows)
        return path

    # -- views -----------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.rows)

    def labelled(self) -> list[dict[str, Any]]:
        """Rows that already have a category (``pass`` included)."""
        return [row for row in self.rows if row["category"]]

    def categories(self) -> list[str]:
        """Failure categories in first-seen order (``pass`` excluded)."""
        return list(dict.fromkeys(r["category"] for r in self.labelled() if r["category"] != PASS))

    def counts(self) -> Counter:
        return Counter(row["category"] for row in self.labelled())

    def share(self, category: str) -> Interval:
        """Share of labelled traces in ``category``, with a 95% Wilson interval."""
        rows = self.labelled()
        return wilson_interval(sum(r["category"] == category for r in rows), len(rows))

    def failure_rate(self) -> Interval:
        """Share of labelled traces with ANY failure, with a 95% Wilson interval."""
        rows = self.labelled()
        return wilson_interval(sum(r["category"] != PASS for r in rows), len(rows))

    def saturation(self) -> list[tuple[int, int]]:
        """``(traces read, distinct failure categories so far)`` after every labelled trace.

        When the second number stops growing for the last 20-30 traces, more reading
        mostly confirms what you know: a reasonable moment to stop (theoretical saturation).
        """
        seen: set[str] = set()
        curve = []
        for index, row in enumerate(self.labelled(), start=1):
            if row["category"] != PASS:
                seen.add(row["category"])
            curve.append((index, len(seen)))
        return curve

    def unlabelled(self) -> list[str]:
        return [row["trace_id"] for row in self.rows if not row["category"]]


@dataclass(frozen=True)
class Category:
    """One named failure mode. Every field is required: a vague category can't be measured."""

    name: str
    definition: str
    example: str
    not_this: str
    severity: int  # 1 (cosmetic) .. 5 (harms a customer or the business)
    action: str = "judge"

    def problems(self) -> list[str]:
        found = [f"{self.name}: empty {f}" for f in ("definition", "example", "not_this") if not getattr(self, f).strip()]
        if not 1 <= int(self.severity) <= 5:
            found.append(f"{self.name}: severity must be 1-5, got {self.severity}")
        if self.action not in ACTIONS:
            found.append(f"{self.name}: action must be one of {ACTIONS}, got {self.action!r}")
        if self.name == PASS:
            found.append("'pass' is reserved for traces without a failure")
        return found


@dataclass(frozen=True)
class RankedCategory:
    name: str
    count: int
    share: Interval
    severity: int
    priority: float  # share x severity
    action: str


@dataclass
class Taxonomy:
    """Your failure categories, checked against the label sheet that produced them."""

    categories: dict[str, Category] = field(default_factory=dict)

    @classmethod
    def from_dicts(cls, data: Mapping[str, Mapping[str, Any]]) -> Taxonomy:
        return cls({name: Category(name=name, **dict(fields)) for name, fields in data.items()})

    def validate(self, sheet: LabelSheet | None = None, *, min_categories: int = 5,
                 max_categories: int = 10) -> list[str]:
        """Return every problem found (an empty list means the taxonomy is usable)."""
        found = [p for c in self.categories.values() for p in c.problems()]
        if not min_categories <= len(self.categories) <= max_categories:
            found.append(f"{len(self.categories)} categories: aim for {min_categories}-{max_categories}")
        if sheet is not None:
            unknown = sorted(set(sheet.categories()) - set(self.categories))
            if unknown:
                found.append(f"labels not in the taxonomy: {unknown}")
            if sheet.unlabelled():
                found.append(f"{len(sheet.unlabelled())} trace(s) not labelled yet")
        return found

    def rank(self, sheet: LabelSheet) -> list[RankedCategory]:
        """Categories by frequency x severity (ties: higher severity first). Zero counts stay in.

        A severe category seen 0 times is not "solved": its Wilson upper bound says how
        common it could still be, which is why it keeps a (code) check or a red-team test.
        """
        counts = sheet.counts()
        ranked = []
        for name, cat in self.categories.items():
            share = sheet.share(name)
            ranked.append(RankedCategory(name, counts.get(name, 0), share, int(cat.severity),
                                         share.estimate * int(cat.severity), cat.action))
        return sorted(ranked, key=lambda r: (-r.priority, -r.severity, r.name))

    def to_markdown(self, sheet: LabelSheet | None = None) -> str:
        """``taxonomy.md``: one section per category, with counts when ``sheet`` is given."""
        lines = ["# Failure taxonomy", ""]
        order = [r.name for r in self.rank(sheet)] if sheet else list(self.categories)
        for name in order:
            cat = self.categories[name]
            lines += [f"## {name}", "", f"- **Definition:** {cat.definition}", f"- **Example:** {cat.example}",
                      f"- **Not this:** {cat.not_this}", f"- **Severity:** {cat.severity}/5 · **Action:** {cat.action}"]
            if sheet is not None:
                lines.append(f"- **Frequency:** {sheet.counts().get(name, 0)} of {len(sheet.labelled())} traces, {sheet.share(name):.0%}")
            lines.append("")
        return "\n".join(lines)
