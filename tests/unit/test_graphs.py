"""Module 07: mastery.graphs (reducers, node utilities, the Project 07 pipeline) and the m07 app. Offline."""

from __future__ import annotations

import json
import operator
import subprocess
import sys
from pathlib import Path
from typing import Annotated, TypedDict

import pytest
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send

from mastery.graphs import (
    Critique,
    append_unique,
    keep_last,
    loop_router,
    merge_dicts,
    mermaid_markdown,
    run_summary,
    stream_updates,
    timed,
)
from mastery.graphs.content import (
    TEST_TOPICS,
    build_content_graph,
    corpus_researcher,
    offline_models,
)
from mastery.graphs.state import memory_checkpointer

REPO = Path(__file__).resolve().parents[2]


def test_reducers() -> None:
    assert merge_dicts({"a": 1, "b": 1}, {"b": 2}) == {"a": 1, "b": 2}
    assert merge_dicts(None, None) == {}
    assert append_unique(["x"], ["x", "y", "y"]) == ["x", "y"]
    assert append_unique(None, "z") == ["z"]
    last2 = keep_last(2)
    assert last2([1, 2], [3]) == [2, 3] and last2.__name__ == "keep_last_2"
    with pytest.raises(ValueError):
        keep_last(0)


class S(TypedDict, total=False):
    n: int
    seen: Annotated[list[str], append_unique]
    run_log: Annotated[list[dict], operator.add]


def test_reducer_inside_a_graph_and_timed_rows() -> None:
    @timed()
    def a(state: S) -> dict:
        return {"n": state["n"] + 1, "seen": ["a"]}

    @timed("bee")
    def b(state: S) -> dict:
        return {"seen": ["a", "b"]}

    g = StateGraph(S)
    g.add_node("a", a)
    g.add_node("b", b)
    g.add_edge(START, "a")
    g.add_edge("a", "b")
    g.add_edge("b", END)
    out = g.compile().invoke({"n": 1})
    assert out["n"] == 2 and out["seen"] == ["a", "b"]
    assert [r["node"] for r in out["run_log"]] == ["a", "bee"]
    assert run_summary(out["run_log"] * 2)["a"]["calls"] == 2


def test_timed_rejects_non_dict() -> None:
    @timed()
    def bad(state):
        return Command(goto=END)

    with pytest.raises(TypeError):
        bad({})


def test_loop_router_stops_on_score_or_counter() -> None:
    route = loop_router(score_key="critique", threshold=8, max_iterations=3, again="revise", done="finalize")
    assert route({"critique": Critique(score=5), "iteration": 0}) == "revise"
    assert route({"critique": Critique(score=8), "iteration": 0}) == "finalize"
    assert route({"critique": Critique(score=2), "iteration": 3}) == "finalize"
    assert route({"critique": 9}) == "finalize"
    with pytest.raises(ValueError):
        loop_router(score_key="s", threshold=1, max_iterations=-1, again="a", done="b")


def test_send_fan_out_and_command_and_recursion_limit() -> None:
    class M(TypedDict, total=False):
        items: list[int]
        out: Annotated[list[int], operator.add]

    def square(task: dict) -> dict:
        return {"out": [task["x"] ** 2]}

    g = StateGraph(M)
    g.add_node("square", square)
    g.add_conditional_edges(START, lambda s: [Send("square", {"x": x}) for x in s["items"]], ["square"])
    g.add_edge("square", END)
    assert sorted(g.compile().invoke({"items": [1, 2, 3]})["out"]) == [1, 4, 9]

    class L(TypedDict):
        n: int

    def loop(state: L) -> Command:
        return Command(update={"n": state["n"] + 1}, goto="loop")

    looping = StateGraph(L)
    looping.add_node("loop", loop, destinations=("loop",))
    looping.add_edge(START, "loop")
    with pytest.raises(GraphRecursionError):
        looping.compile().invoke({"n": 0}, {"recursion_limit": 5})


