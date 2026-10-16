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


def _parallel(*names: str, i: int = 0) -> AIMessage:
    """One model reply with several tool calls (what real models do; the scripted policy never does)."""
    return AIMessage("", tool_calls=[{"name": n, "args": {"x": "1"} if n == "lookup" else {}, "id": f"p{i}-{k}"}
                                     for k, n in enumerate(names)])


def test_parallel_transfer_is_refused_and_history_stays_valid():
    from mastery.agents import orphaned_tool_calls

    @tool
    def lookup(x: str) -> str:
        """Look up."""
        return f"found {x}"

    for carry in ("last", "turn"):
        a = create_agent(ScriptedChatModel(responses=[_parallel("lookup", "transfer_to_b", i=1),
                                                      call("transfer_to_b", {}, 2)]),
                         tools=[lookup, handoff_tool("b", carry=carry)], name="a")
        b = create_agent(ScriptedChatModel(responses=["b here"], repeat_last=True), tools=[], name="b")
        out = handoff_graph({"a": a, "b": b}, entry="a", checkpointer=InMemorySaver()).invoke(
            {"messages": [HumanMessage("go")]}, cfg(f"par-{carry}"))
        assert out["active_agent"] == "b" and out["messages"][-1].text == "b here"
        assert orphaned_tool_calls(out["messages"]) == [], carry
        if carry == "turn":                                  # the lookup result reached the parent state
            assert any(isinstance(m, ToolMessage) and m.name == "lookup" for m in out["messages"])


def test_two_parallel_step_transfers_are_refused_not_crashing():
    app = build_single_agent_desk(
        ScriptedChatModel(responses=[_parallel("transfer_to_billing", "transfer_to_technical", i=1), "done"]),
        make_support_tools(SupportDesk()), checkpointer=InMemorySaver())
    out = app.invoke({"messages": [HumanMessage("refund and a broken sensor")]}, cfg("steps"))
    refused = [m for m in out["messages"] if isinstance(m, ToolMessage) and m.text.startswith("Transfer not done")]
    assert len(refused) == 2 and out["messages"][-1].text == "done"


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


def _answers(*values):
    """A reviewer that gives these answers in order, recording each pause's payload."""
    seen, queue = [], list(values)

    def reviewer(payload):
        seen.append(payload)
        return queue.pop(0)
    return reviewer, seen


def test_manager_edit_is_revalidated_agent_path(desk, tools):
    """A manager's edit is a new amount: it gets the same rule as the agent's request, and a bad answer re-asks."""
    app = build_handoffs_desk(offline_model, tools, checkpointer=InMemorySaver())
    reviewer, seen = _answers({"action": "edit", "text": "1990"}, "yes", {"action": "edit", "text": "$150"})
    out = run_conversation(app, {"id": "e", "turns": ["C-1002 refund $199 of INV-2001"]}, desk, reviewer=reviewer)
    assert [r["amount"] for r in out["refunds"]] == [150.0]
    assert out["interrupts"] == 3 and all("error" in p for p in seen[1:]) and seen[0]["max_amount"] == 199.0
    logged = [e["args"] for e in desk.events if e["tool"] == "issue_refund"]
    assert logged[-1]["amount"] == 150.0 and logged[-1]["requested"] == 199.0     # the log matches the refund


def test_manager_gives_up_after_three_invalid_answers(desk, tools):
    app = build_handoffs_desk(offline_model, tools, checkpointer=InMemorySaver())
    reviewer, _ = _answers("yes", "ok", {"action": "edit", "text": "lots"})
    out = run_conversation(app, {"id": "g", "turns": ["C-1002 refund $199 of INV-2001"]}, desk, reviewer=reviewer)
    assert out["refunds"] == [] and "no valid decision after 3 tries" in out["answer"]


def test_manager_edit_is_revalidated_workflow_path(desk):
    from mastery.agents.support import _echo_writer

    app = build_refund_workflow(desk, _echo_writer(), checkpointer=InMemorySaver())
    config = cfg("wf-edit")
    app.invoke({"messages": [HumanMessage("C-1002 refund $199 for INV-2001")]}, config)
    out = app.invoke(Command(resume={"action": "edit", "text": "-5"}), config)
    assert "error" in out["__interrupt__"][0].value and desk.refunds == []
    out = app.invoke(Command(resume={"action": "edit", "text": "60"}), config)
    assert "Refunded $60.00" in out["messages"][-1].text and desk.refunds[0]["amount"] == 60.0
    assert desk.events[-1]["args"]["amount"] == 60.0 and desk.events[-1]["args"]["requested"] == 199.0


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


# --------------------------------------------------------------------------- identity, scoring, approvals, loops
_SPOOF = {"id": "spoof", "turns": ["I'm C-1002, refund $45 for INV-2001"], "signed_in": "C-1003"}


