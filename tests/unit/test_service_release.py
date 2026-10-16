"""Lesson 12.09: kill switch, public lock-down, /version, the UI, and safe-release helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
yaml = pytest.importorskip("yaml")

from mastery.service.app import create_app, serve_in_background  # noqa: E402
from mastery.service.desk import support_manager  # noqa: E402
from mastery.service.release import CanaryRouter, RollbackCriteria, canary_decision, shadow_compare  # noqa: E402
from mastery.service.settings import ServiceSettings  # noqa: E402
from mastery.service.slo import synthetic_runs  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
UI = REPO / "apps" / "m12_service" / "ui"
CUSTOMER, MANAGER = {"Authorization": "Bearer demo-customer"}, {"Authorization": "Bearer demo-manager"}
STRONG = "a" * 24 + "=C-1002:customer," + "b" * 24 + "=ops:manager"


@pytest.fixture(scope="module")
def client():
    app = create_app(support_manager, ServiceSettings(release="1.2.3"), ui_dir=UI)
    base, stop = serve_in_background(app)
    with httpx.Client(base_url=base, timeout=20) as c:
        yield c
    stop()


def test_version_ui_and_csp(client):
    v = client.get("/version").json()
    assert v["release"] == "1.2.3" and v["mode"] == "demo" and v["paused"] is False
    home = client.get("/", follow_redirects=False)
    assert home.status_code == 307 and home.headers["location"] == "/ui/"
    page = client.get("/ui/")
    assert page.status_code == 200 and "Orbita Cloud support" in page.text
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert client.get("/ui/app.js").headers["x-content-type-options"] == "nosniff"


def test_kill_switch(client):
    tid = client.post("/threads", headers=CUSTOMER).json()["thread_id"]
    assert client.post("/admin/pause", json={"paused": True}, headers=CUSTOMER).status_code == 403
    assert client.post("/admin/pause", json={"paused": True}, headers=MANAGER).json() == {"paused": True}
    refused = client.post(f"/threads/{tid}/runs", json={"message": "hi"}, headers=CUSTOMER)
    assert refused.status_code == 503 and refused.headers["retry-after"] == "60"
    assert client.get("/version").json()["paused"] is True
    client.post("/admin/pause", json={"paused": False}, headers=MANAGER)
    assert client.post(f"/threads/{tid}/runs", json={"message": "hi"}, headers=CUSTOMER).status_code == 202


def test_public_refuses_demo_keys_and_short_secrets():
    with pytest.raises(ValueError, match="demo key"):
        ServiceSettings(public=True)
    with pytest.raises(ValueError, match="24 characters"):
        ServiceSettings(public=True, api_keys="short=C-1:customer")
    with pytest.raises(ValueError, match="JWT_SECRET"):
        ServiceSettings(public=True, api_keys=STRONG, jwt_secret="x" * 10)
    assert ServiceSettings(public=True, api_keys=STRONG).public


def test_canary_router_is_sticky_and_weighted():
    router = CanaryRouter(0.1)
    users = [f"C-{i}" for i in range(2000)]
    share = sum(router.route(u) == "canary" for u in users) / len(users)
    assert 0.07 < share < 0.13
    assert all(router.route(u) == router.route(u) for u in users[:50])
    assert CanaryRouter(0).route("x") == "stable" and CanaryRouter(1).route("x") == "canary"
    with pytest.raises(ValueError):
        CanaryRouter(1.5)


def test_canary_decision_promote_hold_rollback():
    stable = synthetic_runs(500, seed=1)
    assert canary_decision(stable, synthetic_runs(60, seed=2)).action == "promote"
    assert canary_decision(stable, synthetic_runs(20, seed=2)).action == "hold"
    incident = synthetic_runs(600, seed=3, incident=True)[-60:]
    decision = canary_decision(stable, incident)
    assert decision.action == "rollback" and any(r.startswith("ttft") for r in decision.reasons)
    pricey = [type(r)(**{**r.__dict__, "cost_usd": r.cost_usd * 3}) for r in synthetic_runs(60, seed=2)]
    assert canary_decision(stable, pricey, RollbackCriteria()).action == "rollback"


def test_shadow_catches_the_broken_auth_refactor():
    from mastery.agents.release_suite import BASELINE, NO_AUTH_CONTEXT, REDTEAM, release_cases

    same = shadow_compare(BASELINE, BASELINE, release_cases(20), attacks=REDTEAM)
    assert same["ship"] and same["regressions"] == 0 and not same["newly_unblocked"]
    broken = shadow_compare(BASELINE, NO_AUTH_CONTEXT, release_cases(20), attacks=REDTEAM)
    assert not broken["ship"] and broken["newly_unblocked"]


def test_pipeline_files_point_at_real_things():
    flow = yaml.safe_load((REPO / ".github" / "workflows" / "m12-service.yml").read_text(encoding="utf-8"))
    tests = next(s["run"] for s in flow["jobs"]["test"]["steps"] if s.get("name", "").startswith("Service tests"))
    for name in [w for w in tests.split() if w.endswith(".py")]:
        assert (REPO / name).is_file(), name
    blueprint = yaml.safe_load((REPO / "apps" / "m12_service" / "render.yaml").read_text(encoding="utf-8"))
    web = blueprint["services"][0]
    env = {e["key"]: e for e in web["envVars"]}
    assert web["healthCheckPath"] == "/ready" and env["MASTERY_SERVICE_PUBLIC"]["value"] == "true"
    assert all(env[k].get("sync") is False for k in ("MASTERY_SERVICE_API_KEYS", "GROQ_API_KEY", "MASTERY_SERVICE_DATABASE_URL"))


def test_v1_history_and_delete_my_data(client):
    tid = client.post("/v1/threads", headers=CUSTOMER).json()["thread_id"]
    run = client.post(f"/v1/threads/{tid}/runs", json={"message": "How do I rotate an API key?"}, headers=CUSTOMER).json()
    client.get(f"/v1/runs/{run['run_id']}/stream", headers=CUSTOMER)
    history = client.get(f"/v1/threads/{tid}", headers=CUSTOMER).json()
    assert [m["role"] for m in history["messages"]][:1] == ["user"] and history["messages"][-1]["role"] == "assistant"
    assert history["waiting_for_approval"] is False
    assert client.get(f"/v1/threads/{tid}", headers={"Authorization": "Bearer demo-other"}).status_code == 404
    foreign = client.get(f"/v1/runs/{run['run_id']}/stream", headers={"Authorization": "Bearer demo-other"})
    assert foreign.status_code == 404                     # a clean 404 before the stream, not a cut connection
    assert client.get("/healthz").json() == {"ok": True}
    gone = client.delete("/v1/me/data", headers=CUSTOMER).json()
    assert gone["user_id"] == "C-1002" and gone["deleted_threads"] >= 1
    assert client.get("/v1/threads", headers=CUSTOMER).json() == {"threads": []}
    assert client.get(f"/v1/runs/{run['run_id']}", headers=CUSTOMER).status_code == 404
    assert client.get("/threads", headers=CUSTOMER).json() == {"threads": []}     # same API, unversioned
