"""Offline tests for mastery.memory (no network, no keys)."""

from __future__ import annotations

import math
import subprocess
import sys
import warnings
from pathlib import Path
from typing import TypedDict

import pytest
from langchain.agents import create_agent
from langchain.messages import AIMessage, HumanMessage
from langchain.tools import ToolRuntime, tool

from mastery.memory import (
    HashingEmbeddings,
    close,
    count_tokens,
    learner_namespace,
    make_checkpointer,
    make_store,
    memory_dir,
    safe_label,
    thread_config,
)
from mastery.testing import ScriptedChatModel


def _echo_agent(checkpointer):
    model = ScriptedChatModel(responses=[lambda msgs: f"I have seen {len(msgs)} message(s)."], repeat_last=True)
    return create_agent(model, tools=[], checkpointer=checkpointer)


def test_thread_config_shape_and_validation() -> None:
    assert thread_config("t1") == {"configurable": {"thread_id": "t1"}}
    assert thread_config("t1", user="x")["configurable"]["user"] == "x"
    with pytest.raises(ValueError):
        thread_config("  ")


def test_memory_dir_is_under_data_outputs(tmp_path: Path) -> None:
    folder = memory_dir(tmp_path)
    assert folder == tmp_path / "data" / "outputs" / "memory" and folder.is_dir()


def test_in_memory_checkpointer_keeps_threads_apart() -> None:
    agent = _echo_agent(make_checkpointer("memory"))
    agent.invoke({"messages": [HumanMessage("hi")]}, thread_config("a"))
    out = agent.invoke({"messages": [HumanMessage("again")]}, thread_config("a"))
    assert len(out["messages"]) == 4
    other = agent.invoke({"messages": [HumanMessage("hi")]}, thread_config("b"))
    assert len(other["messages"]) == 2


def test_sqlite_checkpointer_survives_a_new_process(tmp_path: Path) -> None:
    db = tmp_path / "chat"  # bare name -> chat.sqlite
    saver = make_checkpointer("sqlite", db)
    _echo_agent(saver).invoke({"messages": [HumanMessage("first")]}, thread_config("t"))
    close(saver)
    assert (tmp_path / "chat.sqlite").is_file()
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "from mastery.memory import make_checkpointer, thread_config, close\n"
        "from langchain.agents import create_agent\n"
        "from mastery.testing import ScriptedChatModel\n"
        "s = make_checkpointer('sqlite', %r)\n"
        "a = create_agent(ScriptedChatModel(responses=['ok']), tools=[], checkpointer=s)\n"
        "print(len(a.get_state(thread_config('t')).values['messages']))\n"
        "close(s)\n"
    ) % (str(Path(__file__).resolve().parents[2] / "src"), str(db))
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    assert result.stdout.strip().splitlines()[-1] == "2"


def test_bad_kind_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_checkpointer("redis")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        make_store("redis")  # type: ignore[arg-type]


def test_store_needs_dims_with_embed() -> None:
    class NoDims(HashingEmbeddings):
        dims = 0

    with pytest.raises(ValueError):
        make_store("memory", embed=NoDims.__new__(NoDims))


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_store_put_get_and_semantic_search(kind: str, tmp_path: Path) -> None:
    store = make_store(kind, tmp_path / "store.sqlite", embed=HashingEmbeddings(64), fields=["text"])
    ns = learner_namespace("ana", "facts")
    store.put(ns, "f1", {"text": "struggles with fraction problems"})
    store.put(ns, "f2", {"text": "prefers short visual explanations"})
    store.put(learner_namespace("bob", "facts"), "f1", {"text": "struggles with fractions too"})
    assert store.get(ns, "f1").value["text"].startswith("struggles")
    hits = store.search(ns, query="help me with fractions", limit=1)
    assert [h.key for h in hits] == ["f1"] and hits[0].namespace == ns
    assert {tuple(h.namespace) for h in store.search(("learners", "ana"))} == {ns}
    close(store)


def test_sqlite_store_persists(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    store = make_store("sqlite", path)
    store.put(("learners", "ana"), "profile", {"style": "examples first"})
    close(store)
    again = make_store("sqlite", path)
    assert again.get(("learners", "ana"), "profile").value == {"style": "examples first"}
    close(again)


@pytest.mark.parametrize("bad", ["", "a.b", "ana/../bob", "*", "x" * 129])
def test_safe_label_rejects_unsafe_ids(bad: str) -> None:
    with pytest.raises(ValueError):
        safe_label(bad)


def test_learner_namespace_layout() -> None:
    assert learner_namespace(" ana ") == ("learners", "ana")
    assert learner_namespace("u-1", "facts") == ("learners", "u-1", "facts")


def test_hashing_embeddings_are_stable_and_normalised() -> None:
    emb = HashingEmbeddings(dims=32)
    a = emb.embed_query("Fractions and decimals")
    assert a == HashingEmbeddings(dims=32).embed_query("fraction AND decimal")
    assert math.isclose(sum(v * v for v in a), 1.0, rel_tol=1e-9)
    assert emb.embed_query("the of and") == [0.0] * 32
    with pytest.raises(ValueError):
        HashingEmbeddings(dims=4)


def test_count_tokens_grows_with_text() -> None:
    short = count_tokens([HumanMessage("hi")])
    long = count_tokens([HumanMessage("hi " * 200), AIMessage("ok")])
    assert 0 < short < long


class Ctx(TypedDict):
    user_id: str


def test_store_reaches_tools_and_users_stay_apart() -> None:
    store = make_store("memory")

    @tool
    def remember_fact(fact: str, runtime: ToolRuntime[Ctx]) -> str:
        """Save a fact about the current learner."""
        runtime.store.put(learner_namespace(runtime.context["user_id"]), "fact", {"text": fact})
        return "saved"

    model = ScriptedChatModel(responses=[
        AIMessage("", tool_calls=[{"name": "remember_fact", "args": {"fact": "likes chess"}, "id": "c1"}]),
        "Saved.",
    ])
    agent = create_agent(model, tools=[remember_fact], store=store, context_schema=Ctx)
    with warnings.catch_warnings():  # harmless langchain-core 1.6.9–1.6.10 Pydantic warning about the context
        warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
        agent.invoke({"messages": [HumanMessage("remember I like chess")]}, context={"user_id": "ana"})
    assert store.get(("learners", "ana"), "fact").value == {"text": "likes chess"}
    assert store.search(("learners", "bob")) == []

