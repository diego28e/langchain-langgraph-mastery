"""Operations: readiness, graceful shutdown, request ids, JSON logs and metrics (Lessons 12.06-12.07)."""
from __future__ import annotations

import asyncio
import json
import logging
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("prometheus_client")
httpx = pytest.importorskip("httpx")

from mastery.service.app import create_app, serve_in_background  # noqa: E402
from mastery.service.desk import support_manager  # noqa: E402
from mastery.service.observability import JsonFormatter, ServiceMetrics, log_run  # noqa: E402
from mastery.service.runs import SHUTDOWN_MESSAGE, RunManager  # noqa: E402
from mastery.service.settings import ServiceSettings  # noqa: E402

KEY = {"Authorization": "Bearer demo-customer"}
FAQ = "How do I rotate an API key?"


@pytest.fixture(scope="module")
def service():
    app = create_app(support_manager, ServiceSettings(metrics_token="scrape-me", release="test-1"))
    base, stop = serve_in_background(app)
    with httpx.Client(base_url=base, timeout=20) as client:
        yield app, client
    stop()


def test_ready_reports_release_and_database(service):
    app, c = service
    body = c.get("/ready").json()
    assert body == {"ready": True, "problems": [], "release": "test-1"}

    async def broken():
        raise ConnectionError("db down")

    original = app.state.manager.store.ping
    app.state.manager.store.ping = broken
    try:
        r = c.get("/ready")
        assert r.status_code == 503 and r.json()["problems"] == ["database: ConnectionError"]
    finally:
        app.state.manager.store.ping = original


def test_request_id_is_echoed_or_replaced(service):
    _, c = service
    assert c.get("/ok", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"
    made = c.get("/ok", headers={"X-Request-ID": "bad id; with spaces"}).headers["x-request-id"]
    assert made != "bad id; with spaces" and len(made) == 32


def test_metrics_need_the_token_and_count_runs(service):
    app, c = service
    assert c.get("/metrics").status_code == 401
    tid = c.post("/threads", headers=KEY).json()["thread_id"]
    run = c.post(f"/threads/{tid}/runs", json={"message": FAQ}, headers=KEY | {"X-Request-ID": "req-faq"}).json()
    for _ in range(100):
        if c.get(f"/runs/{run['run_id']}", headers=KEY).json()["status"] == "success":
            break
        time.sleep(0.05)
    text = c.get("/metrics", headers={"Authorization": "Bearer scrape-me"}).text
    assert 'agent_runs_total{status="success"}' in text
    assert 'route="/runs/{run_id}"' in text and run["run_id"] not in text      # templates, not raw paths
    assert "agent_run_ttft_seconds_bucket" in text and "agent_tokens_total" in text
    assert app.state.manager.runs[run["run_id"]].request_id == "req-faq"


def test_trace_config_carries_ids():
    manager = RunManager(graph=None, trace_metadata={"release": "r1"})
    from mastery.service.runs import Run

    config = manager.config_for(Run("run-1", "thread-1", "C-1002", request_id="req-1"))
    assert config["configurable"] == {"thread_id": "thread-1"}
    assert config["metadata"] == {"release": "r1", "service_run_id": "run-1", "thread_id": "thread-1",
                                  "user_id": "C-1002", "request_id": "req-1"}


def test_json_log_line_has_ids_but_no_text(caplog):
    from mastery.service.runs import Run

    run = Run("run-9", "thread-9", "C-1002", status="success", created_at=0.0, ended_at=2.0, answer="SECRET ANSWER")
    with caplog.at_level(logging.INFO, logger="mastery.service"):
        logging.getLogger("mastery.service").addHandler(caplog.handler)
        log_run(run)
    line = json.loads(JsonFormatter().format(caplog.records[-1]))
    assert line["run_id"] == "run-9" and line["run_status"] == "success" and line["duration_s"] == 2.0
    assert "SECRET" not in json.dumps(line)


def test_shutdown_drains_then_cuts_off_and_saves():
    async def scenario():
        manager = support_manager(ServiceSettings(), delay_s=0.3)
        quick = await manager.submit(thread_id="t-quick", user_id="C-1002", input={"messages": [("user", FAQ)]})
        stuck = await manager.submit(thread_id="t-stuck", user_id="C-1002", input={"messages": [("user", FAQ)]})
        cut = await manager.shutdown(drain_s=0.05)
        assert set(cut) == {quick.run_id, stuck.run_id}
        saved = await manager.store.get_run(stuck.run_id)
        assert saved["status"] == "error" and saved["error"] == SHUTDOWN_MESSAGE
        with pytest.raises(Exception, match="shutting down"):
            await manager.submit(thread_id="t-new", user_id="C-1002", input={"messages": [("user", FAQ)]})

        patient = support_manager(ServiceSettings(), delay_s=0.01)
        run = await patient.submit(thread_id="t-ok", user_id="C-1002", input={"messages": [("user", FAQ)]})
        assert await patient.shutdown(drain_s=10) == [] and run.status == "success"

    asyncio.run(scenario())


def test_metrics_registries_are_independent():
    a, b = ServiceMetrics(), ServiceMetrics()
    a.runs.labels("success").inc()
    assert b"agent_runs_total" in b.render()[0] and 'status="success"' not in b.render()[0].decode()


def test_demo_fail_rate_injects_outages():
    async def scenario():
        manager = support_manager(ServiceSettings(demo_fail_rate=1.0))
        run = await manager.submit(thread_id="t-x", user_id="C-1002", input={"messages": [("user", FAQ)]})
        await manager.wait(run.run_id)
        assert run.status == "error" and run.error.startswith("SimulatedOutage")

    asyncio.run(scenario())


def test_deploy_files_agree():
    """The Dockerfile copies only allowlisted paths that exist; compose and Prometheus files parse."""
    import re
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[2]
    app = root / "apps" / "m12_service"
    allow = [line[1:].rstrip("/") for line in (app / "Dockerfile.dockerignore").read_text().splitlines()
             if line.startswith("!")]
    for line in (app / "Dockerfile").read_text().splitlines():
        if line.startswith("COPY") and "--from" not in line:
            for src in line.split()[1:-1]:
                src = src.rstrip("/")
                assert (root / src).exists(), src
                assert any(src == a or src.startswith(a + "/") for a in allow), f"{src} is not in the allowlist"
    compose = yaml.safe_load((app / "compose.yaml").read_text())
    assert compose["services"]["db"]["image"] == "postgres:17-alpine"
    assert compose["services"]["api"]["depends_on"]["db"]["condition"] == "service_healthy"
    rules = yaml.safe_load((app / "ops" / "alerts.yml").read_text())
    names = [r["alert"] for g in rules["groups"] for r in g["rules"]]
    runbook = (app / "RUNBOOK.md").read_text()
    for name in names:
        assert f"## {name}" in runbook, f"RUNBOOK.md has no section for {name}"
    assert re.search(r"agent_runs_total", (app / "ops" / "alerts.yml").read_text())
