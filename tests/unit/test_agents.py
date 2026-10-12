"""Tests for mastery.agents and mastery.testing (Module 02). Offline: scripted models only."""

from __future__ import annotations

import warnings

import pytest
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel

from mastery.agents import (
    LoopLimitError, agent_stats, execute_tool_calls, format_stream_part, format_transcript, run_tool_loop,
)
from mastery.testing import ScriptExhaustedError, ScriptedChatModel
from mastery.tools import calculator


def call(name: str, args: dict, call_id: str = "c1") -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])


@tool
def explode(x: int) -> str:
    """Always fails."""
    raise RuntimeError("database is down")


# --- ScriptedChatModel ----------------------------------------------------------
def test_scripted_model_replays_and_records() -> None:
    model = ScriptedChatModel(responses=["one", lambda msgs: f"saw {len(msgs)} messages"])
    assert model.bind_tools([calculator], tool_choice="any") is model
    assert model.bound_tools == ["calculator"] and model.tool_choice == "any"
    assert model.invoke("hi").content == "one"
    assert model.invoke([HumanMessage("a"), HumanMessage("b")]).content == "saw 2 messages"
    with pytest.raises(ScriptExhaustedError):
        model.invoke("again")
    model.reset()
    assert model.invoke("hi").content == "one"


def test_scripted_model_streams_tool_call_chunks_then_text() -> None:
    model = ScriptedChatModel(responses=[call("calculator", {"expression": "1+1"})])
    chunks = list(model.stream("x"))
    assert chunks[0].tool_call_chunks[0]["name"] == "calculator"
    model = ScriptedChatModel(responses=["two words"])
    assert "".join(c.content for c in model.stream("x")) == "two words"


# --- hand-written loop ------------------------------------------------------------
def test_execute_tool_calls_turns_every_failure_into_an_error_message() -> None:
    message = AIMessage("", tool_calls=[
        {"name": "calculator", "args": {"expression": "6*7"}, "id": "a"},
        {"name": "nope", "args": {}, "id": "b"},
        {"name": "calculator", "args": {"wrong": 1}, "id": "c"},
        {"name": "explode", "args": {"x": 1}, "id": "d"},
    ])
    results = execute_tool_calls(message, [calculator, explode])
    assert [r.tool_call_id for r in results] == ["a", "b", "c", "d"]
    assert results[0].content == "42" and results[0].status == "success"
    assert [r.status for r in results[1:]] == ["error", "error", "error"]
    assert "not a valid tool" in results[1].content and "database is down" in results[3].content


def test_run_tool_loop_stops_when_the_model_stops_calling_tools() -> None:
    model = ScriptedChatModel(responses=[call("calculator", {"expression": "2340*0.175"}), "It is 409.5."])
    history = run_tool_loop(model, [calculator], [("user", "17.5% of 2340?")])
    assert [type(m).__name__ for m in history] == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
    assert history[2].content == "409.5"


def test_run_tool_loop_has_a_step_limit() -> None:
    model = ScriptedChatModel(responses=[call("calculator", {"expression": "1+1"}, f"c{i}") for i in range(5)])
    with pytest.raises(LoopLimitError):
        run_tool_loop(model, [calculator], [("user", "loop")], max_steps=3)


# --- with create_agent ---------------------------------------------------------------
def test_scripted_model_drives_create_agent_with_structured_output() -> None:
    class Answer(BaseModel):
        value: float

    model = ScriptedChatModel(responses=[call("calculator", {"expression": "3*7"}), call("Answer", {"value": 21}, "c2")])
    agent = create_agent(model, tools=[calculator], response_format=ToolStrategy(Answer))
    result = agent.invoke({"messages": [{"role": "user", "content": "3*7"}]})
    assert result["structured_response"] == Answer(value=21)
    assert model.bound_tools == ["calculator", "Answer"] and model.tool_choice == "any"


def test_transcript_stats_and_stream_lines() -> None:
    model = ScriptedChatModel(responses=[call("calculator", {"expression": "2+2"}), "4."])
    agent = create_agent(model, tools=[calculator])
    parts = list(agent.stream({"messages": [{"role": "user", "content": "2+2?"}]},
                              stream_mode=["updates", "messages"], version="v2"))
    lines = [line for p in parts if (line := format_stream_part(p))]
    assert any(line.startswith("[model]") and "calculator(" in line for line in lines)
    assert any(line.startswith("[tools]") and ": 4" in line for line in lines)

    model.reset()
    messages = create_agent(model, tools=[calculator]).invoke({"messages": [("user", "2+2?")]})["messages"]
    text = format_transcript(messages)
    assert "👤 user" in text and "→ calculator(expression='2+2')" in text and "🔧 tool" in text
    stats = agent_stats(messages)
    assert stats["model_calls"] == 2 and stats["tool_calls"] == 1 and stats["tools_used"] == ["calculator"]
    assert format_stream_part({"type": "custom", "data": "50% done"}) == "[progress] 50% done"
    assert format_stream_part({"type": "messages", "data": (ToolMessage("x", tool_call_id="1"), {})}) is None


def test_runtime_exceptions_in_tools_crash_the_agent_by_default() -> None:
    """Documented v1 behavior (Lesson 02.04): ToolNode returns invalid-argument errors to the
    model, but an exception raised inside the tool propagates unless you add error handling."""
    model = ScriptedChatModel(responses=[call("explode", {"x": 1}), "unreachable"])
    with warnings.catch_warnings(), pytest.raises(RuntimeError, match="database is down"):
        warnings.simplefilter("ignore")
        create_agent(model, tools=[explode]).invoke({"messages": [("user", "go")]})


def test_scripted_model_repeat_last_simulates_a_stuck_model():
    from mastery.testing import ScriptedChatModel

    model = ScriptedChatModel(responses=["again"], repeat_last=True)
    assert [model.invoke("x").content for _ in range(3)] == ["again"] * 3
