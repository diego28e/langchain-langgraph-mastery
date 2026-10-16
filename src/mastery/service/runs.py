"""Background runs for a long-running agent: queue, concurrency limit, event log, resume and cancel (Lessons 12.03-12.04).

An HTTP request must not wait for a whole agent run: runs take seconds to minutes, clients
disconnect, users cancel. :class:`RunManager` starts each run as an ``asyncio`` task and keeps
an **event log** per run (tokens, steps, the final answer), so any number of clients can follow
a run and a client that reconnects resumes from the last event it saw (SSE ``Last-Event-ID``).

What it enforces, and the error each rule raises (the FastAPI app maps them to HTTP codes):

- at most ``max_concurrent`` runs execute at once; the rest wait in a queue (queue time is measured);
- at most ``max_queue`` runs wait; beyond that :class:`ServiceBusy` (HTTP 429, back-pressure);
- one active run per thread; a second message while one runs raises :class:`ThreadBusy` (HTTP 409),
  the "reject" double-texting strategy;
- an ``idempotency_key`` already used by the same user returns the ORIGINAL run (no second run,
  so a retried "refund" request can't refund twice);
- the optional :class:`~mastery.service.budgets.SpendLedger` refuses runs over budget (:class:`OverBudget`, HTTP 429);
- every run ends ``success``, ``interrupted`` (waiting for a human), ``error``, ``cancelled`` or ``timeout``.

Runs, events and idempotency keys are written to a ``store`` (:mod:`mastery.service.store`): in memory
by default, SQLite or Postgres from Lesson 12.05, so a restarted process can still replay finished
runs and honour old idempotency keys. Finished runs
become :class:`~mastery.service.slo.RunRecord`\\ s, so the SLO code of Lesson 12.01 reads the service's own log.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mastery.service.budgets import SpendLedger
from mastery.service.observability import request_id_var
from mastery.service.slo import RunRecord

TERMINAL = frozenset({"success", "interrupted", "error", "cancelled", "timeout"})


SHUTDOWN_MESSAGE = "the service shut down during this run; please send it again"


class ServiceBusy(Exception):
    """The queue is full: try again later (HTTP 429 with Retry-After)."""


class ThreadBusy(Exception):
    """This thread already has an active run (HTTP 409)."""


class OverBudget(Exception):
    """The spend ledger refused the run (HTTP 429); ``reason`` says which cap."""


@dataclass
class Event:
    """One entry of a run's event log. ``id`` is its position, used as the SSE event id."""

    id: int
    event: str          # "metadata", "token", "step", "interrupt", "end", "error"
    data: dict[str, Any]


@dataclass
class Run:
    run_id: str
    thread_id: str
    user_id: str
    status: str = "queued"
    created_at: float = 0.0
    started_at: float | None = None
    first_token_at: float | None = None
    ended_at: float | None = None
    answer: str | None = None
    error: str | None = None
    interrupt: Any = None
    usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    idempotency_key: str | None = None
    request_id: str | None = None      # the HTTP request that started it (logs and traces, Lesson 12.07)
    events: list[Event] = field(default_factory=list)
    saved: int = 0                   # events already written to the store
    task: asyncio.Task | None = field(default=None, repr=False)
    _changed: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    @property
    def done(self) -> bool:
        return self.status in TERMINAL

    def emit(self, event: str, data: dict[str, Any]) -> Event:
        item = Event(len(self.events), event, data)
        self.events.append(item)
        self._changed.set()            # wake every follower; each re-arms its own wait
        return item

    def public(self) -> dict[str, Any]:
        """What GET /runs/{id} returns (no internals)."""
        def secs(t: float | None) -> float | None:
            return None if t is None else round(t - self.created_at, 3)
        return {"run_id": self.run_id, "thread_id": self.thread_id, "status": self.status,
                "answer": self.answer, "error": self.error, "interrupt": self.interrupt,
                "queue_s": secs(self.started_at), "ttft_s": secs(self.first_token_at), "duration_s": secs(self.ended_at),
                "usage": self.usage, "cost_usd": round(self.cost_usd, 8), "events": len(self.events)}

    def stored(self) -> dict[str, Any]:
        """What the store keeps: the public view plus owner and key."""
        return self.public() | {"user_id": self.user_id, "idempotency_key": self.idempotency_key}

    def record(self) -> RunRecord:
        """This run as a :class:`RunRecord` for SLOs (``started_at`` is the submit time)."""
        status = {"success": "ok", "interrupted": "ok", "cancelled": "cancelled"}.get(self.status, "error")
        ttft = None if self.first_token_at is None else self.first_token_at - self.created_at
        duration = None if self.ended_at is None else self.ended_at - self.created_at
        queue = (self.started_at or self.created_at) - self.created_at
        return RunRecord(self.run_id, self.user_id, self.created_at, status, ttft, duration, self.cost_usd,
                         {"queue": round(queue, 4)})