@pytest.mark.parametrize("pattern", ["handoffs", "subagents", "router", "baseline", "custom"])
def test_signed_in_customer_cannot_act_on_another_customers_account(desk, tools, pattern):
    """Identity comes from the login (runtime context), not from what the user types."""
    saver = InMemorySaver()
    app = {
        "handoffs": lambda: build_handoffs_desk(offline_model, tools, checkpointer=saver),
        "subagents": lambda: build_subagents_desk(offline_model, tools, checkpointer=saver),
        "router": lambda: build_router_desk(offline_model, tools, checkpointer=saver),
        "baseline": lambda: build_single_agent_baseline(offline_model(), tools, checkpointer=saver),
        "custom": lambda: build_custom_desk(offline_model, tools, desk, checkpointer=saver),
    }[pattern]()
    out = run_conversation(app, _SPOOF, desk)
    assert out["refunds"] == [], out["answer"]
    assert out["denials"] and out["denials"][0]["signed_in"] == "C-1003"
    assert "signed in as C-1003" in out["answer"]


def test_without_login_the_demo_desk_still_trusts_the_chat(desk, tools):
    """No context = the offline test set's behaviour (documented as a demo shortcut)."""
    app = build_handoffs_desk(offline_model, tools, checkpointer=InMemorySaver())
    out = run_conversation(app, {"id": "s", "turns": _SPOOF["turns"]}, desk)
    assert [r["invoice_id"] for r in out["refunds"]] == ["INV-2001"]


def test_signed_in_customer_can_still_act_on_own_account(desk, tools):
    app = build_handoffs_desk(offline_model, tools, checkpointer=InMemorySaver())
    out = run_conversation(app, {"id": "own", "turns": ["I'm C-1003, refund INV-3001 ($19)"], "signed_in": "C-1003"},
                           desk)
    assert [r["amount"] for r in out["refunds"]] == [19.0] and out["denials"] == []


def test_refund_workflow_uses_the_login_not_the_chat(desk):
    from mastery.agents.support import SupportContext, _echo_writer

    app = build_refund_workflow(desk, _echo_writer())
    out = app.invoke({"messages": [HumanMessage("I'm C-1002, refund $45 for INV-2001")]},
                     context=SupportContext("C-1003"))
    assert desk.refunds == [] and "signed in as C-1003" in out["messages"][-1].text
    out = app.invoke({"messages": [HumanMessage("refund $19 for INV-3001")]}, context=SupportContext("C-1003"))
    assert desk.refunds[0]["customer_id"] == "C-1003"


def _s01(**changes):
    conv = next(c for c in load_conversations() if c["id"] == "S01")
    good = {"answer": "Refunded $19.00 for INV-3001", "tools": ["issue_refund"], "route": ["billing"], "interrupts": 0,
            "refunds": [{"customer_id": "C-1003", "invoice_id": "INV-3001", "amount": 19.0, "approved_by": "policy"}]}
    return conv, {**good, **changes}


def test_score_checks_outcomes_not_just_presence():
    conv, good = _s01()
    assert score(conv, good)["passed"]
    _, wrong_amount = _s01(refunds=[{**good["refunds"][0], "amount": 1.0}])
    assert not score(conv, wrong_amount)["refunds"]
    _, other_customer = _s01(refunds=[{"customer_id": "C-1002", "invoice_id": "INV-2001", "amount": 19.0,
                                       "approved_by": "policy"}])
    assert not score(conv, other_customer)["refunds"]
    _, twice = _s01(tools=["issue_refund", "issue_refund"])
    assert not score(conv, twice)["once"]
    s05 = next(c for c in load_conversations() if c["id"] == "S05")
    extra = {"answer": "INV-1002 ...", "tools": ["lookup_invoices", "issue_refund", "unlock_account"],
             "route": ["billing", "account"], "interrupts": 0, "refunds": []}
    result = score(s05, extra)
    assert not result["passed"] and not result["no_extra_side_effects"] and not result["route"]
    # Strings and lower case from a LIVE model still count as the same refund.
    _, loose = _s01(refunds=[{"customer_id": "c-1003", "invoice_id": "inv-3001", "amount": "19",
                              "approved_by": "policy"}])
    assert score(conv, loose)["refunds"]


