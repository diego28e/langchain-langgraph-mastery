"""The Project 09 Orbita Cloud support desk, wired for the service (Lessons 12.04-12.09).

``support_manager(settings)`` is the ``build_manager`` that :func:`mastery.service.app.create_app` calls
at startup. DEMO mode uses the rule-based offline model (no key, no cost); LIVE uses Groq
(``MASTERY_MODEL_FAST``) with a client-side rate limiter. Each run acts as the signed-in customer
(``SupportContext``), so a customer can't touch another customer's invoices, and refunds above
the threshold pause for a manager's approval (``interrupt``).
"""
from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mastery.service.budgets import CostBudget, SpendLedger, estimate_request_cost
from mastery.service.runs import RunManager
from mastery.service.settings import ServiceSettings


def slow(model: Any, delay_s: float) -> Any:
    """Make an offline model wait ``delay_s`` (simulated model latency, labelled as such) before each async call.

    The wait is ``await asyncio.sleep``, so many slow runs share one event loop, as real async
    provider clients do. Sync calls (``invoke``) are not delayed.
    """
    if delay_s <= 0:
        return model
    base = type(model)

    class SlowModel(base):  # type: ignore[misc, valid-type]
        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001, ANN202
            await asyncio.sleep(delay_s)
            return self._generate(messages, stop=stop, **kwargs)

        async def _astream(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001, ANN202
            await asyncio.sleep(delay_s)
            for chunk in self._stream(messages, stop=stop, **kwargs):
                yield chunk

    SlowModel.__name__ = f"Slow{base.__name__}"
    model.__class__ = SlowModel
    return model


class SimulatedOutage(RuntimeError):
    """Raised by :func:`faulty` models: a provider error injected on purpose (incident drills, Lesson 12.07)."""


def faulty(model: Any, fail_rate: float, rng: random.Random) -> Any:
    """Make an offline model fail ``fail_rate`` of its async calls with :class:`SimulatedOutage`."""
    if fail_rate <= 0:
        return model
    base = type(model)

    class FaultyModel(base):  # type: ignore[misc, valid-type]
        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001, ANN202
            if rng.random() < fail_rate:
                raise SimulatedOutage("simulated provider outage (HTTP 503)")
            return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)

        async def _astream(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001, ANN202
            if rng.random() < fail_rate:
                raise SimulatedOutage("simulated provider outage (HTTP 503)")
            async for chunk in super()._astream(messages, stop=stop, run_manager=run_manager, **kwargs):
                yield chunk

    FaultyModel.__name__ = f"Faulty{base.__name__}"
    model.__class__ = FaultyModel
    return model


def support_graph(mode: str = "demo", *, checkpointer: Any = None, delay_s: float = 0.0,
                  fail_rate: float = 0.0, seed: int = 0) -> tuple[Any, Any]:
    """Return ``(graph, desk)``: the handoffs desk with an offline or a Groq model.

    ``fail_rate`` (DEMO only) makes that share of model calls fail, for incident drills (Lesson 12.07).
    """
    from langgraph.checkpoint.memory import InMemorySaver

    from mastery.agents.support import SupportDesk, build_handoffs_desk, make_support_tools, offline_model

    desk = SupportDesk.load()
    if mode == "live":
        from langchain_core.rate_limiters import InMemoryRateLimiter

        from mastery.models import get_model

        limiter = InMemoryRateLimiter(requests_per_second=0.4, check_every_n_seconds=0.1, max_bucket_size=2)

        def model_for(role: str) -> Any:
            return get_model("fast", max_tokens=600, rate_limiter=limiter)
    else:
        rng = random.Random(seed)

        def model_for(role: str) -> Any:
            return faulty(slow(offline_model(role), delay_s), fail_rate, rng)
    graph = build_handoffs_desk(model_for, make_support_tools(desk), checkpointer=checkpointer or InMemorySaver())
    return graph, desk


def support_manager(settings: ServiceSettings, *, checkpointer: Any = None, delay_s: float = 0.0,
                    store: Any = None, fail_rate: float | None = None, seed: int = 0) -> RunManager:
    """The :class:`RunManager` for the desk, with the cost budget from ``settings`` (state in memory by default)."""
    from mastery.agents.support import SupportContext
    from mastery.config import load_settings

    fail_rate = settings.demo_fail_rate if fail_rate is None else fail_rate      # ignored in LIVE mode
    graph, desk = support_graph(settings.mode, checkpointer=checkpointer, delay_s=delay_s, fail_rate=fail_rate, seed=seed)
    model = load_settings().model_fast
    ledger = SpendLedger(CostBudget(settings.budget_per_request_usd, settings.budget_per_user_day_usd,
                                    settings.budget_global_day_usd))

    def estimate(graph_input: Any) -> float:
        # Upper bound: ~4 characters per token, plus the prompts and tool schemas resent on each of
        # about 4 model calls, plus the output cap. Charged with real usage after the run.
        text = str(graph_input)
        return estimate_request_cost(model, 4 * (len(text) // 4 + 1500), 4 * 600)

    manager = RunManager(graph, max_concurrent=settings.max_concurrent, max_queue=settings.max_queue,
                         timeout_s=settings.run_timeout_s, context_for=lambda run: SupportContext(run.user_id),
                         ledger=ledger, estimate=estimate, model=model, store=store)
    manager.desk = desk            # exposed for tests and the notebook (refunds issued, events)
    return manager


@asynccontextmanager
async def durable_support_manager(settings: ServiceSettings, *, delay_s: float = 0.0) -> AsyncIterator[RunManager]:
    """The desk with durable state from ``settings.database_url`` (memory when unset).

    Opens the LangGraph checkpointer and the service store on the same database, creates their
    tables, and closes both at shutdown. ``create_app(durable_support_manager)`` uses it in the lifespan.
    """
    from mastery.service.store import open_checkpointer, open_store

    url = settings.database()
    async with open_checkpointer(url) as checkpointer, open_store(url) as store:
        yield support_manager(settings, checkpointer=checkpointer, delay_s=delay_s, store=store)
