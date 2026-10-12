"""Retrieval metrics on a golden set: recall@k, hit rate, MRR (a preview of Module 09)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.documents import Document


def _sources(docs: list[Document] | list[str]) -> list[str]:
    return [d if isinstance(d, str) else d.metadata.get("source", "?") for d in docs]


def recall_at_k(retrieved: list[Document] | list[str], expected: list[str], k: int = 5) -> float:
    """Share of the expected sources found in the top ``k`` results (1.0 = all found)."""
    if not expected:
        return 1.0
    top = set(_sources(retrieved)[:k])
    return sum(1 for s in expected if s in top) / len(expected)


def mrr(retrieved: list[Document] | list[str], expected: list[str]) -> float:
    """1 / rank of the first relevant result (0 when none): rewards putting the right chunk first."""
    for rank, source in enumerate(_sources(retrieved), start=1):
        if source in expected:
            return 1.0 / rank
    return 0.0


def evaluate_retrieval(search: Callable[[str], list[Document]], golden: list[dict], k: int = 5) -> dict[str, Any]:
    """Run ``search`` on every in-corpus golden question; return per-question rows and averages.

    ``hit_rate`` = share of questions with at least one expected source in the top ``k``.
    """
    rows = []
    for item in golden:
        if not item.get("in_corpus", True):
            continue
        docs = search(item["question"])
        r = recall_at_k(docs, item["expected_sources"], k)
        rows.append({"id": item["id"], "recall": r, "hit": r > 0, "mrr": mrr(docs[:k], item["expected_sources"]),
                     "top": _sources(docs)[:k]})
    n = len(rows) or 1
    return {"k": k, "questions": len(rows), "recall": round(sum(r["recall"] for r in rows) / n, 3),
            "hit_rate": round(sum(r["hit"] for r in rows) / n, 3), "mrr": round(sum(r["mrr"] for r in rows) / n, 3),
            "rows": rows}
