"""Module 08: hitl, persistence, stores and the Project 08 research graph (offline)."""

from __future__ import annotations

import asyncio
import operator
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Annotated

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from typing_extensions import TypedDict

from mastery.graphs.hitl import (
    adrive,
    approval_node,
    drive,
    parse_decision,
    pending_interrupts,
    resume,
    run_until_pause,
    scripted_reviewer,
)
from mastery.graphs.persistence import (
    async_sqlite_checkpointer,
    checkpoint_rows,
    count_checkpoints,
    file_size,
    sqlite_checkpointer,
    trim_thread,
)
from mastery.graphs.research import (
    build_research_graph,
    corpus_docs_search,
    offline_models,
    offline_web_search,
)
from mastery.graphs.state import memory_checkpointer
from mastery.graphs.stores import check_store_contract
from mastery.memory import HashingEmbeddings, close, make_store

REPO = Path(__file__).resolve().parents[2]
QUESTION = "How do I keep the battery healthy in winter?"


class Doc(TypedDict, total=False):
    draft: str
    feedback: str
    rejections: int
    approval: str
    final: str


def _doc_graph(checkpointer=None, **kw):
    def write(state: Doc) -> dict:
        return {"draft": f"draft v{state.get('rejections', 0) + 1}" + (f" ({state['feedback']})" if state.get("feedback") else "")}

    b = StateGraph(Doc)
    b.add_node("write", write)
    b.add_node("approval", approval_node(approved="publish", rejected="write", **kw), destinations=("publish", "write", END))
    b.add_node("publish", lambda s: {"final": s["draft"].upper()})
    b.add_edge(START, "write")
    b.add_edge("write", "approval")
    b.add_edge("publish", END)
    return b.compile(checkpointer=checkpointer or memory_checkpointer())


def test_parse_decision_accepts_and_rejects() -> None:
    assert parse_decision("Approve").action == "approve"
    assert parse_decision({"action": "edit", "text": "new"}).text == "new"
    for bad in ({"action": "reject"}, {"action": "edit", "text": " "}, {"action": "ship"}, 42):
        with pytest.raises(ValueError):
            parse_decision(bad)


def test_approval_node_approve_edit_reject_and_give_up() -> None:
    g = _doc_graph()
    cfg = {"configurable": {"thread_id": "a"}}
    first = run_until_pause(g, {}, cfg, printer=None)
    assert first["interrupts"][0].value["kind"] == "approval" and first["interrupts"][0].value["draft"] == "draft v1"
    assert len(pending_interrupts(g, cfg)) == 1
    again = resume(g, cfg, {"action": "reject", "feedback": "more detail"}, printer=None)
    assert again["interrupts"][0].value["draft"] == "draft v2 (more detail)"
    done = resume(g, cfg, {"action": "edit", "text": "my text"}, printer=None)
    assert done["done"] and done["values"]["final"] == "MY TEXT" and done["values"]["approval"] == "edited"

    g2 = _doc_graph(max_rejections=2)
    out = drive(g2, {}, {"configurable": {"thread_id": "b"}}, scripted_reviewer([{"action": "reject", "feedback": "no"}] * 5))
    assert out["values"]["approval"] == "gave_up" and out["values"]["rejections"] == 2 and "final" not in out["values"]


def test_invalid_answer_reasks_in_the_same_node() -> None:
    g = _doc_graph()
    cfg = {"configurable": {"thread_id": "c"}}
    run_until_pause(g, {}, cfg, printer=None)
    r = resume(g, cfg, {"action": "reject"}, printer=None)          # missing feedback
    payload = r["interrupts"][0].value
    assert payload["attempt"] == 2 and "feedback" in payload["error"]
    assert resume(g, cfg, "approve", printer=None)["values"]["final"] == "DRAFT V1"


