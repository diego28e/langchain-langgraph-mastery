"""Count what a multi-agent pattern costs: model calls, tokens and wall-clock time, per agent.

The multi-agent docs compare patterns by *model calls* and *tokens*; this callback measures
both on your own runs. Pass it in the config of the OUTER invoke; callbacks propagate into
subagents called inside tools and into subgraph nodes, so one meter sees every model call::

    meter = UsageMeter()
    with meter:                                   # times the block
        app.invoke(inputs, {"callbacks": [meter], "configurable": {"thread_id": "t1"}})
    meter.summary()   # {'model_calls': 3, 'input_tokens': ..., 'seconds': ...}

Agents are told apart by the ``lc_agent_name`` metadata that ``create_agent(name=...)`` sets.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, Self

from langchain_core.callbacks import BaseCallbackHandler

__all__ = ["UsageMeter"]


class UsageMeter(BaseCallbackHandler):
    """Thread-safe callback: model calls and token usage, in total and per agent name."""

    raise_error = False

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._names: dict[Any, str] = {}
        self._started: float | None = None
        self.reset()

    # --- bookkeeping ---------------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self.model_calls = 0
            self.input_tokens = 0
            self.output_tokens = 0
            self.seconds = 0.0
            self.by_agent: dict[str, dict[str, int]] = defaultdict(
                lambda: {"model_calls": 0, "input_tokens": 0, "output_tokens": 0})
            self._names.clear()

    def __enter__(self) -> Self:
        self._started = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._started is not None:
            self.seconds += time.perf_counter() - self._started
            self._started = None

    # --- callbacks -----------------------------------------------------------
    def on_chat_model_start(self, serialized: Any, messages: Any, *, run_id: Any,
                            metadata: dict | None = None, **kwargs: Any) -> None:
        meta = metadata or {}
        name = str(meta.get("lc_agent_name") or meta.get("langgraph_node") or "model")
        with self._lock:
            self._names[run_id] = name
            self.model_calls += 1
            self.by_agent[name]["model_calls"] += 1

    def on_llm_end(self, response: Any, *, run_id: Any, **kwargs: Any) -> None:
        usage: dict = {}
        for generations in getattr(response, "generations", []) or []:
            for gen in generations:
                message = getattr(gen, "message", None)
                usage = getattr(message, "usage_metadata", None) or usage
        with self._lock:
            name = self._names.pop(run_id, "model")
            for key in ("input_tokens", "output_tokens"):
                value = int(usage.get(key, 0) or 0)
                setattr(self, key, getattr(self, key) + value)
                self.by_agent[name][key] += value

    # --- reading -------------------------------------------------------------
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def summary(self, digits: int = 2) -> dict[str, Any]:
        return {"model_calls": self.model_calls, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "total_tokens": self.total_tokens,
                "seconds": round(self.seconds, digits)}

    def agents(self) -> dict[str, dict[str, int]]:
        """Per-agent counts, in first-seen order."""
        return {name: dict(counts) for name, counts in self.by_agent.items()}