def test_content_pipeline_offline_improves_and_terminates() -> None:
    m = offline_models()
    graph = build_content_graph(m["planner"], m["writer"], m["critic"], corpus_researcher())
    for topic in TEST_TOPICS:
        out = graph.invoke({"topic": topic})
        assert out["scores"] == [4, 6, 8] and out["iteration"] == 2
        assert len(out["sections"]) == 3 and all(s["sources"] for s in out["sections"])
        assert "[source: " in out["final"] and "Sources: " in out["final"]
        assert out["critique"].issues == ["End with a '## Conclusion' section."]   # 8 = good enough: the loop stops
        nodes = [r["node"] for r in out["run_log"]]
        assert nodes.count("research_section") == 3 and nodes[-1] == "finalize"


def test_content_pipeline_hard_stop_with_a_critic_that_never_approves() -> None:
    from langchain_core.messages import AIMessage

    from mastery.testing import ScriptedChatModel

    m = offline_models()
    harsh = ScriptedChatModel(responses=[AIMessage("", tool_calls=[{"name": "Critique", "id": "c",
                                                                    "args": {"score": 3, "issues": ["Rewrite."]}}])],
                              repeat_last=True)
    graph = build_content_graph(m["planner"], m["writer"], harsh, corpus_researcher(), max_iterations=3)
    out = graph.invoke({"topic": TEST_TOPICS[0]})
    assert out["iteration"] == 3 and out["scores"] == [3, 3, 3, 3] and "final" in out


def test_pipeline_streams_and_checkpoints() -> None:
    m = offline_models()
    graph = build_content_graph(m["planner"], m["writer"], m["critic"], corpus_researcher(), checkpointer=memory_checkpointer())
    lines: list[str] = []
    config = {"configurable": {"thread_id": "t1"}}
    final = stream_updates(graph, {"topic": TEST_TOPICS[1]}, config, printer=lines.append)
    assert final["scores"] == [4, 6, 8]
    assert any("plan_outline" in ln for ln in lines) and sum("research_section" in ln for ln in lines) == 3
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")      # no "Deserializing unregistered type" warning
        assert graph.get_state(config).values["final"] == final["final"]
        assert len(list(graph.get_state_history(config))) == 11
    text = mermaid_markdown(graph)
    assert text.startswith("```mermaid") and "research_section" in text and "revise" in text


def test_m07_app_config_and_import() -> None:
    app = REPO / "apps" / "m07_content_pipeline"
    cfg = json.loads((app / "langgraph.json").read_text(encoding="utf-8"))
    assert cfg["graphs"] == {"content_pipeline": "./pipeline.py:graph"} and cfg["env"] == "../../.env"
    code = ("import os, runpy; os.environ['MASTERY_OFFLINE']='1'; "
            "g = runpy.run_path('pipeline.py')['graph']; "
            "print(sorted(n for n in g.get_graph().nodes if not n.startswith('__')))")
    out = subprocess.run([sys.executable, "-c", code], cwd=app, capture_output=True, text=True, timeout=120, check=True)
    assert "critique" in out.stdout and "research_section" in out.stdout


