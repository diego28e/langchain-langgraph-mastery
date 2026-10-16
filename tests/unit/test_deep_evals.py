from __future__ import annotations

import pytest

pytest.importorskip("deepagents")

from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402

from mastery.deep.evals import (  # noqa: E402
    check_case,
    file_text,
    forbidden_calls,
    grounding,
    subagents_called,
    trajectory,
    trajectory_matches,
)


def _run(report: str) -> dict:
    return {
        "messages": [
            AIMessage("", tool_calls=[{"name": "web_search", "args": {"query": "q"}, "id": "1"}]),
            ToolMessage("Sources:\n- https://example.org/a", tool_call_id="1"),
            AIMessage("", tool_calls=[{"name": "task", "args": {"subagent_type": "critic", "description": "d"}, "id": "2"},
                                      {"name": "write_file", "args": {"file_path": "/reports/brief.md", "content": report}, "id": "3"}]),
            ToolMessage("ok", tool_call_id="2"),
            ToolMessage("ok", tool_call_id="3"),
            AIMessage("done"),
        ],
        "files": {"/reports/brief.md": {"content": report, "encoding": "utf-8"}},
    }


def test_trajectory_and_modes():
    run = _run("x")
    assert trajectory(run) == ["web_search", "task", "write_file"]
    assert subagents_called(run) == ["critic"]
    assert trajectory_matches(trajectory(run), ["web_search", "write_file"], "ordered")
    assert not trajectory_matches(trajectory(run), ["write_file", "web_search"], "ordered")
    assert trajectory_matches(trajectory(run), ["write_file", "web_search"], "subset")
    assert not trajectory_matches(trajectory(run), ["web_search", "write_file"], "exact")
    assert forbidden_calls(trajectory(run), ["execute", "task"]) == ["task"]
    with pytest.raises(ValueError):
        trajectory_matches([], [], "fuzzy")


def test_file_and_grounding():
    good = _run("# Brief\nSee https://example.org/a")
    bad = _run("# Brief\nSee https://example.org/a and https://invented.example/b")
    assert file_text(good, "/reports/brief.md").startswith("# Brief")
    assert file_text(good, "/missing.md") is None
    assert grounding(file_text(bad, "/reports/brief.md"), bad) == (["https://example.org/a"], ["https://invented.example/b"])
    case = {"expect_tools": ["web_search", "write_file"], "forbid_tools": ["execute"], "file": "/reports/brief.md",
            "file_contains": ["# brief"], "grounded": True, "max_model_calls": 3}
    assert check_case(good, case) == {"trajectory": True, "no_forbidden": True, "file": True, "grounded": True,
                                      "budget": True, "passed": True}
    out = check_case(bad, case)
    assert out["grounded"] is False and out["passed"] is False
    assert check_case(good, {"max_model_calls": 2})["passed"] is False
