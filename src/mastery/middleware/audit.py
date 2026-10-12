"""``AuditLogMiddleware``: one redacted JSON line per agent event.

An audit log answers "what did the agent do, with which tool, when, and was it
allowed?" after the fact. It is separate from tracing (LangSmith): you own the
file, it is append-only, and nothing in it is raw PII because every string goes
through :func:`mastery.middleware.redaction.redact_obj` first.

Events: ``run_start``, ``model_call``, ``model_error``, ``tool_call``,
``tool_error``, ``run_end``, plus anything you add with :meth:`record`
(for example ``injection_blocked``).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from mastery.middleware.redaction import redact_obj

__all__ = ["AuditLogMiddleware", "read_audit_log"]


def _thread_id(runtime: Any) -> str | None:
    info = getattr(runtime, "execution_info", None)
    tid = getattr(info, "thread_id", None)
    if tid:
        return str(tid)
    config = getattr(runtime, "config", None) or {}
    return (config.get("configurable") or {}).get("thread_id")


def _model_name(model: Any) -> str:
    return str(getattr(model, "model_name", None) or getattr(model, "model", None) or type(model).__name__)


def _preview(text: Any, n: int = 120) -> str:
    text = text if isinstance(text, str) else str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


class AuditLogMiddleware(AgentMiddleware):
    """Record agent events, redacted, in memory and (optionally) in a JSONL file.

    Args:
        path: File to append to (created with its folder). ``None`` = memory only.
        redact: Function applied to every event before it is stored.
        clock: Returns a timestamp (seconds); injectable for tests.

    Attributes:
        events: Every event of this middleware instance, oldest first.

    Example:
        >>> audit = AuditLogMiddleware()            # memory only
        >>> audit.record("injection_blocked", source="e-104", signals=["override"])["event"]
        'injection_blocked'
    """

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        redact: Callable[[Any], Any] = redact_obj,
        clock: Callable[[], float] = time.time,
    ) -> None:
        super().__init__()
        self.path = Path(path) if path is not None else None
        self.redact = redact
        self.clock = clock
        self.events: list[dict[str, Any]] = []

    # --- public -------------------------------------------------------------
    def record(self, event: str, **fields: Any) -> dict[str, Any]:
        """Store one event (redacted) and return it."""
        entry = self.redact({"ts": round(self.clock(), 3), "event": event, **fields})
        self.events.append(entry)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return entry

    def of(self, event: str) -> list[dict[str, Any]]:
        """All stored events with this name."""
        return [e for e in self.events if e["event"] == event]

    # --- hooks --------------------------------------------------------------
    def before_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        last = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
        self.record("run_start", thread_id=_thread_id(runtime),
                    user=_preview(last.content) if last is not None else None)
        return None

    def _model_event(self, request: Any, response: Any, start: float) -> None:
        messages = getattr(response, "result", None) or []
        ai = next((m for m in messages if isinstance(m, AIMessage)), None)
        usage = (getattr(ai, "usage_metadata", None) or {}) if ai is not None else {}
        self.record("model_call", thread_id=_thread_id(request.runtime), model=_model_name(request.model),
                    n_messages=len(request.messages), tools_offered=len(request.tools),
                    tool_calls=[c["name"] for c in (ai.tool_calls if ai is not None else [])],
                    tokens=usage.get("total_tokens"), ms=round((time.perf_counter() - start) * 1000, 1))

    def _model_error(self, request: Any, error: Exception) -> None:
        self.record("model_error", thread_id=_thread_id(request.runtime), model=_model_name(request.model),
                    error=type(error).__name__)

    def _tool_event(self, request: Any, result: Any, start: float) -> None:
        call = request.tool_call
        status = getattr(result, "status", "success") if isinstance(result, ToolMessage) else "command"
        self.record("tool_call", thread_id=_thread_id(getattr(request, "runtime", None)), tool=call["name"],
                    args=call.get("args"), status=status, ms=round((time.perf_counter() - start) * 1000, 1))

    def _tool_error(self, request: Any, error: Exception) -> None:
        call = request.tool_call
        self.record("tool_error", thread_id=_thread_id(getattr(request, "runtime", None)), tool=call["name"],
                    args=call.get("args"), error=type(error).__name__)

    def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        start = time.perf_counter()
        try:
            response = handler(request)
        except Exception as error:
            self._model_error(request, error)
            raise
        self._model_event(request, response, start)
        return response

    async def awrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        """Async version (agents run with ``ainvoke``, e.g. with MCP tools in Module 05)."""
        start = time.perf_counter()
        try:
            response = await handler(request)
        except Exception as error:
            self._model_error(request, error)
            raise
        self._model_event(request, response, start)
        return response

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        start = time.perf_counter()
        try:
            result = handler(request)
        except Exception as error:
            self._tool_error(request, error)
            raise
        self._tool_event(request, result, start)
        return result

    async def awrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        """Async version of :meth:`wrap_tool_call`."""
        start = time.perf_counter()
        try:
            result = await handler(request)
        except Exception as error:
            self._tool_error(request, error)
            raise
        self._tool_event(request, result, start)
        return result

    def after_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        last = state["messages"][-1] if state["messages"] else None
        self.record("run_end", thread_id=_thread_id(runtime), messages=len(state["messages"]),
                    final=_preview(getattr(last, "content", "")) if last is not None else None)
        return None


def read_audit_log(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL audit file back into a list of dicts (missing file -> ``[]``)."""
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