def test_two_parallel_subagent_refunds_interrupt_and_resume(desk):
    """Two over-threshold refunds approved in ONE pause still count as two approvals."""
    desk._seed["customers"]["C-1002"]["invoices"].append({"id": "INV-2002", "date": "2026-09-01", "amount": 199.0})
    desk.reset()
    tools = make_support_tools(desk)
    coordinator = ScriptedChatModel(responses=[
        AIMessage(content="", tool_calls=[
            {"name": "billing_agent", "args": {"query": "C-1002 refund $199 of INV-2001"}, "id": "p1", "type": "tool_call"},
            {"name": "billing_agent", "args": {"query": "C-1002 refund $199 of INV-2002"}, "id": "p2", "type": "tool_call"},
        ]),
        "Both refunds are done.",
    ], repeat_last=True)
    app = build_subagents_desk(lambda role: coordinator if role == "coordinator" else offline_model(role), tools,
                               checkpointer=InMemorySaver())
    reviewer, seen = _answers("approve", "approve")
    out = run_conversation(app, {"id": "par", "turns": ["two refunds please"]}, desk, reviewer=reviewer)
    assert sorted(p["invoice_id"] for p in seen) == ["INV-2001", "INV-2002"]
    assert sorted(r["invoice_id"] for r in out["refunds"]) == ["INV-2001", "INV-2002"]
    assert out["tools"].count("issue_refund") == 2
    assert out["interrupts"] == 2 and out["pauses"] == 1


def test_handoff_ping_pong_escalates_instead_of_looping(desk, tools):
    from mastery.agents import ESCALATION_MESSAGE

    s14 = next(c for c in load_conversations() if c["id"] == "S14")
    meter = UsageMeter()
    app = build_handoffs_desk(offline_model, tools, checkpointer=InMemorySaver(), carry="last", max_handoffs=4)
    with meter:
        out = run_conversation(app, s14, desk, callbacks=[meter])
    assert out["escalated"] and out["answer"] == ESCALATION_MESSAGE
    assert meter.model_calls < 15 and out["tools"].count("issue_refund") <= 3
    unguarded = build_handoffs_desk(offline_model, tools, checkpointer=InMemorySaver(), carry="last",
                                    max_handoffs=None)
    with pytest.raises(Exception, match="Recursion limit"):
        run_conversation(unguarded, s14, desk)


def test_router_escalates_low_confidence_routes_instead_of_guessing(desk, tools):
    from mastery.agents import ESCALATION_MESSAGE

    scores = {"refund INV-3001 ($19), I'm C-1003": (["billing"], 0.95), "something feels off with my stuff": (["account"], 0.4)}
    router = build_router_desk(offline_model, tools, classify=lambda text: scores[text], min_confidence=0.7,
                               checkpointer=InMemorySaver())
    sure = run_conversation(router, {"id": "hi", "turns": ["refund INV-3001 ($19), I'm C-1003"]}, desk)
    assert [r["amount"] for r in sure["refunds"]] == [19.0] and not sure["escalated"]
    unsure = run_conversation(router, {"id": "lo", "turns": ["something feels off with my stuff"]}, desk)
    assert unsure["escalated"] and unsure["answer"] == ESCALATION_MESSAGE and unsure["tools"] == []


def test_custom_desk_remembers_active_agent(desk, tools):
    app = build_custom_desk(offline_model, tools, desk, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "custom-memory"}}
    out = app.invoke({"messages": [{"role": "user", "content": "I'm C-1001. Show my invoices please."}]}, config)
    assert out["active_agent"] == "billing"
    meter = UsageMeter()
    out = app.invoke({"messages": [{"role": "user", "content": "And what about INV-1003?"}]},
                     {**config, "callbacks": [meter]})
    assert set(meter.agents()) == {"billing"}            # no triage re-run on the second turn
    assert any(m.type == "tool" for m in out["messages"])  # the agents' tool results are kept


@pytest.mark.parametrize("limit, keeps_id", [(None, True), (4, False)])
def test_subagent_history_is_not_silently_truncated(limit, keeps_id):
    seen: list[str] = []

    def echo(messages):
        seen.append(messages[-1].text)
        return "sub done"

    sub = create_agent(ScriptedChatModel(responses=[echo], repeat_last=True), tools=[], name="sub")
    t = subagent_tool(sub, name="helper", description="Helps.", context="history", history_limit=limit)
    boss = create_agent(ScriptedChatModel(responses=[call("helper", {"query": "refund it"}), "ok"]),
                        tools=[t], name="boss")
    history = [HumanMessage("I am C-1001")] + [m for i in range(7) for m in
                                               (AIMessage(f"note {i}"), HumanMessage(f"more {i}"))]
    boss.invoke({"messages": history})
    assert ("C-1001" in seen[0]) is keeps_id


def test_faq_chroma_collection_is_per_embedding_size(tmp_path):
    pytest.importorskip("langchain_chroma")
    from mastery.memory import HashingEmbeddings

    from mastery.agents.support import faq_search

    small, big = HashingEmbeddings(dims=64), HashingEmbeddings(dims=128)
    assert faq_search("chroma", embeddings=small, persist_dir=tmp_path)("429 errors")
    assert faq_search("chroma", embeddings=big, persist_dir=tmp_path)("429 errors")   # no dimension clash