def test_sqlite_checkpointer_survives_a_new_saver_and_prunes(tmp_path) -> None:
    db = tmp_path / "cp.sqlite"
    saver = sqlite_checkpointer(db)
    cfg = {"configurable": {"thread_id": "t"}}
    run_until_pause(_doc_graph(saver), {}, cfg, printer=None)
    close(saver)
    saver2 = sqlite_checkpointer(db)                                # "restart": new process, same file
    g = _doc_graph(saver2)
    assert g.get_state(cfg).next == ("approval",)
    rows = checkpoint_rows(g, cfg)
    assert rows[0]["interrupts"] == 1 and rows[-1]["source"] == "input" and rows[0]["parent_id"] == rows[1]["checkpoint_id"]
    assert resume(g, cfg, "approve", printer=None)["done"]
    before = count_checkpoints(saver2, "t")
    with pytest.raises(NotImplementedError):
        saver2.prune(["t"], strategy="keep_latest")        # in the base API, not in SqliteSaver 3.1.1
    assert trim_thread(saver2, "t") == before - 1
    assert count_checkpoints(saver2, "t") == 1 < before and g.get_state(cfg).values["final"] == "DRAFT V1"
    saver2.delete_thread("t")
    assert count_checkpoints(saver2) == 0 and file_size(db).endswith("KB")
    close(saver2)


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_store_contract(kind, tmp_path) -> None:
    store = make_store(kind, tmp_path / "s.sqlite" if kind == "sqlite" else None, embed=HashingEmbeddings())
    results = check_store_contract(store, semantic=True)
    assert all(results.values()), [k for k, v in results.items() if not v]
    close(store)


def _research(**kw):
    store = kw.pop("store", None)
    return build_research_graph(offline_models(), web_search=kw.pop("web", offline_web_search()),
                                docs_search=corpus_docs_search(), checkpointer=kw.pop("checkpointer", memory_checkpointer()),
                                store=store, **kw)


def test_research_graph_needs_approval_and_uses_feedback_and_preferences() -> None:
    store = make_store("memory")
    store.put(("preferences", "ana"), "style", {"text": "one paragraph, no bullets"})
    g = _research(store=store)
    cfg = {"configurable": {"thread_id": "r1"}}

    async def run():
        from mastery.graphs.hitl import aresume, arun_until_pause
        from mastery.graphs.research import ResearchContext

        ctx = ResearchContext(user_id="ana")
        first = await arun_until_pause(g, {"question": QUESTION}, cfg, printer=None, context=ctx)
        assert first["interrupts"][0].value["kind"] == "approval" and "final" not in first["values"]
        assert "[source: support/faq-battery.md]" in first["values"]["draft"] and "\n- " not in first["values"]["draft"]
        second = await aresume(g, cfg, {"action": "reject", "feedback": "shorter"}, printer=None, context=ctx)
        assert "_Revised after review: shorter_" in second["interrupts"][0].value["draft"]
        done = await aresume(g, cfg, "approve", printer=None, context=ctx)
        nodes = [r["node"] for r in done["values"]["run_log"]]
        assert done["done"] and done["values"]["final"].endswith("support/faq-battery.md")
        assert nodes.count("plan") == 1 and nodes.count("draft") == 2 and nodes.count("search_docs") == 1

    asyncio.run(run())


def test_research_graph_clarifies_vague_requests() -> None:
    g = _research()
    out = asyncio.run(adrive(g, {"question": "Battery?"}, {"configurable": {"thread_id": "r2"}},
                             scripted_reviewer(["the Nimbus Pro in winter", "approve"])))
    assert out["pauses"] == 2 and out["values"]["clarification"] == "the Nimbus Pro in winter"
    assert "(the Nimbus Pro in winter)" in out["values"]["question"]


def test_clarify_is_resume_safe_with_a_flipping_clarifier() -> None:
    """The clarify node re-runs on resume: a second, different verdict must not drop the human's answer."""
    from langchain_core.messages import AIMessage

    from mastery.testing import ScriptedChatModel

    calls = {"n": 0}

    def flipping(messages: list) -> AIMessage:          # ambiguous the first time, "clear" afterwards
        calls["n"] += 1
        args = {"ambiguous": calls["n"] == 1, "question": "Which product?" if calls["n"] == 1 else ""}
        return AIMessage("", tool_calls=[{"name": "Clarity", "id": f"c{calls['n']}", "args": args}])

    models = offline_models() | {"clarifier": ScriptedChatModel(responses=[flipping], repeat_last=True)}
    g = build_research_graph(models, web_search=offline_web_search(), docs_search=corpus_docs_search(),
                             checkpointer=memory_checkpointer())
    out = asyncio.run(adrive(g, {"question": "Battery?"}, {"configurable": {"thread_id": "flip"}},
                             scripted_reviewer(["the Nimbus Pro in winter", "approve"])))
    assert calls["n"] == 1                                  # the verdict was replayed, not asked again
    assert out["values"]["clarification"] == "the Nimbus Pro in winter"
    assert "(the Nimbus Pro in winter)" in out["values"]["question"]


