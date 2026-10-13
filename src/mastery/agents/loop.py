"""mastery.agents.loop: small helpers to run, inspect and display agent loops.

Introduced in Module 02 as ``mastery/agents.py``; moved here in Module 09 when
``mastery.agents`` became a package. ``from mastery.agents import ...`` still works. Everything here is plain Python over LangChain
messages, so it works the same with Groq, OpenAI, or the offline
``mastery.testing.ScriptedChatModel``.

- :func:`execute_tool_calls`: one "tools" step of the loop, written out
  (Lesson 02.02 builds it by hand first; this is the tested version).
- :func:`run_tool_loop`: the whole hand-written loop with a step limit.
- :func:`format_transcript` / :func:`agent_stats`: read an agent run at a glance.
- :func:`format_stream_part`: one readable line per ``agent.stream(..., version="v2")`` part.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool

__all__ = [
    "LoopLimitError",
    "agent_stats",
    "execute_tool_calls",
    "format_stream_part",
    "format_transcript",
    "run_tool_loop",
]


class LoopLimitError(RuntimeError):
    """The hand-written loop hit ``max_steps`` before the model stopped calling tools."""


def execute_tool_calls(message: AIMessage, tools: Sequence[BaseTool]) -> list[ToolMessage]:
    """Run every tool call in ``message`` and return one ``ToolMessage`` per call.

    Errors never raise: an unknown tool name, invalid arguments, or an exception
    inside the tool becomes a ``ToolMessage(status="error")`` that tells the model
    what went wrong, so it can correct itself (the same contract ``create_agent``
    uses for unknown tools and invalid arguments).

    Args:
        message: The model's reply (``AIMessage``) with ``tool_calls``.
        tools: The tools that were bound to the model.
    """
    by_name = {t.name: t for t in tools}
    results: list[ToolMessage] = []
    for call in message.tool_calls:
        tool = by_name.get(call["name"])
        if tool is None:
            results.append(ToolMessage(
                content=f"Error: {call['name']} is not a valid tool. Valid tools: {', '.join(by_name) or 'none'}.",
                tool_call_id=call["id"], name=call["name"], status="error"))
            continue
        try:
            # Passing the whole ToolCall (not just args) makes the tool return a ToolMessage
            # with the right tool_call_id, and keeps any artifact.
            output = tool.invoke(call)
        except Exception as exc:  # noqa: BLE001 - every failure must reach the model as data.
            output = ToolMessage(content=f"Error: {type(exc).__name__}: {exc}", tool_call_id=call["id"],
                                 name=call["name"], status="error")
        if not isinstance(output, ToolMessage):  # Tools returning Command etc. are agent-only.
            output = ToolMessage(content=str(output), tool_call_id=call["id"], name=call["name"])
        results.append(output)
    return results


def run_tool_loop(
    model: Any,
    tools: Sequence[BaseTool],
    messages: list[BaseMessage | dict[str, Any] | tuple[str, str]],
    *,
    max_steps: int = 6,
) -> list[BaseMessage]:
    """The ReAct-style loop by hand: model -> tools -> model ... until no tool calls.

    Args:
        model: A chat model with ``bind_tools`` (``get_model(...)`` or ``ScriptedChatModel``).
        tools: Tools to offer.
        messages: Conversation so far (messages, dicts or tuples).
        max_steps: Maximum model calls. Protects you from loops and runaway cost.

    Returns:
        The full message history, ending with the model's final ``AIMessage``.

    Raises:
        LoopLimitError: The model still wanted tools after ``max_steps`` calls.
    """
    from langchain_core.messages import convert_to_messages

    bound = model.bind_tools(tools)
    history = list(convert_to_messages(messages))
    for _ in range(max_steps):
        reply = bound.invoke(history)
        history.append(reply)
        if not reply.tool_calls:          # The stop condition of every agent loop.
            return history
        history.extend(execute_tool_calls(reply, tools))
    raise LoopLimitError(f"Stopped after {max_steps} model calls; the model kept calling tools.")


def _short(text: Any, max_chars: int) -> str:
    text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, default=str)
    text = " ".join(text.split())
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def format_transcript(messages: Iterable[BaseMessage], *, max_chars: int = 200) -> str:
    """A numbered, one-line-per-event view of an agent run.

    Example output::

        1. 👤 user      How many days until 2026-12-25?
        2. 🤖 model     → days_between(start='2026-10-12', end='2026-12-25')
        3. 🔧 tool      days_between: 74
        4. 🤖 model     There are 74 days left.
    """
    lines = []
    for number, message in enumerate(messages, start=1):
        if isinstance(message, SystemMessage):
            lines.append(f"{number}. ⚙️ system    {_short(message.text, max_chars)}")
        elif isinstance(message, HumanMessage):
            lines.append(f"{number}. 👤 user      {_short(message.text, max_chars)}")
        elif isinstance(message, AIMessage):
            calls = ", ".join(
                f"{c['name']}(" + ", ".join(f"{k}={v!r}" for k, v in c["args"].items()) + ")" for c in message.tool_calls
            )
            text = message.text
            body = (f"→ {calls}" if calls else "") + (("  " if calls and text else "") + _short(text, max_chars) if text else "")
            lines.append(f"{number}. 🤖 model     {body or '(empty reply)'}")
        elif isinstance(message, ToolMessage):
            flag = " ❌" if message.status == "error" else ""
            lines.append(f"{number}. 🔧 tool{flag}{' ' * (6 - len(flag))}{message.name or '?'}: {_short(message.content, max_chars)}")
        else:
            lines.append(f"{number}. {message.type:<10} {_short(message.content, max_chars)}")
    return "\n".join(lines)


def agent_stats(messages: Iterable[BaseMessage]) -> dict[str, Any]:
    """Count model calls, tool calls, tool errors and tokens in a run."""
    stats: dict[str, Any] = {"model_calls": 0, "tool_calls": 0, "tool_errors": 0, "tools_used": [],
                             "input_tokens": 0, "output_tokens": 0}
    for message in messages:
        if isinstance(message, AIMessage):
            stats["model_calls"] += 1
            stats["tool_calls"] += len(message.tool_calls)
            stats["tools_used"] += [c["name"] for c in message.tool_calls]
            usage = message.usage_metadata or {}
            stats["input_tokens"] += usage.get("input_tokens", 0)
            stats["output_tokens"] += usage.get("output_tokens", 0)
        elif isinstance(message, ToolMessage) and message.status == "error":
            stats["tool_errors"] += 1
    return stats


def format_stream_part(part: Mapping[str, Any], *, max_chars: int = 160) -> str | None:
    """Turn one ``version="v2"`` stream part into a readable line (or ``None`` to skip it).

    Handles ``updates`` (one line per new message, labelled with the node),
    ``custom`` (whatever the tool wrote), and ``messages`` token chunks (returns
    the raw text so you can ``print(..., end="")``; tool-call chunks are skipped,
    because the ``updates`` part shows the complete call).
    """
    kind, data = part.get("type"), part.get("data")
    if kind == "updates" and isinstance(data, Mapping):
        lines = []
        for node, update in data.items():
            for message in (update or {}).get("messages", []) if isinstance(update, Mapping) else []:
                line = format_transcript([message], max_chars=max_chars).split(". ", 1)[-1]
                lines.append(f"[{node}] {line}")
        return "\n".join(lines) or None
    if kind == "custom":
        return f"[progress] {_short(data, max_chars)}"
    if kind == "messages" and isinstance(data, tuple) and data:
        token = data[0]
        if isinstance(token, ToolMessage):
            return None
        return token.text or None
    return None
