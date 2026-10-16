"""Fault injection and retry predicates for resilience drills (Lesson 12.02).

``flaky`` turns a scripted reply into one that fails like a real provider some of the time
(seeded, so a drill is repeatable). ``transient_only`` is the ``retry_on`` predicate for
``ModelRetryMiddleware``: its default retries every exception except non-retryable
``ModelError``s, so a provider SDK's 401 or 400 is retried too, wasting time and quota.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from langchain_core.exceptions import ModelAPIError, ModelRateLimitError, ModelTimeoutError

from mastery.models import is_transient

__all__ = ["flaky", "transient_only"]

_ERRORS = {"rate_limit": ModelRateLimitError, "timeout": ModelTimeoutError, "server": ModelAPIError}


def flaky(reply: Any, *, fail_rate: float, seed: int = 0, kind: str = "rate_limit",
          error: type[BaseException] | None = None) -> Callable[[list[Any]], Any]:
    """A ``ScriptedChatModel`` response that raises ``fail_rate`` of the time, else returns ``reply``.

    Args:
        reply: What a successful call returns (str, AIMessage or a callable of the messages).
        fail_rate: Probability of failure per call (0–1).
        seed: Random seed (each ``flaky`` has its own generator, so runs are repeatable).
        kind: ``rate_limit``, ``timeout`` or ``server`` (LangChain's standard exceptions).
        error: Raise this exception class instead (e.g. an auth error, to test "don't retry").
    """
    rng = random.Random(seed)
    exc = error or _ERRORS[kind]

    def respond(messages: list[Any]) -> Any:
        if rng.random() < fail_rate:
            raise exc(f"injected {exc.__name__} failure")
        return reply(messages) if callable(reply) else reply

    return respond


def transient_only(error: BaseException) -> bool:
    """Retry timeouts, connection errors, 429s and 5xx; never auth, permission or bad requests."""
    return is_transient(error)
