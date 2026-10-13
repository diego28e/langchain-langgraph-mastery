"""Tests for the Module 09 multi-agent helpers (mastery.agents.*). Offline: scripted models only."""
from __future__ import annotations

import pytest
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import mastery.agents as agents_pkg
from mastery.agents import (
    Specialist,
    StepState,
    UsageMeter,
    handoff_graph,
    handoff_tool,
    step_middleware,
    step_tool,
    subagent_tool,
    task_tool,
)
from mastery.agents.support import (
    REFUND_THRESHOLD,
    SupportDesk,
    build_custom_desk,
    build_handoffs_desk,
    build_refund_workflow,
    build_router_desk,
    build_single_agent_baseline,
    build_single_agent_desk,
    build_skills_desk,
    build_subagents_desk,
    detect_intents,
    evaluate,
    load_conversations,
    make_skills,
    make_support_tools,
    offline_model,
    parse_refund,
    run_conversation,
    score,
    split_by_intent,
)
from mastery.testing import ScriptedChatModel


def call(name: str, args: dict | None = None, i: int = 0) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": f"c{i}_{name}", "type": "tool_call"}])


def cfg(thread: str, *callbacks) -> dict:
    return {"configurable": {"thread_id": thread}, "callbacks": list(callbacks)}


@pytest.fixture
def desk() -> SupportDesk:
    return SupportDesk.load()


@pytest.fixture
def tools(desk: SupportDesk) -> dict:
    return make_support_tools(desk)


# --------------------------------------------------------------------------- package
def test_module02_api_still_importable_from_package():
    for name in ("run_tool_loop", "execute_tool_calls", "format_transcript", "agent_stats",
                 "format_stream_part", "LoopLimitError"):
        assert hasattr(agents_pkg, name)
    assert agents_pkg.__file__.replace("\\", "/").endswith("mastery/agents/__init__.py")


# --------------------------------------------------------------------------- subagents
def test_subagent_tool_query_vs_history_context():
    seen: list[str] = []

    def echo(messages):
        seen.append(messages[-1].text)
        return "sub done"

    sub = create_agent(ScriptedChatModel(responses=[echo], repeat_last=True), tools=[], name="sub")
    for context in ("query", "history"):
        t = subagent_tool(sub, name="helper", description="Helps.", context=context)
        boss = create_agent(ScriptedChatModel(responses=[call("helper", {"query": "do X"}), "ok"]),
                            tools=[t], name="boss")
        out = boss.invoke({"messages": [HumanMessage("I am C-1001, please do X")]})
        assert out["messages"][-1].text == "ok"
        assert out["messages"][-2].text == "sub done"
    assert seen[0] == "do X"
    assert "user: I am C-1001" in seen[1] and seen[1].endswith("Your task: do X")


def test_task_tool_enum_and_dispatch():
    sub = create_agent(ScriptedChatModel(responses=["billing says hi"]), tools=[], name="billing")
    t = task_tool({"billing": (sub, "Money things.")})
    schema = t.args_schema.model_json_schema()
    assert "billing" in str(schema) and "Money things." in t.description
    assert t.invoke({"agent_name": "billing", "description": "hello"}) == "billing says hi"
    with pytest.raises(Exception):  # noqa: B017 - pydantic rejects unknown agent names
        t.invoke({"agent_name": "sales", "description": "hello"})


def test_interrupt_in_subagent_pauses_outer_and_resumes(desk, tools):
    app = build_subagents_desk(offline_model, tools, checkpointer=InMemorySaver())
    config = cfg("refund")
    out = app.invoke({"messages": [HumanMessage("I'm C-1002, refund $199 for INV-2001")]}, config)
    assert out["__interrupt__"][0].value["type"] == "refund_approval"
    out = app.invoke(Command(resume="approve"), config)
    assert "Refunded $199.00" in out["messages"][-1].text
    assert desk.tools_called() == ["issue_refund"]          # logged once, after the interrupt
    assert desk.refunds[0]["approved_by"] == "billing manager"


