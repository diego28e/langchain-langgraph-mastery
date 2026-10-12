"""``TokenBudgetMiddleware``: stop an agent before it spends more tokens than you allow.

``ModelCallLimitMiddleware`` counts *calls*; a single call with a huge context can
still be expensive. This guard counts *tokens*, per run and (with a checkpointer)
per thread, and ends the run politely, or raises, before the next model call would
cross the budget.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.messages.utils import count_tokens_approximately
from typing_extensions import NotRequired

__all__ = ["BudgetState", "TokenBudgetExceededError", "TokenBudgetMiddleware"]


class BudgetState(AgentState):
    """Agent state plus the two counters this middleware keeps."""

    budget_run_tokens: NotRequired[int]
    budget_thread_tokens: NotRequired[int]


class TokenBudgetExceededError(RuntimeError):
    """Raised when ``exit_behavior="error"`` and the next call would exceed the budget."""


def _used(message: BaseMessage, counter: Callable[[Sequence[BaseMessage]], int], prompt: int) -> int:
    usage = getattr(message, "usage_metadata", None) or {}
    total = usage.get("total_tokens")
    return int(total) if total else prompt + counter([message])


class TokenBudgetMiddleware(AgentMiddleware[BudgetState]):
    """End (or fail) a run before the next model call would cross a token budget.

    Before each model call it estimates the prompt size of ``state["messages"]``.
    If tokens already used + that estimate would exceed a limit, the run ends with
    an explanatory ``AIMessage`` (``exit_behavior="end"``) or raises
    :class:`TokenBudgetExceededError` (``"error"``). After each call it adds the
    provider's ``usage_metadata.total_tokens`` (or the estimate, if missing).

    Args:
        run_limit: Max tokens per ``invoke`` (one user turn). ``None`` = no limit.
        thread_limit: Max tokens across a whole thread (needs a checkpointer).
        exit_behavior: ``"end"`` (default) or ``"error"``.
        token_counter: Estimates tokens for a list of messages.

    Example:
        >>> guard = TokenBudgetMiddleware(run_limit=4_000)
    """

    state_schema = BudgetState

    def __init__(
        self,
        *,
        run_limit: int | None = None,
        thread_limit: int | None = None,
        exit_behavior: Literal["end", "error"] = "end",
        token_counter: Callable[[Sequence[BaseMessage]], int] = count_tokens_approximately,
    ) -> None:
        super().__init__()
        if run_limit is None and thread_limit is None:
            raise ValueError("Set run_limit, thread_limit, or both.")
        if exit_behavior not in ("end", "error"):
            raise ValueError("exit_behavior must be 'end' or 'error'.")
        self.run_limit = run_limit
        self.thread_limit = thread_limit
        self.exit_behavior = exit_behavior
        self.token_counter = token_counter
        self._last_prompt = 0

    def before_agent(self, state: BudgetState, runtime: Any) -> dict[str, Any] | None:
        return {"budget_run_tokens": 0}

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: BudgetState, runtime: Any) -> dict[str, Any] | None:
        prompt = self.token_counter(state["messages"])
        self._last_prompt = prompt
        run_used = state.get("budget_run_tokens", 0)
        thread_used = state.get("budget_thread_tokens", 0)
        over = []
        if self.run_limit is not None and run_used + prompt > self.run_limit:
            over.append(f"run {run_used} + ~{prompt} > {self.run_limit}")
        if self.thread_limit is not None and thread_used + prompt > self.thread_limit:
            over.append(f"thread {thread_used} + ~{prompt} > {self.thread_limit}")
        if not over:
            return None
        reason = "Token budget reached (" + "; ".join(over) + " tokens)."
        if self.exit_behavior == "error":
            raise TokenBudgetExceededError(reason)
        return {"messages": [AIMessage(f"{reason} I stopped before calling the model again.")], "jump_to": "end"}

    def after_model(self, state: BudgetState, runtime: Any) -> dict[str, Any] | None:
        spent = _used(state["messages"][-1], self.token_counter, self._last_prompt)
        return {
            "budget_run_tokens": state.get("budget_run_tokens", 0) + spent,
            "budget_thread_tokens": state.get("budget_thread_tokens", 0) + spent,
        }