def _text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text")


class RunManager:
    """Run a compiled LangGraph graph (e.g. a ``create_agent`` agent) in the background.

    Args:
        graph: Compiled graph with a checkpointer (threads need one).
        max_concurrent: Runs executing at once (a semaphore; the rest queue).
        max_queue: Runs allowed to wait; more raise :class:`ServiceBusy`.
        timeout_s: Wall-clock limit per run; a run past it ends ``timeout``.
        context_for: ``(run) -> context`` for ``astream(context=...)``, e.g. the signed-in customer.
        ledger, estimate, model: Optional cost control. ``estimate(input) -> USD`` is checked before
            the run; after it, the run's real usage is priced for ``model`` and charged.
        recursion_limit: Graph steps per run.
        clock: Time source (tests pass a fake one).
        trace_metadata: Added to every run's config ``metadata`` (with run, thread and user ids), so
            LangSmith or OpenTelemetry traces can be filtered by them (Lesson 12.07).

    ``listeners`` are called with each run once it has ended and been saved (metrics, Lesson 12.07).
    """

    def __init__(self, graph: Any, *, max_concurrent: int = 4, max_queue: int = 50, timeout_s: float = 120.0,
                 context_for: Callable[[Run], Any] | None = None, ledger: SpendLedger | None = None,
                 estimate: Callable[[Any], float] | None = None, model: str | None = None,
                 recursion_limit: int = 40, clock: Callable[[], float] = time.monotonic, store: Any = None,
                 flush_every_s: float = 0.25, trace_metadata: dict[str, Any] | None = None) -> None:
        from mastery.service.store import MemoryStore

        self.graph = graph
        self.max_concurrent, self.max_queue, self.timeout_s = max_concurrent, max_queue, timeout_s
        self.context_for, self.ledger, self.estimate, self.model = context_for, ledger, estimate, model
        self.recursion_limit, self.clock = recursion_limit, clock
        self.store = store if store is not None else MemoryStore()
        self.flush_every_s = flush_every_s
        self.trace_metadata = dict(trace_metadata or {})
        self.listeners: list[Callable[[Run], None]] = []
        self.draining = False                            # set by shutdown(): no new runs
        self.runs: dict[str, Run] = {}
        self._active: dict[str, str] = {}               # thread_id -> run_id
        self._semaphore: asyncio.Semaphore | None = None

    # -- submitting -------------------------------------------------------------------------
    async def submit(self, *, thread_id: str, user_id: str, input: Any, idempotency_key: str | None = None) -> Run:
        """Queue a run and return it at once (status ``queued``). Raises the errors in the module docstring."""
        if idempotency_key:
            known = await self.store.run_for_key(user_id, idempotency_key)
            if known:
                return self.runs.get(known) or self._from_store(await self.store.get_run(known))
        if self.draining:
            raise ServiceBusy("the service is shutting down; retry in a few seconds")
        active = self._active.get(thread_id)
        if active and not self.runs[active].done:
            raise ThreadBusy(f"thread {thread_id} already has an active run ({active})")
        if self.queued >= self.max_queue:
            raise ServiceBusy(f"queue full ({self.max_queue} runs waiting)")
        if self.ledger is not None and self.estimate is not None:
            decision = self.ledger.check(self._day(), user_id, self.estimate(input))
            if not decision.allowed:
                raise OverBudget(decision.reason)
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        run = Run(f"run-{uuid.uuid4().hex[:12]}", thread_id, user_id, created_at=self.clock(),
                  idempotency_key=idempotency_key, request_id=request_id_var.get())
        self.runs[run.run_id] = run
        self._active[thread_id] = run.run_id
        run.emit("metadata", {"run_id": run.run_id, "thread_id": thread_id})
        await self.store.save_run(run.stored())
        if idempotency_key:
            await self.store.remember_key(user_id, idempotency_key, run.run_id)
        await self._flush(run)
        run.task = asyncio.create_task(self._execute(run, input))
        await asyncio.sleep(0)          # let the task take a free slot now, so `queued` is accurate
        return run

    async def _execute(self, run: Run, input: Any) -> None:
        assert self._semaphore is not None
        try:
            async with self._semaphore:
                if run.done:                       # cancelled while queued
                    return
                run.started_at, run.status = self.clock(), "running"
                await asyncio.wait_for(self._stream(run, input), timeout=self.timeout_s)
        except asyncio.CancelledError:
            if not run.done:
                self._finish(run, "cancelled")
                run.emit("end", {"status": "cancelled"})
        except asyncio.TimeoutError:
            self._finish(run, "timeout", error=f"run exceeded {self.timeout_s:g} s")
            run.emit("error", {"status": "timeout", "message": run.error})
        except Exception as exc:  # noqa: BLE001  (the run fails, the service keeps going)
            self._finish(run, "error", error=f"{type(exc).__name__}: {exc}")
            run.emit("error", {"status": "error", "message": run.error})
        finally:
            await self._charge(run)
            await self._flush(run)
            await self.store.save_run(run.stored())
            for listener in self.listeners:
                try:
                    listener(run)
                except Exception:  # noqa: BLE001  (a broken metric must not break the run)
                    pass

    def config_for(self, run: Run) -> dict[str, Any]:
        """The LangGraph config for ``run``: thread, step limit, and trace name, tags and metadata."""
        return {"configurable": {"thread_id": run.thread_id}, "recursion_limit": self.recursion_limit,
                "run_name": "service-run", "tags": ["agent-service"],
                "metadata": {**self.trace_metadata, "service_run_id": run.run_id, "thread_id": run.thread_id,
                             "user_id": run.user_id, "request_id": run.request_id}}

    async def _stream(self, run: Run, input: Any) -> None:
        config = self.config_for(run)
        kwargs = {"context": self.context_for(run)} if self.context_for else {}
        last_flush = self.clock()
        async for namespace, mode, chunk in self.graph.astream(input, config, stream_mode=["messages", "updates"],
                                                              subgraphs=True, **kwargs):
            if self.clock() - last_flush >= self.flush_every_s:      # batch writes: not one per token
                await self._flush(run)
                last_flush = self.clock()
            if mode == "messages":
                message, meta = chunk
                text = _text(message)
                if text and type(message).__name__ == "AIMessageChunk":
                    if run.first_token_at is None:
                        run.first_token_at = self.clock()
                    run.emit("token", {"text": text, "node": meta.get("langgraph_node")})
                for key, value in (getattr(message, "usage_metadata", None) or {}).items():
                    if isinstance(value, int):
                        run.usage[key] = run.usage.get(key, 0) + value
            elif mode == "updates" and not namespace:
                for node in chunk:
                    if node != "__interrupt__":
                        run.emit("step", {"node": node})
        state = await self.graph.aget_state({"configurable": {"thread_id": run.thread_id}})
        if state.interrupts:
            run.interrupt = [item.value for item in state.interrupts]
            if run.first_token_at is None:       # the approval request is the first thing the user sees
                run.first_token_at = self.clock()
            self._finish(run, "interrupted")
            run.emit("interrupt", {"status": "interrupted", "interrupts": run.interrupt})
        else:
            messages = state.values.get("messages", [])
            run.answer = _text(messages[-1]) if messages else ""
            self._finish(run, "success")
            run.emit("end", {"status": "success", "answer": run.answer})

    def _finish(self, run: Run, status: str, error: str | None = None) -> None:
        run.status, run.error, run.ended_at = status, error, self.clock()

    async def _charge(self, run: Run) -> None:
        if self.model and run.usage:
            from mastery.pricing import estimate_cost

            run.cost_usd = estimate_cost(run.usage, self.model) or 0.0
        if run.cost_usd:
            if self.ledger is not None:
                self.ledger.charge(self._day(), run.user_id, run.cost_usd)
            await self.store.add_spend(self._day(), run.user_id, run.cost_usd)

    async def _flush(self, run: Run) -> None:
        if run.saved < len(run.events):
            end = len(run.events)
            await self.store.add_events(run.run_id, run.events[run.saved:end])
            run.saved = end

    @staticmethod
    def _from_store(data: dict[str, Any] | None) -> Run:
        """A read-only :class:`Run` rebuilt from the store (a run from before a restart)."""
        if data is None:
            raise KeyError("run not found")
        run = Run(data["run_id"], data["thread_id"], data["user_id"], status=data["status"],
                  answer=data.get("answer"), error=data.get("error"), interrupt=data.get("interrupt"),
                  usage=data.get("usage") or {}, cost_usd=data.get("cost_usd") or 0.0,
                  idempotency_key=data.get("idempotency_key"))
        run.saved = data.get("events", 0)
        return run

    # -- restarts -------------------------------------------------------------------------------
    async def recover(self) -> list[str]:
        """At startup: runs the store still shows as queued/running died with the old process.

        Mark them ``error`` with a final event, so clients following them get an ending instead of
        waiting forever. The thread's checkpoint is intact: the user can simply send the message again.
        """
        lost = []
        for data in await self.store.orphans():
            run = self._from_store(data)
            run.status, run.error = "error", "the service restarted during this run; please send it again"
            events = await self.store.get_events(run.run_id)
            run.events, run.saved = list(events), len(events)
            run.emit("error", {"status": "error", "message": run.error})
            await self._flush(run)
            await self.store.save_run(run.stored() | {"events": len(run.events)})
            lost.append(run.run_id)
        if self.ledger is not None:
            for user, usd in (await self.store.spend_totals(self._day())).items():
                self.ledger.charge(self._day(), user, usd)       # today's spend survives restarts
        return lost

    async def get(self, run_id: str) -> Run | None:
        """A run from memory, or rebuilt from the store (status and answer only) after a restart."""
        if run_id in self.runs:
            return self.runs[run_id]
        data = await self.store.get_run(run_id)
        return self._from_store(data) if data else None

    @staticmethod
    def _day() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # -- following, cancelling, reading ------------------------------------------------------
    async def follow(self, run_id: str, after: int = -1, heartbeat_s: float | None = None) -> AsyncIterator[Event | None]:
        """Yield the run's events with ``id > after``, then new ones as they come, until the run ends.

        With ``heartbeat_s``, yields ``None`` when nothing happened for that long, so the caller can
        send a keep-alive (or notice the client left).
        """
        if run_id not in self.runs:                    # from before a restart: replay what was stored
            for event in await self.store.get_events(run_id, after):
                yield event
            return
        run = self.runs[run_id]
        position = after + 1
        while True:
            while position < len(run.events):
                yield run.events[position]
                position += 1
            if run.done and position >= len(run.events):
                return
            run._changed.clear()
            if position < len(run.events):
                continue
            try:
                await asyncio.wait_for(run._changed.wait(), timeout=heartbeat_s)
            except asyncio.TimeoutError:
                yield None

    async def cancel(self, run_id: str) -> Run:
        """Cancel a queued or running run (no-op once it ended)."""
        run = self.runs.get(run_id) or await self.get(run_id)
        if run is None:
            raise KeyError(run_id)
        if not run.done and run.task is not None:
            if run.status == "queued":
                self._finish(run, "cancelled")
                run.emit("end", {"status": "cancelled"})
            run.task.cancel()
            try:
                await run.task
            except asyncio.CancelledError:
                pass
            await self._flush(run)                     # a task cancelled before it started never ran its finally
            await self.store.save_run(run.stored())
        return run

    async def shutdown(self, drain_s: float = 10.0) -> list[str]:
        """Graceful stop (SIGTERM): refuse new runs, let active ones finish for up to ``drain_s``,
        then end the rest as ``error`` with a clear message, saved, so clients know to send them again.
        Returns the ids of the runs that were cut off."""
        self.draining = True
        pending = [run for run in self.runs.values() if not run.done and run.task is not None]
        if pending and drain_s > 0:
            await asyncio.wait([run.task for run in pending], timeout=drain_s)
        cut = [run for run in pending if not run.done]
        for run in cut:
            self._finish(run, "error", error=SHUTDOWN_MESSAGE)
            run.emit("error", {"status": "error", "message": SHUTDOWN_MESSAGE})
            run.task.cancel()
            try:
                await run.task
            except asyncio.CancelledError:
                pass
            await self._flush(run)
            await self.store.save_run(run.stored())
        return [run.run_id for run in cut]

    async def wait(self, run_id: str) -> Run:
        """Wait until a run ends (tests and load tests)."""
        run = self.runs[run_id]
        if run.task is not None and not run.task.done():
            try:
                await asyncio.shield(run.task)
            except asyncio.CancelledError:
                if not run.task.cancelled():
                    raise
        return run

    @property
    def queued(self) -> int:
        """Runs waiting for a free slot."""
        return sum(run.status == "queued" for run in self.runs.values())

    def records(self) -> list[RunRecord]:
        """Finished runs as :class:`RunRecord` (for :func:`~mastery.service.slo.evaluate_slo`)."""
        return [run.record() for run in self.runs.values() if run.done]

    def stats(self) -> dict[str, Any]:
        statuses: dict[str, int] = {}
        for run in self.runs.values():
            statuses[run.status] = statuses.get(run.status, 0) + 1
        running = sum(run.status == "running" for run in self.runs.values())
        return {"runs": len(self.runs), "by_status": statuses, "running": running, "queued": self.queued,
                "max_concurrent": self.max_concurrent, "max_queue": self.max_queue}
