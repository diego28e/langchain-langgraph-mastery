"""Evaluators for deep-agent runs (Lesson 11.11, Project 11).

A deep agent's answer is only part of the result. These functions check the other parts that
the final state holds: the **trajectory** (which tools, in which order), the **file state**
(what the agent wrote), **grounding** (every URL it cites was returned by a tool) and **cost**.
They are deterministic, cost nothing, and work on the dict that ``agent.invoke`` returns.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal

from mastery.mcp import check_sources, extract_urls

__all__ = ["check_case", "file_text", "forbidden_calls", "grounding", "subagents_called", "tool_calls",
           "trajectory", "trajectory_matches"]

Mode = Literal["exact", "ordered", "subset"]


def _messages(result: Mapping[str, Any]) -> list[Any]:
    return list(result.get("messages", []))


def tool_calls(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every tool call the (top-level) agent made, in order: ``[{"name", "args"}]``."""
    return [{"name": c["name"], "args": c.get("args", {})}
            for m in _messages(result) if getattr(m, "type", "") == "ai" for c in (getattr(m, "tool_calls", None) or [])]


def trajectory(result: Mapping[str, Any]) -> list[str]:
    """Tool names in call order (subagents' own calls stay inside their ``task``)."""
    return [c["name"] for c in tool_calls(result)]


def subagents_called(result: Mapping[str, Any]) -> list[str]:
    """``subagent_type`` of every ``task`` call, in order."""
    return [str(c["args"].get("subagent_type", "")) for c in tool_calls(result) if c["name"] == "task"]


def trajectory_matches(actual: Sequence[str], expected: Sequence[str], mode: Mode = "ordered") -> bool:
    """Compare a trajectory with a reference.

    * ``exact``: the same calls in the same order (brittle: use for short, fixed flows);
    * ``ordered``: ``expected`` appears in order inside ``actual``, extra calls allowed (the usual choice);
    * ``subset``: every expected tool was called at least once, in any order.
    """
    if mode == "exact":
        return list(actual) == list(expected)
    if mode == "subset":
        return set(expected) <= set(actual)
    if mode == "ordered":
        it = iter(actual)
        return all(any(a == e for a in it) for e in expected)
    raise ValueError(f"unknown mode {mode!r}")


def forbidden_calls(actual: Iterable[str], forbidden: Iterable[str]) -> list[str]:
    """The forbidden tools that were called (empty list = fine)."""
    banned = set(forbidden)
    return [name for name in actual if name in banned]


def file_text(result: Mapping[str, Any], path: str) -> str | None:
    """Content of an agent file in the final state (``StateBackend`` / ``files`` key), or None."""
    data = (result.get("files") or {}).get(path)
    if data is None:
        return None
    content = data.get("content") if isinstance(data, Mapping) else data
    return "\n".join(content) if isinstance(content, list) else str(content)


def grounding(text: str, result: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Split the URLs cited in ``text`` into (grounded, invented) against every tool result in the run."""
    seen = [u for m in _messages(result) if getattr(m, "type", "") == "tool"
            for u in extract_urls(m.content) + extract_urls(getattr(m, "artifact", None) or "")]
    return check_sources(extract_urls(text), seen)


def check_case(result: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, bool]:
    """Run the checks a case asks for. Keys present in ``case`` decide which checks run.

    ``expect_tools`` (+ ``mode``), ``forbid_tools``, ``file`` (+ ``file_contains``),
    ``grounded`` (True: every URL in ``file`` or the final answer must be grounded),
    ``max_model_calls``. The result has one bool per check plus ``passed``.
    """
    from mastery.deep.factory import run_stats

    path = trajectory(result)
    checks: dict[str, bool] = {}
    if "expect_tools" in case:
        checks["trajectory"] = trajectory_matches(path, case["expect_tools"], case.get("mode", "ordered"))
    if "forbid_tools" in case:
        checks["no_forbidden"] = not forbidden_calls(path, case["forbid_tools"])
    text = None
    if "file" in case:
        text = file_text(result, case["file"])
        checks["file"] = text is not None and all(s.lower() in text.lower() for s in case.get("file_contains", ()))
    if case.get("grounded"):
        if text is None:
            messages = _messages(result)
            text = str(messages[-1].content) if messages else ""
        cited, invented = grounding(text, result)
        checks["grounded"] = bool(cited) and not invented
    if "max_model_calls" in case:
        checks["budget"] = run_stats(result)["model_calls"] <= case["max_model_calls"]
    checks["passed"] = all(checks.values())
    return checks
