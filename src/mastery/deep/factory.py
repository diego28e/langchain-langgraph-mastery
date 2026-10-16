"""``build_deep_agent()``: ``create_deep_agent`` with the course defaults. Introduced in Lesson 11.01.

Course defaults (Module 11 README, "Default model stack"):

* the model is always passed explicitly (relying on ``model=None`` is deprecated since 0.5.3),
  read from ``MASTERY_DEEP_MODEL`` / ``MASTERY_DEEP_SUBAGENT_MODEL``;
* a client-side rate limiter, so a free tier is not hit with bursts;
* per-run call budgets (``ModelCallLimitMiddleware`` / ``ToolCallLimitMiddleware``), so a confused
  agent cannot burn a day's quota;
* optional backups from ``MASTERY_FALLBACK_MODELS`` through ``ModelFallbackMiddleware``.
  ``create_deep_agent`` needs a real chat model (a ``.with_fallbacks()`` wrapper is rejected), so
  deep agents fall back in middleware, as the Deep Agents fault-tolerance docs show:
  https://docs.langchain.com/oss/python/deepagents/fault-tolerance
"""
from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any, Literal

from mastery.config import is_set
from mastery.models import PROVIDER_KEY_ENV

# VERIFIED 2026-10-16: listed under "Suggested models" on https://docs.langchain.com/oss/python/deepagents/models
DEFAULT_DEEP_MODEL = "google_genai:gemini-3.6-flash"
DeepRole = Literal["main", "subagent"]
_ROLE_ENV = {"main": "MASTERY_DEEP_MODEL", "subagent": "MASTERY_DEEP_SUBAGENT_MODEL"}


def deep_model_spec(role: DeepRole = "main") -> str:
    """The ``provider:model`` string for ``role`` (``.env`` first, then the course default)."""
    value = os.environ.get(_ROLE_ENV[role], "").strip()
    return value or DEFAULT_DEEP_MODEL


def _provider(spec: str) -> str:
    return spec.split(":", 1)[0] if ":" in spec else "groq"


def deep_key_ready(spec: str) -> bool:
    """True if the key for ``spec``'s provider is set (never prints it). Unknown providers: False."""
    names = PROVIDER_KEY_ENV.get(_provider(spec))
    if names is None:
        return False
    return not names or any(is_set(n) for n in names)


def _normalize(spec: str) -> str:
    return spec if ":" in spec else f"groq:{spec}"


def fallback_specs(primary: str | None = None) -> list[str]:
    """Backups from ``MASTERY_FALLBACK_MODELS`` whose key is set, minus the primary itself."""
    raw = os.environ.get("MASTERY_FALLBACK_MODELS", "")
    seen = {_normalize(primary)} if primary else set()
    out = []
    for item in (s.strip() for s in raw.split(",")):
        if not item:
            continue
        spec = _normalize(item)
        if spec in seen or not deep_key_ready(spec):
            continue
        seen.add(spec)
        out.append(spec)
    return out


def _init(spec: str, *, requests_per_second: float | None, **kwargs: Any) -> Any:
    from langchain.chat_models import init_chat_model

    if requests_per_second:
        from langchain_core.rate_limiters import InMemoryRateLimiter

        kwargs.setdefault("rate_limiter", InMemoryRateLimiter(
            requests_per_second=requests_per_second, check_every_n_seconds=0.1, max_bucket_size=1))
    if spec.startswith("groq:qwen/"):
        kwargs.setdefault("reasoning_format", "parsed")   # Groq: qwen + tools needs parsed/hidden reasoning
    return init_chat_model(spec, **kwargs)


def deep_model(role: DeepRole = "main", *, spec: str | None = None,
               requests_per_second: float | None = 0.25, **kwargs: Any) -> Any:
    """A chat model for a deep agent. ``requests_per_second=0.25`` = at most one call every 4 s.

    Pass ``requests_per_second=None`` to turn the limiter off. Extra kwargs go to ``init_chat_model``
    (``temperature``, ``timeout``, ``max_retries``, ``thinking_level`` for Gemini ...).
    """
    return _init(spec or deep_model_spec(role), requests_per_second=requests_per_second, **kwargs)


def fallback_middleware(primary: str | None = None, *, requests_per_second: float | None = 0.25) -> Any | None:
    """``ModelFallbackMiddleware`` over the usable ``MASTERY_FALLBACK_MODELS``, or None if there are none.

    It switches model on ANY model error (outage, 429, timeout), after the model's own retries.
    """
    specs = fallback_specs(primary)
    if not specs:
        return None
    from langchain.agents.middleware import ModelFallbackMiddleware

    models = [_init(s, requests_per_second=requests_per_second) for s in specs]
    return ModelFallbackMiddleware(*models)


