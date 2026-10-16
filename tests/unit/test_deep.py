"""Module 11 helpers: mastery.deep (offline, scripted models)."""
from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage

pytest.importorskip("deepagents")

from mastery.deep import (  # noqa: E402
    DEFAULT_DEEP_MODEL,
    build_deep_agent,
    deep_key_ready,
    deep_model_spec,
    fallback_middleware,
    fallback_specs,
    run_stats,
)
from mastery.testing import ScriptedChatModel  # noqa: E402

FAKE = "gsk_" + "x" * 40


class Boom(ScriptedChatModel):
    def _generate(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        raise RuntimeError("provider down")


def test_spec_defaults_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MASTERY_DEEP_MODEL", raising=False)
    assert deep_model_spec() == DEFAULT_DEEP_MODEL
    monkeypatch.setenv("MASTERY_DEEP_SUBAGENT_MODEL", "groq:openai/gpt-oss-20b")
    assert deep_model_spec("subagent") == "groq:openai/gpt-oss-20b"


def test_key_ready_and_fallback_specs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", FAKE)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert deep_key_ready("groq:openai/gpt-oss-20b") and not deep_key_ready("openai:gpt-5.5")
    assert not deep_key_ready("nosuchprovider:x")
    monkeypatch.setenv("MASTERY_FALLBACK_MODELS", "openai/gpt-oss-120b, openai:gpt-5.5, groq:openai/gpt-oss-20b")
    # bare id -> groq; no OpenAI key -> skipped; the primary itself -> skipped
    assert fallback_specs("groq:openai/gpt-oss-20b") == ["groq:openai/gpt-oss-120b"]
    monkeypatch.delenv("MASTERY_FALLBACK_MODELS")
    assert fallback_middleware() is None


def test_build_runs_writes_files_and_counts() -> None:
    model = ScriptedChatModel(responses=[
        AIMessage("", tool_calls=[{"name": "write_file", "args": {"file_path": "/a.md", "content": "hi"}, "id": "1"}]),
        AIMessage("done")])
    agent = build_deep_agent(model, fallbacks=False)
    result = agent.invoke({"messages": [{"role": "user", "content": "write"}]})
    assert result["files"]["/a.md"]["content"] == "hi"
    stats = run_stats(result)
    assert stats["model_calls"] == 2 and stats["tool_calls"] == 1 and stats["files"] == 1
    assert {"ls", "read_file", "write_file", "edit_file", "task"} <= set(model.bound_tools)


def test_model_budget_ends_a_loop_cleanly() -> None:
    looper = ScriptedChatModel(responses=[AIMessage("", tool_calls=[{"name": "ls", "args": {}, "id": "l"}])],
                               repeat_last=True)
    result = build_deep_agent(looper, model_calls=3, fallbacks=False).invoke(
        {"messages": [{"role": "user", "content": "loop"}]})
    assert run_stats(result)["model_calls"] <= 4   # 3 real calls + the limit's closing message


def test_fallback_middleware_switches_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from langchain.agents.middleware import ModelFallbackMiddleware

    backup = ScriptedChatModel(responses=[AIMessage("from backup")])
    agent = build_deep_agent(Boom(responses=[AIMessage("x")]), fallbacks=False,
                             middleware=[ModelFallbackMiddleware(backup)])
    result = agent.invoke({"messages": [{"role": "user", "content": "hi"}]})
    assert result["messages"][-1].content == "from backup"


def test_course_backend_scopes_memories_per_user_and_denies_secrets(tmp_path) -> None:
    from dataclasses import dataclass

    from deepagents.backends import FilesystemBackend
    from langgraph.store.memory import InMemoryStore

    from mastery.deep import course_backend, secret_deny_rules

    @dataclass
    class Ctx:
        user_id: str

    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    store = InMemoryStore()
    model = ScriptedChatModel(responses=[
        AIMessage("", tool_calls=[{"name": "write_file", "args": {"file_path": "/memories/p.md", "content": "short"}, "id": "1"}]),
        AIMessage("", tool_calls=[{"name": "read_file", "args": {"file_path": "/reports/.env"}, "id": "2"}]),
        AIMessage("done")])
    agent = build_deep_agent(model, backend=course_backend(reports=FilesystemBackend(root_dir=tmp_path, virtual_mode=True)),
                             store=store, context_schema=Ctx, permissions=secret_deny_rules(), fallbacks=False)
    result = agent.invoke({"messages": [{"role": "user", "content": "go"}]}, context=Ctx("ana"))
    assert [item.key for item in store.search(("ana", "memories"))] == ["/p.md"]
    assert "permission denied" in result["messages"][4].content


def test_catch_all_deny_needs_dotfile_patterns() -> None:
    from deepagents import FilesystemPermission
    from deepagents.backends.utils import create_file_data

    from mastery.deep import deny_everything_else

    seeded = {"/.env": create_file_data("KEY=x")}

    def read_env(rules: list) -> str:
        model = ScriptedChatModel(responses=[
            AIMessage("", tool_calls=[{"name": "read_file", "args": {"file_path": "/.env"}, "id": "1"}]), AIMessage("ok")])
        out = build_deep_agent(model, permissions=rules, fallbacks=False).invoke(
            {"messages": [{"role": "user", "content": "r"}], "files": seeded})
        return out["messages"][2].content

    naive = [FilesystemPermission(operations=["read", "write"], paths=["/**"], mode="deny")]
    assert "KEY=x" in read_env(naive)                       # documents the gotcha: "/**" skips dot-files
    assert "permission denied" in read_env([deny_everything_else()])