def test_search_web_retries_then_falls_back() -> None:
    flaky = offline_web_search(failures=2)
    out = asyncio.run(adrive(_research(web=flaky), {"question": QUESTION}, {"configurable": {"thread_id": "r3"}},
                             scripted_reviewer(["approve"])))
    assert flaky.calls["calls"] == 3 + 1 and not any("unavailable" in f["text"] for f in out["values"]["findings"])
    down = offline_web_search(failures=99)
    out = asyncio.run(adrive(_research(web=down, search_attempts=2), {"question": QUESTION},
                             {"configurable": {"thread_id": "r4"}}, scripted_reviewer(["approve"])))
    assert any("Web search unavailable (ConnectionError" in f["text"] for f in out["values"]["findings"])
    assert any(r.get("error") for r in out["values"]["run_log"])


def test_search_web_timeout_is_handled() -> None:
    slow = offline_web_search(delay=0.5)
    out = asyncio.run(adrive(_research(web=slow, search_timeout=0.1, search_attempts=1), {"question": QUESTION},
                             {"configurable": {"thread_id": "r5"}}, scripted_reviewer(["approve"])))
    assert any("NodeTimeoutError" in f["text"] for f in out["values"]["findings"])


def test_killed_run_resumes_from_sqlite(tmp_path) -> None:
    db = tmp_path / "kill.sqlite"
    proc = subprocess.Popen([sys.executable, "-u", "-m", "mastery.graphs.research", "--db", str(db), "--thread", "k",
                             "--question", QUESTION, "--slow", "5"], cwd=REPO, stdout=subprocess.PIPE, text=True)
    for line in proc.stdout:
        if "searching docs" in line:
            proc.kill()
            break
    proc.wait(timeout=30)

    async def run():
        saver = await async_sqlite_checkpointer(db)
        g = _research(checkpointer=saver)
        cfg = {"configurable": {"thread_id": "k"}}
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert (await g.aget_state(cfg)).next == ("research",)
        out = await adrive(g, None, cfg, scripted_reviewer(["approve"]))
        await saver.conn.close()
        return out

    out = asyncio.run(run())
    assert out["done"] and [r["node"] for r in out["values"]["run_log"]][:2] == ["clarify_question", "plan"]


def test_m08_app_config_and_import() -> None:
    import json

    app = REPO / "apps" / "m08_research_agent"
    assert json.loads((app / "langgraph.json").read_text(encoding="utf-8"))["graphs"] == {"research_agent": "./agent.py:graph"}
    code = ("import os, runpy; os.environ['MASTERY_OFFLINE']='1'; g = runpy.run_path('agent.py')['graph']; "
            "print(sorted(n for n in g.get_graph().nodes if not n.startswith('__')))")
    out = subprocess.run([sys.executable, "-c", code], cwd=app, capture_output=True, text=True, timeout=120, check=True)
    assert "['approval', 'clarify_question', 'draft', 'finalize', 'plan', 'research']" in out.stdout


def test_resume_with_command_payload_for_parallel_interrupts() -> None:
    from langgraph.types import Send, interrupt

    class P(TypedDict, total=False):
        items: list[str]
        out: Annotated[list[str], operator.add]

    def ask(t):
        return {"out": [f"{t['item']}={interrupt(t['item'])}"]}

    g = (StateGraph(P).add_node("ask", ask)
         .add_conditional_edges(START, lambda s: [Send("ask", {"item": i}) for i in s["items"]], ["ask"])
         .compile(checkpointer=memory_checkpointer()))
    cfg = {"configurable": {"thread_id": "p"}}
    first = g.invoke({"items": ["a", "b"]}, cfg)
    answers = {i.id: i.value.upper() for i in first["__interrupt__"]}
    assert sorted(g.invoke(Command(resume=answers), cfg)["out"]) == ["a=A", "b=B"]


def test_in_memory_saver_does_not_implement_prune_either() -> None:
    """Canary for Lesson 03.02's text: when upstream implements prune(), update the lesson."""
    from langgraph.checkpoint.memory import InMemorySaver

    with pytest.raises(NotImplementedError):
        InMemorySaver().prune(["t"], strategy="keep_latest")
