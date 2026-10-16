"""Retrieval metrics on a golden set: recall@k, hit rate, MRR (a preview of Module 10)."""
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


def score_answers(rows: list[dict[str, Any]], k: int = 5, *, require_chunk_id: bool = False) -> dict[str, Any]:
    """Reference scorer for a cited-RAG run (Project 06), computed independently of learner code.

    Each row is a golden item plus the run's output: ``in_corpus``, ``answer_contains``,
    ``expected_sources``, ``docs`` (retrieved) and ``answer`` (a ``CitedAnswer``).

    Returns counts, not just rates, so a check can say "12/16": ``in_corpus``/``out_of_corpus``
    (questions that ran), ``recall@k`` (in-corpus mean), ``correct``, ``false_dont_know`` (in-corpus
    questions answered with "don't know"), ``dont_know`` (out-of-corpus questions correctly
    declined), ``fabricated_final`` (citations in final answers that fail ``verify_citations``) and
    ``uncited`` (real answers shipped without a citation). ``require_chunk_id=True`` also counts
    citations without a valid ``chunk_id`` as fabricated.
    """
    from mastery.rag.citations import is_dont_know, verify_citations  # local import: no cycle at load time

    inside = [r for r in rows if r["in_corpus"]]
    outside = [r for r in rows if not r["in_corpus"]]
    recall = sum(recall_at_k(r["docs"], r["expected_sources"], k=k) for r in inside) / max(len(inside), 1)
    return {
        "in_corpus": len(inside),
        "out_of_corpus": len(outside),
        f"recall@{k}": round(recall, 2),
        "correct": sum(r["answer_contains"].lower() in r["answer"].answer.lower() for r in inside),
        "false_dont_know": sum(is_dont_know(r["answer"]) for r in inside),
        "dont_know": sum(is_dont_know(r["answer"]) for r in outside),
        "fabricated_final": sum(len(verify_citations(r["answer"], r["docs"], require_chunk_id=require_chunk_id)["fabricated"])
                                for r in rows),
        "uncited": sum(not r["answer"].citations and not is_dont_know(r["answer"]) for r in rows),
    }


def is_right(row: dict[str, Any]) -> bool:
    """One row's grade: the expected text for an in-corpus question; a decline for any other (correct refusal)."""
    from mastery.rag.citations import is_dont_know

    if row["in_corpus"]:
        return row["answer_contains"].lower() in row["answer"].answer.lower()
    return is_dont_know(row["answer"])


def score_by_stratum(rows: list[dict[str, Any]], key: str = "stratum") -> dict[str, dict[str, Any]]:
    """Per-stratum ``{"n", "right", "rate"}`` with :func:`is_right` (out-of-scope rows: right = declined)."""
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        cell = out.setdefault(row.get(key, "?"), {"n": 0, "right": 0})
        cell["n"] += 1
        cell["right"] += is_right(row)
    for cell in out.values():
        cell["rate"] = round(cell["right"] / cell["n"], 2)
    return out


def stratified_sample(items: list[dict[str, Any]], n: int, key: str = "stratum") -> list[dict[str, Any]]:
    """About ``n`` items, taken round-robin across strata in file order, so every stratum is represented."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(item.get(key, "?"), []).append(item)
    picked: list[dict[str, Any]] = []
    while len(picked) < min(n, len(items)):
        for group in groups.values():
            if group and len(picked) < n:
                picked.append(group.pop(0))
    return sorted(picked, key=items.index)