# --------------------------------------------------------------------------- metrics
def test_usage_meter_sees_subagent_calls():
    sub = create_agent(ScriptedChatModel(responses=["inner"]), tools=[], name="inner")
    t = subagent_tool(sub, name="inner_agent", description="Inner.")
    boss = create_agent(ScriptedChatModel(responses=[call("inner_agent", {"query": "q"}), "outer"]),
                        tools=[t], name="outer")
    meter = UsageMeter()
    with meter:
        boss.invoke({"messages": [HumanMessage("hi")]}, cfg("m", meter))
    assert meter.model_calls == 3
    assert meter.agents()["outer"]["model_calls"] == 2 and meter.agents()["inner"]["model_calls"] == 1
    assert meter.total_tokens > 0 and meter.summary()["seconds"] >= 0
    meter.reset()
    assert meter.model_calls == 0 and meter.agents() == {}


# --------------------------------------------------------------------------- handoffs
def _two_agent_graph(carry: str):
    @tool
    def lookup(x: str) -> str:
        """Look up."""
        return f"found {x}"

    a = create_agent(ScriptedChatModel(responses=[call("lookup", {"x": "1"}, 1), call("transfer_to_b", {}, 2)]),
                     tools=[lookup, handoff_tool("b", carry=carry)], name="a")

    def b_policy(messages):
        names = [m.name for m in messages if isinstance(m, ToolMessage)]
        return f"b saw {names}"

    b = create_agent(ScriptedChatModel(responses=[b_policy], repeat_last=True), tools=[], name="b")
    return handoff_graph({"a": a, "b": b}, entry="a", checkpointer=InMemorySaver())


def test_handoff_carry_last_vs_turn():
    last = _two_agent_graph("last").invoke({"messages": [HumanMessage("go")]}, cfg("l"))
    turn = _two_agent_graph("turn").invoke({"messages": [HumanMessage("go")]}, cfg("t"))
    assert last["messages"][-1].text == "b saw ['transfer_to_b']"
    assert turn["messages"][-1].text == "b saw ['lookup', 'transfer_to_b']"
    assert turn["active_agent"] == "b"


def test_handoff_graph_next_turn_starts_at_active_agent(desk, tools):
    app = build_handoffs_desk(offline_model, tools, checkpointer=InMemorySaver())
    meter = UsageMeter()
    config = cfg("h", meter)
    app.invoke({"messages": [HumanMessage("I'm C-1001, list my invoices")]}, config)
    assert list(meter.agents()) == ["triage", "billing"]
    meter.reset()
    out = app.invoke({"messages": [HumanMessage("Refund INV-1003 ($49), duplicate")]}, config)
    assert list(meter.agents()) == ["billing"]               # no triage on the second turn
    assert "Refunded $49.00" in out["messages"][-1].text


def test_step_middleware_swaps_prompt_and_tools():
    @tool
    def alpha() -> str:
        """Alpha."""
        return "a"

    seen: list[tuple[str, list[str]]] = []
    model = ScriptedChatModel(responses=[call("transfer_to_two"), "done"])
    original = model._next

    def spy(messages):
        system = next(m for m in messages if isinstance(m, SystemMessage)).text
        seen.append((system, list(model.bound_tools)))
        return original(messages)

    object.__setattr__(model, "_next", spy)
    mw = step_middleware({"one": {"prompt": "P1", "tools": ["transfer_to_two"]},
                          "two": {"prompt": "P2", "tools": [alpha]}}, default="one")
    agent = create_agent(model, tools=[alpha, step_tool("two")], middleware=[mw], state_schema=StepState,
                         checkpointer=InMemorySaver())
    out = agent.invoke({"messages": [HumanMessage("hi")]}, cfg("s"))
    assert out["current_step"] == "two"
    assert seen == [("P1", ["transfer_to_two"]), ("P2", ["alpha"])]


# --------------------------------------------------------------------------- support desk
def test_detect_intents_order():
    assert detect_intents("refund INV-1 and fix 429 errors") == ["billing", "technical"]
    assert detect_intents("I forgot my password") == ["account"]
    assert detect_intents("hello there") == []


def test_refund_threshold_and_decisions(desk, tools):
    app = build_handoffs_desk(offline_model, tools, checkpointer=InMemorySaver())
    small = run_conversation(app, {"id": "a", "turns": ["C-1003 refund INV-3001 $19"]}, desk)
    assert small["interrupts"] == 0 and small["refunds"][0]["approved_by"] == "policy"
    rejected = run_conversation(app, {"id": "b", "turns": ["C-1002 refund $120 of INV-2001"], "decision": "reject"},
                                desk)
    assert rejected["interrupts"] == 1 and rejected["refunds"] == [] and "not approved" in rejected["answer"]
    edited = run_conversation(app, {"id": "c", "turns": ["C-1002 refund $120 of INV-2001"]}, desk,
                              reviewer=lambda payload: {"action": "edit", "text": "40"})
    assert edited["refunds"][0]["amount"] == 40.0
    assert REFUND_THRESHOLD == 50.0


