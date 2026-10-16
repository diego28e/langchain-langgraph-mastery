from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from mastery.service.app import create_app, serve_in_background  # noqa: E402
from mastery.service.client import parse_sse, stream_events  # noqa: E402
from mastery.service.desk import support_manager  # noqa: E402
from mastery.service.settings import ServiceSettings  # noqa: E402

REFUND_199 = "I'm customer C-1002. I want a refund of $199 for INV-2001, we moved to another vendor."


def auth(key):
    return {"Authorization": f"Bearer {key}"}


def sse(client, run_id, key, last=None):
    return [{"event": e.event, "data": e.data, "id": e.id}
            for e in stream_events(client, run_id, key, last_event_id=None if last is None else str(last))]


@pytest.fixture(scope="module")
def service():
    app = create_app(support_manager, ServiceSettings())
    base, stop = serve_in_background(app)
    with httpx.Client(base_url=base, timeout=20) as client:
        yield app, client
    stop()


def test_auth_and_ownership(service):
    app, c = service
    assert c.get("/ok").json() == {"ok": True}
    assert c.post("/threads").status_code == 401
    assert c.post("/threads", headers=auth("wrong")).status_code == 401
    tid = c.post("/threads", headers=auth("demo-customer")).json()["thread_id"]
    assert c.post(f"/threads/{tid}/runs", json={"message": "hi"}, headers=auth("demo-other")).status_code == 404
    assert c.post(f"/threads/{tid}/runs", json={}, headers=auth("demo-customer")).status_code == 422
    assert c.post(f"/threads/{tid}/runs", json={"message": "x" * 5000}, headers=auth("demo-customer")).status_code == 413
    assert c.get("/stats", headers=auth("demo-customer")).status_code == 403


def test_refund_flow_with_idempotency_resume_and_approval(service):
    app, c = service
    tid = c.post("/threads", headers=auth("demo-customer")).json()["thread_id"]
    headers = auth("demo-customer") | {"Idempotency-Key": "refund-1"}
    first = c.post(f"/threads/{tid}/runs", json={"message": REFUND_199}, headers=headers)
    assert first.status_code == 202
    again = c.post(f"/threads/{tid}/runs", json={"message": REFUND_199}, headers=headers)
    assert again.json()["run_id"] == first.json()["run_id"]
    events = sse(c, first.json()["run_id"], "demo-customer")
    assert events[-1]["event"] == "interrupt"
    assert sse(c, first.json()["run_id"], "demo-customer", last=len(events) - 1) == []
    assert c.post(f"/threads/{tid}/runs", json={"resume": "approve"}, headers=auth("demo-customer")).status_code == 403
    resumed = c.post(f"/threads/{tid}/runs", json={"resume": "approve"}, headers=auth("demo-manager")).json()
    events = sse(c, resumed["run_id"], "demo-manager")
    assert events[-1]["event"] == "end" and "Refunded $199.00" in events[-1]["data"]["answer"]
    status = c.get(f"/runs/{resumed['run_id']}", headers=auth("demo-customer")).json()
    assert status["status"] == "success" and status["usage"]["input_tokens"] > 0
    assert len([r for r in app.state.manager.desk.refunds if r["invoice_id"] == "INV-2001"]) == 1
    stats = c.get("/stats", headers=auth("demo-manager")).json()
    assert stats["by_status"]["success"] >= 1 and stats["slos"][0]["name"] == "availability"


def test_parse_sse_handles_comments_multiline_and_plain_text():
    lines = [": keep-alive", "", "event: token", 'data: {"text": "hi"}', "id: 3", "", "data: a", "data: b", ""]
    events = list(parse_sse(lines))
    assert [(e.event, e.data, e.id) for e in events] == [("token", {"text": "hi"}, "3"), ("message", "a\nb", None)]


def test_disconnect_then_resume_with_last_event_id(service):
    app, c = service
    tid = c.post("/threads", headers=auth("demo-customer")).json()["thread_id"]
    rid = c.post(f"/threads/{tid}/runs", json={"message": "I'm customer C-1002. Please show my invoices."},
                 headers=auth("demo-customer")).json()["run_id"]
    first = stream_events(c, rid, "demo-customer", limit=3)
    rest = stream_events(c, rid, "demo-customer", last_event_id=first[-1].id)
    ids = [int(e.id) for e in first + rest]
    assert ids == list(range(len(ids))) and rest[-1].event == "end"