def test_sql_helpers_are_read_only(tmp_path) -> None:
    from mastery.graphs.sql import (
        check_sql,
        list_tables,
        run_readonly_query,
        sqlite_from_csv,
        table_schema,
    )

    db = sqlite_from_csv(REPO / "data" / "samples" / "expenses" / "expenses-2026.csv", tmp_path / "e.sqlite", "expenses")
    assert list_tables(db) == ["expenses"]
    assert "CREATE TABLE expenses" in table_schema(db, ["expenses"]) and "unknown table" in table_schema(db, ["nope"])
    out = run_readonly_query(db, "SELECT COUNT(*) AS n FROM expenses")
    assert out.splitlines() == ["n", "128"]
    assert check_sql("select 1") == (True, "select 1 LIMIT 50")
    assert check_sql("SELECT * FROM expenses LIMIT 3 OFFSET 5")[1].startswith("SELECT * FROM (")
    assert check_sql("SELECT * FROM expenses -- top rows")[1].endswith("\n) LIMIT 50")
    assert not check_sql("DROP TABLE expenses")[0]
    assert not check_sql("SELECT 1; DELETE FROM expenses")[0]
    assert run_readonly_query(db, "SELECT nope FROM expenses").startswith("Error:")
    # A WITH that tries to write is refused by the authorizer / read-only connection, and the data survives.
    assert run_readonly_query(db, "WITH x AS (SELECT 1) DELETE FROM expenses").startswith("Error:")
    # ...and the refusal comes from the authorizer itself, not from the appended LIMIT (a syntax error).
    import sqlite3

    from mastery.graphs.sql import _connect

    con = _connect(db)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            con.execute("WITH x AS (SELECT 1) DELETE FROM expenses")
    finally:
        con.close()
    assert run_readonly_query(db, "SELECT COUNT(*) FROM expenses").splitlines()[1] == "128"
    with pytest.raises(ValueError):
        sqlite_from_csv(REPO / "data" / "samples" / "expenses" / "expenses-2026.csv", tmp_path / "x.sqlite", "bad name")


def test_dev_server_command_and_missing_config(tmp_path) -> None:
    from mastery.graphs.server import DevServer, dev_server_command

    cmd = dev_server_command(2999)
    assert cmd[:3] == [sys.executable, "-m", "langgraph_cli"] and "--no-reload" in cmd and cmd[-1] == "2999"
    with pytest.raises(FileNotFoundError):
        DevServer(tmp_path)
    server = DevServer(REPO / "apps" / "m07_content_pipeline", port=2999)
    assert server.studio_url == "https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2999"


def test_canary_parallel_writes_apply_in_send_order_but_stream_in_completion_order() -> None:
    """Canary for Lesson 07.03 Part 2 ("In which order do parallel results land?").

    LangGraph 1.2 applies a super-step's writes in task order, while ``stream_mode="updates"``
    yields them as workers finish. The docs do NOT promise either order ("updates from a
    parallel superstep may not be ordered consistently"), which is why the course carries an
    index in Send payloads. If this test fails after an upgrade, the runtime changed: update the
    lesson's "You should now see" text, not the course's advice.
    """
    import operator
    import time
    from typing import Annotated, TypedDict

    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Send

    class Race(TypedDict):
        out: Annotated[list[int], operator.add]

    def runner(task: dict) -> dict:
        time.sleep(0.03 * (4 - task["i"]))
        return {"out": [task["i"]]}

    builder = StateGraph(Race)
    builder.add_node(runner)
    builder.add_conditional_edges(START, lambda s: [Send("runner", {"i": i}) for i in range(5)], ["runner"])
    builder.add_edge("runner", END)
    race = builder.compile()

    streamed = [u["runner"]["out"][0] for u in race.stream({"out": []}, stream_mode="updates")]
    assert streamed == [4, 3, 2, 1, 0]
    assert race.invoke({"out": []})["out"] == [0, 1, 2, 3, 4]


def test_content_graph_sets_a_tight_recursion_limit():
    from langchain_core.messages import AIMessage

    from mastery.graphs.content import content_recursion_limit
    from mastery.testing import ScriptedChatModel
    m = offline_models()
    harsh = ScriptedChatModel(responses=[AIMessage("", tool_calls=[{"name": "Critique", "id": "c",
                                                                   "args": {"score": 1, "issues": ["Again."]}}])],
                              repeat_last=True)
    graph = build_content_graph(m["planner"], m["writer"], harsh, corpus_researcher(), max_iterations=3)
    assert graph.config["recursion_limit"] == content_recursion_limit(3) == 16
    assert graph.invoke({"topic": "Battery care in winter"})["iteration"] == 3      # the harsh critic fits
    with pytest.raises(GraphRecursionError):                                        # a runaway loop fails fast
        build_content_graph(m["planner"], m["writer"], harsh, corpus_researcher(), max_iterations=50).invoke(
            {"topic": "Battery care in winter"}, {"recursion_limit": content_recursion_limit(3)})
