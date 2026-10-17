"""Few-shot ticket routing with any chat model, in batches (Lesson 14.03).

One request labels ``batch_size`` tickets at once with structured output, so the instructions and the
examples are paid for once per batch instead of once per ticket: about 20× fewer prompt tokens on Groq's
free tier. A batch that fails is retried once and then marked ``"error"`` (counted as wrong), so one bad
generation never stops a 200-ticket run.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from mastery.finetune.tickets import QUEUE_HELP, QUEUES

__all__ = ["pick_examples", "fewshot_prompt", "RouterRun", "route_with_llm", "Routed", "RoutedBatch"]

Queue = Literal["billing", "outage", "account_access", "bug", "how_to", "feature_request"]


class Routed(BaseModel):
    id: str
    queue: Queue


class RoutedBatch(BaseModel):
    labels: list[Routed]


def pick_examples(train: Sequence[dict[str, Any]], per_queue: int = 2) -> list[dict[str, Any]]:
    """``per_queue`` training tickets per queue, the shortest non-hard English ones (stable choice)."""
    out = []
    for q in QUEUES:
        pool = sorted((t for t in train if t["queue"] == q and not t.get("hard") and t.get("lang", "en") == "en"),
                      key=lambda t: (len(t["text"]), t["id"]))
        out += pool[:per_queue]
    return out


def fewshot_prompt(examples: Sequence[dict[str, Any]] = ()) -> str:
    lines = ["You route Orbita Cloud support tickets (weather stations and their dashboard) to one queue.", "", "Queues:"]
    lines += [f"- {q}: {QUEUE_HELP[q]}" for q in QUEUES]
    lines += ["", "If a ticket has two intents, pick the one the team must act on first. Tickets may be in Spanish."]
    if examples:
        lines += ["", "Examples:"] + [f"- {t['text']!r} → {t['queue']}" for t in examples]
    lines += ["", "Return one label per ticket id, for every id you are given."]
    return "\n".join(lines)


@dataclass
class RouterRun:
    labels: dict[str, str] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    failed_batches: int = 0

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def route_with_llm(model: Any, tickets: Sequence[dict[str, Any]], *, examples: Sequence[dict[str, Any]] = (),
                   batch_size: int = 20, structured: Callable[[Any, Any], Any] | None = None,
                   on_batch: Callable[[int, RouterRun], None] | None = None) -> RouterRun:
    """Label ``tickets`` with ``model``; ``structured(model, schema)`` defaults to ``mastery.models.structured_model``."""
    if structured is None:
        from mastery.models import structured_model as structured
    runner = structured(model, RoutedBatch, include_raw=True) if _takes_raw(structured) else structured(model, RoutedBatch)
    system = fewshot_prompt(examples)
    run = RouterRun()
    start = time.perf_counter()
    for b in range(0, len(tickets), batch_size):
        batch = tickets[b:b + batch_size]
        user = "\n".join(f"{t['id']}: {t['text']}" for t in batch)
        for attempt in (1, 2):
            try:
                out = runner.invoke([("system", system), ("user", user)])
                parsed, raw = (out["parsed"], out.get("raw")) if isinstance(out, dict) else (out, None)
                if parsed is None:
                    raise ValueError(f"unparsed reply: {out.get('parsing_error') if isinstance(out, dict) else ''}")
                usage = getattr(raw, "usage_metadata", None) or {}
                run.input_tokens += usage.get("input_tokens", 0)
                run.output_tokens += usage.get("output_tokens", 0)
                wanted = {t["id"] for t in batch}
                run.labels.update({r.id: r.queue for r in parsed.labels if r.id in wanted})
                break
            except Exception as exc:  # one bad generation must not stop the run
                print(f"⚠️ batch {b // batch_size + 1} attempt {attempt} failed: {type(exc).__name__}: {str(exc)[:120]}")
                if attempt == 2:
                    run.failed_batches += 1
        for t in batch:
            run.labels.setdefault(t["id"], "error")
        if on_batch:
            on_batch(b // batch_size + 1, run)
    run.seconds = round(time.perf_counter() - start, 2)
    return run


def _takes_raw(fn: Callable[..., Any]) -> bool:
    import inspect

    try:
        return "include_raw" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
