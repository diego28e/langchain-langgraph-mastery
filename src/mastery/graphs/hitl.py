"""Human-in-the-loop helpers for graphs (Module 08, Lesson 08.03; Project 08).

- :func:`approval_node` builds a node that pauses with ``interrupt()`` and routes on the
  human's decision: approve, edit (replace the draft), or reject with feedback.
- :func:`parse_decision` validates what the human sent back; invalid answers re-ask
  inside the same node (the documented validation-loop pattern), never crash.
- :func:`run_until_pause`, :func:`resume` and :func:`drive` run a graph up to its next
  interrupt, resume it with ``Command(resume=...)``, or answer every pause with a
  reviewer function (scripted humans for tests and keyless notebooks).

Rules the node follows (from the Interrupts docs): no ``try/except`` around
``interrupt()``, the same interrupt order on every run, and no side effects before
the interrupt (the node re-runs from the top when it is resumed).
Verified 2026-10-12 with langgraph 1.2.14.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Literal

from langgraph.graph import END
from langgraph.types import Command, interrupt
from pydantic import BaseModel, ValidationError, model_validator

__all__ = [
    "ACTIONS",
    "Decision",
    "adrive",
    "approval_node",
    "approval_request",
    "aresume",
    "arun_until_pause",
    "drive",
    "parse_decision",
    "pending_interrupts",
    "resume",
    "run_until_pause",
    "scripted_reviewer",
]

ACTIONS = ("approve", "edit", "reject")


class Decision(BaseModel):
    """What a reviewer sends back: ``{"action": "approve" | "edit" | "reject", ...}``."""

    action: Literal["approve", "edit", "reject"]
    text: str | None = None          # edit: the replacement text
    feedback: str | None = None      # reject: what to change

    @model_validator(mode="after")
    def _needs_payload(self) -> Decision:
        if self.action == "edit" and not (self.text or "").strip():
            raise ValueError("edit needs non-empty 'text'")
        if self.action == "reject" and not (self.feedback or "").strip():
            raise ValueError("reject needs non-empty 'feedback'")
        return self


def parse_decision(value: Any) -> Decision:
    """Accept ``"approve"``, ``{"action": ...}`` or a :class:`Decision`; raise ``ValueError`` otherwise."""
    if isinstance(value, Decision):
        return value
    if isinstance(value, str):
        value = {"action": value.strip().lower()}
    if not isinstance(value, dict):
        raise ValueError(f"expected a dict like {{'action': 'approve'}}, got {type(value).__name__}")  # noqa: TRY004 - the approval loop catches ValueError
    try:
        return Decision.model_validate(value)
    except ValidationError as exc:
        raise ValueError("; ".join(e["msg"] for e in exc.errors())) from None


def approval_request(draft: str, *, question: str = "Approve this draft?", error: str | None = None,
                     attempt: int = 1) -> dict[str, Any]:
    """The JSON payload shown to the reviewer (what ``__interrupt__[0].value`` contains)."""
    payload = {"kind": "approval", "question": question, "draft": draft, "actions": list(ACTIONS),
               "examples": [{"action": "approve"}, {"action": "edit", "text": "..."},
                            {"action": "reject", "feedback": "..."}], "attempt": attempt}
    if error:
        payload["error"] = error
    return payload


def approval_node(*, draft_key: str = "draft", approved: str = "finalize", rejected: str = "draft",
                  feedback_key: str = "feedback", count_key: str = "rejections",
                  max_rejections: int | None = 3, give_up: str = END, max_invalid: int = 3,
                  question: str = "Approve this draft?") -> Callable[[dict], Command]:
    """Build an approval node. Register it with ``destinations=(approved, rejected, give_up)``.

    approve → ``approved`` · edit → ``approved`` with ``state[draft_key] = text`` ·
    reject → ``rejected`` with ``state[feedback_key] = feedback`` and ``state[count_key] += 1``;
    after ``max_rejections`` rejections → ``give_up``. Sets ``state["approval"]``.
    An invalid answer re-asks (up to ``max_invalid`` times, then counts as a rejection).
    """

    def approval(state: dict) -> Command:
        error, decision = None, None
        for attempt in range(1, max_invalid + 1):
            answer = interrupt(approval_request(state.get(draft_key, ""), question=question,
                                                error=error, attempt=attempt))
            try:
                decision = parse_decision(answer)
                break
            except ValueError as exc:        # validating the *answer*; interrupt() itself is outside any try
                error = str(exc)
        if decision is None:
            decision = Decision(action="reject", feedback=f"no valid decision after {max_invalid} tries ({error})")
        if decision.action == "approve":
            return Command(goto=approved, update={"approval": "approved"})
        if decision.action == "edit":
            return Command(goto=approved, update={draft_key: decision.text, "approval": "edited"})
        count = int(state.get(count_key, 0) or 0) + 1
        target = give_up if max_rejections is not None and count >= max_rejections else rejected
        return Command(goto=target, update={feedback_key: decision.feedback, count_key: count,
                                            "approval": "rejected" if target == rejected else "gave_up"})

    approval.__name__ = "approval"
    return approval


def pending_interrupts(graph: Any, config: dict) -> list[Any]:
    """Interrupts the thread is currently paused on (empty when it isn't paused)."""
    return list(graph.get_state(config).interrupts)


def _report(part: dict, printer: Callable[[str], Any] | None) -> None:
    if printer is None:
        return
    for node, update in (part["data"] or {}).items():
        where = "/".join(ns.split(":")[0] for ns in part["ns"])
        label = f"{where}/{node}" if where else node
        if node == "__interrupt__":
            where_txt = f" in {where}" if where else ""
            printer(f"⏸️  paused{where_txt} → {update[0].value if update else ''!s:.120}")
        else:
            keys = ", ".join(update) if isinstance(update, dict) else type(update).__name__
            printer(f"✅ {label:<24} updated: {keys}")


def _thread_only(config: dict) -> dict:
    """Drop ``checkpoint_id`` so we read the NEWEST checkpoint after a replay/fork from an old one."""
    conf = {k: v for k, v in (config.get("configurable") or {}).items() if k != "checkpoint_id"}
    return {**config, "configurable": conf}


def _result(snapshot: Any) -> dict[str, Any]:
    interrupts = list(snapshot.interrupts)
    return {"values": snapshot.values, "interrupts": interrupts, "done": not snapshot.next and not interrupts}


def run_until_pause(graph: Any, inputs: Any, config: dict, *, printer: Callable[[str], Any] | None = print,
                    subgraphs: bool = False) -> dict[str, Any]:
    """Stream ``inputs`` (or a ``Command``) until the run ends or pauses.

    Prints one line per node update (``printer=None`` for silence). Returns
    ``{"values": <state>, "interrupts": [Interrupt, ...], "done": bool}``.
    """
    for part in graph.stream(inputs, config, stream_mode="updates", subgraphs=subgraphs, version="v2"):
        _report(part, printer)
    return _result(graph.get_state(_thread_only(config)))


async def arun_until_pause(graph: Any, inputs: Any, config: dict, *, printer: Callable[[str], Any] | None = print,
                           subgraphs: bool = False, context: Any = None) -> dict[str, Any]:
    """Async :func:`run_until_pause` (graphs with async nodes, ``AsyncSqliteSaver``)."""
    async for part in graph.astream(inputs, config, stream_mode="updates", subgraphs=subgraphs, version="v2",
                                    context=context):
        _report(part, printer)
    return _result(await graph.aget_state(_thread_only(config)))


def resume(graph: Any, config: dict, value: Any, *, interrupt_id: str | None = None,
           printer: Callable[[str], Any] | None = print) -> dict[str, Any]:
    """Resume a paused thread. With several pending interrupts pass ``interrupt_id`` or a ``{id: value}`` dict."""
    payload = {interrupt_id: value} if interrupt_id else value
    return run_until_pause(graph, Command(resume=payload), config, printer=printer)


def drive(graph: Any, inputs: Any, config: dict, reviewer: Callable[[Any], Any], *, max_pauses: int = 10,
          printer: Callable[[str], Any] | None = None) -> dict[str, Any]:
    """Run to completion, answering each pause with ``reviewer(interrupt.value)``. Returns the last result."""
    result = run_until_pause(graph, inputs, config, printer=printer)
    pauses = 0
    while result["interrupts"]:
        pauses += 1
        if pauses > max_pauses:
            raise RuntimeError(f"still paused after {max_pauses} answers; check the reviewer")
        answers = {i.id: reviewer(i.value) for i in result["interrupts"]}
        value = next(iter(answers.values())) if len(answers) == 1 else answers
        result = run_until_pause(graph, Command(resume=value), config, printer=printer)
    result["pauses"] = pauses
    return result


async def aresume(graph: Any, config: dict, value: Any, *, interrupt_id: str | None = None,
                  printer: Callable[[str], Any] | None = print, context: Any = None) -> dict[str, Any]:
    """Async :func:`resume`."""
    payload = {interrupt_id: value} if interrupt_id else value
    return await arun_until_pause(graph, Command(resume=payload), config, printer=printer, context=context)


async def adrive(graph: Any, inputs: Any, config: dict, reviewer: Callable[[Any], Any], *, max_pauses: int = 10,
                 printer: Callable[[str], Any] | None = None, context: Any = None) -> dict[str, Any]:
    """Async :func:`drive`."""
    result = await arun_until_pause(graph, inputs, config, printer=printer, context=context)
    pauses = 0
    while result["interrupts"]:
        pauses += 1
        if pauses > max_pauses:
            raise RuntimeError(f"still paused after {max_pauses} answers; check the reviewer")
        answers = {i.id: reviewer(i.value) for i in result["interrupts"]}
        value = next(iter(answers.values())) if len(answers) == 1 else answers
        result = await arun_until_pause(graph, Command(resume=value), config, printer=printer, context=context)
    result["pauses"] = pauses
    return result


def scripted_reviewer(answers: Iterable[Any]) -> Callable[[Any], Any]:
    """A fake human that gives ``answers`` in order (then keeps approving). For tests and 🧪 cells."""
    queue = list(answers)

    def review(payload: Any) -> Any:
        return queue.pop(0) if queue else {"action": "approve"}

    review.remaining = queue  # type: ignore[attr-defined]
    return review