def budget_middleware(model_calls: int = 25, tool_calls: int = 60) -> list[Any]:
    """Per-run caps (reset every invoke). ``exit_behavior="end"`` ends the run cleanly instead of raising."""
    from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

    return [ModelCallLimitMiddleware(run_limit=model_calls, exit_behavior="end"),
            ToolCallLimitMiddleware(run_limit=tool_calls, exit_behavior="continue")]


def build_deep_agent(model: Any = None, *, tools: Sequence[Any] = (), system_prompt: str | None = None,
                     middleware: Sequence[Any] = (), model_calls: int | None = 25, tool_calls: int | None = 60,
                     fallbacks: bool = True, **kwargs: Any) -> Any:
    """``create_deep_agent`` with an explicit model, call budgets and optional fallbacks.

    ``model``: a chat model, a ``provider:model`` string, or None for ``deep_model("main")``.
    Any other keyword (``subagents``, ``backend``, ``checkpointer``, ``interrupt_on`` ...) is passed through.
    """
    from deepagents import create_deep_agent

    primary_spec = model if isinstance(model, str) else None
    if model is None:
        primary_spec = deep_model_spec("main")
        model = deep_model("main")
    elif isinstance(model, str):
        model = deep_model(spec=model)
    stack = list(middleware)
    if model_calls is not None or tool_calls is not None:
        stack += budget_middleware(model_calls or 10_000, tool_calls or 10_000)
    if fallbacks:
        backup = fallback_middleware(primary_spec)
        if backup is not None:
            stack.append(backup)
    return create_deep_agent(model=model, tools=list(tools), system_prompt=system_prompt,
                             middleware=stack, **kwargs)


def run_stats(result: dict) -> dict[str, int]:
    """Model calls, tool calls and tokens of ONE agent's messages (subagent calls are not in them)."""
    from langchain_core.messages import AIMessage, ToolMessage

    messages = result.get("messages", [])
    ai = [m for m in messages if isinstance(m, AIMessage)]
    usage = [m.usage_metadata or {} for m in ai]
    return {
        "model_calls": len(ai),
        "tool_calls": sum(isinstance(m, ToolMessage) for m in messages),
        "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
        "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
        "files": len(result.get("files", {}) or {}),
    }


# --------------------------------------------------------------------------- backends and permissions (Lesson 11.04)
# Read AND write denied for secret-looking files anywhere. Put these rules FIRST: permissions are first-match-wins.
SECRET_PATTERNS: tuple[str, ...] = ("/**/.env", "/**/.env.*", "/**/*.pem", "/**/*.key", "/**/secrets/**")


def secret_deny_rules() -> list[Any]:
    """``FilesystemPermission`` rules that block reading or writing secret files (docs: Permissions)."""
    from deepagents import FilesystemPermission

    return [FilesystemPermission(operations=["read", "write"], paths=list(SECRET_PATTERNS), mode="deny")]


def course_backend(*, user_key: str = "user_id", reports: Any = None) -> Any:
    """The course layout: scratch files in state, ``/memories/`` per user in the store, ``/reports/`` routed.

    * ``/`` (default): ``StateBackend``: thread-scoped scratch (also where offloaded results go);
    * ``/memories/``: ``StoreBackend`` namespaced by ``runtime.context.<user_key>`` (needs ``store=`` and
      ``context_schema`` on the agent);
    * ``/reports/``: ``reports`` if given (e.g. ``FilesystemBackend(root_dir=..., virtual_mode=True)``), else state.
    """
    from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

    routes: dict[str, Any] = {
        "/memories/": StoreBackend(namespace=lambda rt: (str(getattr(rt.context, user_key)), "memories")),
    }
    if reports is not None:
        routes["/reports/"] = reports
    return CompositeBackend(default=StateBackend(), routes=routes)


# `**` in permission globs does NOT match dot-files or dot-folders (wcmatch without DOTGLOB, deepagents 0.7.26):
# a closing deny on "/**" leaves "/.env" and "/repo/.git/config" allowed. Add these patterns to catch-all rules.
DOTFILE_PATTERNS: tuple[str, ...] = ("/**/.*", "/**/.*/**")


def deny_everything_else(operations: Sequence[str] = ("read", "write")) -> Any:
    """A closing catch-all deny that really covers everything, dot-files included. Put it LAST."""
    from deepagents import FilesystemPermission

    return FilesystemPermission(operations=list(operations), paths=["/**", *DOTFILE_PATTERNS], mode="deny")
