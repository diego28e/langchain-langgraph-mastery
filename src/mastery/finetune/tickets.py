"""The Orbita Cloud ticket-router dataset (Module 14): load, split by family, check leaks, export for training.

``data/samples/local/tickets.jsonl`` holds ~900 synthetic support tickets in six queues (English, ~12%
Spanish, and a *hard* slice: very short, two intents, sarcasm). Tickets made from the same template form a
**family**, and a whole family always lands in one split: otherwise a near-copy of a test ticket sits in
the training data and every score looks better than it is.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

__all__ = ["QUEUES", "QUEUE_HELP", "TICKETS_PATH", "load_tickets", "by_split", "assign_splits", "family_overlap",
           "to_chat_example", "write_chat_jsonl", "SYSTEM_PROMPT"]

QUEUES = ("billing", "outage", "account_access", "bug", "how_to", "feature_request")
QUEUE_HELP = {
    "billing": "charges, refunds, invoices, plans, payment details",
    "outage": "the service is down or unreachable for many users or stations right now",
    "account_access": "login, passwords, 2FA, SSO, invites, locked or deactivated accounts",
    "bug": "a feature works incorrectly for this customer (wrong values, crashes, broken buttons)",
    "how_to": "the customer asks how to do something that already exists",
    "feature_request": "the customer asks for something the product does not have",
}
SYSTEM_PROMPT = ("You route Orbita Cloud support tickets. Answer with exactly one queue name: "
                 + ", ".join(QUEUES) + ". If a ticket has two intents, pick the one the team must act on first.")
TICKETS_PATH = Path(__file__).resolve().parents[3] / "data" / "samples" / "local" / "tickets.jsonl"


def load_tickets(path: Path | str | None = None) -> list[dict[str, Any]]:
    """All tickets as dicts: ``id, text, queue, lang, family, hard, split``."""
    with Path(path or TICKETS_PATH).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def by_split(tickets: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """``{"train": [...], "dev": [...], "test": [...]}`` from the stored ``split`` field."""
    out: dict[str, list[dict[str, Any]]] = {"train": [], "dev": [], "test": []}
    for t in tickets:
        out[t["split"]].append(t)
    return out


def _rank(family: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{family}".encode()).hexdigest()


def assign_splits(rows: Sequence[dict[str, Any]], *, test: float = 0.2, dev: float = 0.1,
                  salt: str = "m14") -> list[dict[str, Any]]:
    """Give every row a ``split`` by **family**, stratified by (queue, lang, hard).

    Within each stratum the families are ordered by a salted hash (stable, independent of row order); the first
    ``max(1, round(n*test))`` go to test, the next ``round(n*dev)`` (only if ≥ 5 families) to dev, the rest to train.
    """
    strata: dict[tuple, set[str]] = defaultdict(set)
    for r in rows:
        strata[(r["queue"], r.get("lang", "en"), bool(r.get("hard")))].add(r["family"])
    where: dict[str, str] = {}
    for fams in strata.values():
        ordered = sorted(fams, key=lambda f: _rank(f, salt))
        n_test = max(1, round(len(ordered) * test))
        n_dev = round(len(ordered) * dev) if len(ordered) >= 5 else 0
        for i, fam in enumerate(ordered):
            where[fam] = "test" if i < n_test else "dev" if i < n_test + n_dev else "train"
    return [{**r, "split": where[r["family"]]} for r in rows]


def family_overlap(a: Iterable[dict[str, Any]], b: Iterable[dict[str, Any]]) -> set[str]:
    """Families present in both sets (must be empty between train and test)."""
    return {t["family"] for t in a} & {t["family"] for t in b}


def to_chat_example(ticket: dict[str, Any], system: str = SYSTEM_PROMPT) -> dict[str, Any]:
    """One training example in the conversation format TRL/Unsloth read (``{"messages": [...]}``)."""
    return {"messages": [{"role": "system", "content": system},
                         {"role": "user", "content": ticket["text"]},
                         {"role": "assistant", "content": ticket["queue"]}]}


def write_chat_jsonl(tickets: Iterable[dict[str, Any]], path: Path | str, system: str = SYSTEM_PROMPT) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for t in tickets:
            f.write(json.dumps(to_chat_example(t, system), ensure_ascii=False) + "\n")
    return path