def test_score_flags_missing_parts():
    conv = {"id": "x", "expect": {"tools": ["issue_refund"], "interrupts": 1, "contains": ["refunded"]}}
    good = {"answer": "Refunded $99", "tools": ["issue_refund"], "interrupts": 1,
            "refunds": [{"amount": 99, "approved_by": "billing manager"}]}
    bad = {**good, "interrupts": 0, "refunds": [{"amount": 99, "approved_by": "policy"}]}
    assert score(conv, good)["passed"]
    result = score(conv, bad)
    assert not result["passed"] and not result["interrupts"] and not result["refund_policy"]


@pytest.mark.parametrize("pattern", ["baseline", "handoffs", "single", "subagents", "task", "router", "skills",
                                     "inline", "custom"])
def test_all_patterns_pass_the_test_set_offline(desk, tools, pattern):
    saver = InMemorySaver()
    app = {
        "handoffs": lambda: build_handoffs_desk(offline_model, tools, checkpointer=saver),
        "single": lambda: build_single_agent_desk(offline_model(), tools, checkpointer=saver),
        "subagents": lambda: build_subagents_desk(offline_model, tools, checkpointer=saver),
        "task": lambda: build_subagents_desk(offline_model, tools, checkpointer=saver, dispatch="task"),
        "router": lambda: build_router_desk(offline_model, tools, checkpointer=saver),
        "baseline": lambda: build_single_agent_baseline(offline_model(), tools, checkpointer=saver),
        "skills": lambda: build_skills_desk(offline_model(), tools, checkpointer=saver),
        "inline": lambda: build_skills_desk(offline_model(), tools, checkpointer=saver, inline=True),
        "custom": lambda: build_custom_desk(offline_model, tools, desk, checkpointer=saver),
    }[pattern]()
    conversations = load_conversations()
    assert len(conversations) == 15
    report = evaluate(app, conversations, desk, meter=UsageMeter())
    assert report["passed"] == 15, [r["id"] for r in report["rows"] if not r["passed"]]
    assert report["usage"]["model_calls"] > 0


def test_specialist_build_names_agent():
    spec = Specialist(name="x", description="d", system_prompt="You are X.")
    agent = spec.build(ScriptedChatModel(responses=["hi"]))
    assert agent.name == "x"


def test_split_by_intent_and_parse_refund():
    parts = split_by_intent("C-1001: refund INV-1003 ($49) and tell me how to fix 429 errors. Thanks!")
    assert parts == {"billing": "C-1001: refund INV-1003 ($49)", "technical": "tell me how to fix 429 errors. Thanks!"}
    req = parse_refund([HumanMessage("I'm C-1002"), AIMessage("ok"), HumanMessage("refund $120 of INV-2001")])
    assert req["customer_id"] == "C-1002" and req["invoice_id"] == "INV-2001" and req["amount"] == 120.0


def test_skills_load_once_per_conversation(desk, tools):
    assert set(make_skills()) == {"billing", "technical", "account"}
    app = build_skills_desk(offline_model(), tools, checkpointer=InMemorySaver())
    run_conversation(app, load_conversations()[11], desk, thread_id="sk")   # S12: two billing turns
    msgs = app.get_state({"configurable": {"thread_id": "sk"}}).values["messages"]
    assert [c["name"] for m in msgs if isinstance(m, AIMessage) for c in m.tool_calls].count("load_skill") == 1


def test_refund_workflow_policy_in_code(desk):
    from mastery.agents.support import _echo_writer

    app = build_refund_workflow(desk, _echo_writer(), checkpointer=InMemorySaver())
    config = cfg("wf")
    out = app.invoke({"messages": [HumanMessage("C-1002 refund $199 for INV-2001")]}, config)
    assert out["__interrupt__"][0].value["amount"] == 199.0
    out = app.invoke(Command(resume={"action": "edit", "text": "99"}), config)
    assert "Refunded $99.00" in out["messages"][-1].text and desk.refunds[0]["approved_by"] == "billing manager"
    out = app.invoke({"messages": [HumanMessage("C-1002 refund $10 for INV-9999")]}, cfg("wf2"))
    assert "does not belong" in out["messages"][-1].text
    assert desk.tools_called() == ["issue_refund"]
