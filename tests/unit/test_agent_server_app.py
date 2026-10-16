"""The Agent Server app (Lesson 12.08): manifest, graph import and the custom-auth handlers."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("langgraph_sdk")

APP = Path(__file__).resolve().parents[2] / "apps" / "m12_agent_server"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"m12_agent_server_{name}", APP / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def auth(monkeypatch_module):
    return _load("auth")


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    mp.delenv("MASTERY_SERVICE_API_KEYS", raising=False)
    mp.delenv("MASTERY_SERVICE_JWT_SECRET", raising=False)
    mp.delenv("MASTERY_SERVICE_JWKS_URL", raising=False)
    yield mp
    mp.undo()


def ctx(user: str, role: str, action: str = "read"):
    return SimpleNamespace(permissions=[role], user=SimpleNamespace(identity=user), action=action)


def run(coro):
    return asyncio.run(coro)


def test_manifest_points_at_files_that_exist():
    manifest = json.loads((APP / "langgraph.json").read_text(encoding="utf-8"))
    assert manifest["dependencies"] == ["../.."]
    for spec in [*manifest["graphs"].values(), manifest["auth"]["path"]]:
        path, _, attr = spec.partition(":")
        assert (APP / path).is_file() and attr


def test_graph_builds_offline_without_checkpointer(monkeypatch):
    monkeypatch.setenv("MASTERY_SERVICE_MODE", "demo")
    graph = _load("graph").graph
    assert graph.checkpointer is None
    assert len(graph.get_graph().nodes) > 2


def test_authenticate_demo_keys_and_rejects_unknown(auth):
    if "demo-customer" not in auth._principals:
        pytest.skip("MASTERY_SERVICE_API_KEYS in .env replaces the demo keys")
    user = run(auth.authenticate("Bearer demo-customer"))
    assert user == {"identity": "C-1002", "role": "customer", "permissions": ["customer"]}
    from langgraph_sdk import Auth
    for header in (None, "", "Bearer nope"):
        with pytest.raises(Auth.exceptions.HTTPException) as err:
            run(auth.authenticate(header))
        assert err.value.status_code == 401


def test_owner_filter_stamps_and_filters(auth):
    value = {"metadata": {}}
    assert run(auth.owner_only(ctx("C-1002", "customer", "create"), value)) == {"owner": "C-1002"}
    assert value["metadata"]["owner"] == "C-1002"
    assert run(auth.owner_only(ctx("ops", "manager", "read"), {})) is None


def test_run_context_is_set_by_the_server(auth):
    value = {"kwargs": {"context": {"customer_id": "C-1001"}}}
    run(auth.act_as_owner(ctx("C-1002", "customer", "create_run"), value))
    assert value["kwargs"]["context"] == {"customer_id": "C-1002"}
    assert value["metadata"]["owner"] == "C-1002"


def test_only_managers_answer_approvals(auth):
    from langgraph_sdk import Auth
    with pytest.raises(Auth.exceptions.HTTPException) as err:
        run(auth.act_as_owner(ctx("C-1002", "customer", "create_run"), {"kwargs": {"command": {"resume": "approve"}}}))
    assert err.value.status_code == 403
    assert run(auth.act_as_owner(ctx("ops", "manager", "create_run"), {"kwargs": {"command": {"resume": "approve"}}})) is None


def test_only_managers_change_assistants(auth):
    from langgraph_sdk import Auth
    with pytest.raises(Auth.exceptions.HTTPException):
        run(auth.read_only_assistants(ctx("C-1002", "customer", "create"), {}))
    assert run(auth.read_only_assistants(ctx("C-1002", "customer", "search"), {})) is None
    assert run(auth.read_only_assistants(ctx("ops", "manager", "delete"), {})) is None
