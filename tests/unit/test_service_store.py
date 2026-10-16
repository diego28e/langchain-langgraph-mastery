from __future__ import annotations

import asyncio
import os

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jwt")
httpx = pytest.importorskip("httpx")

from mastery.service.app import create_app, serve_in_background  # noqa: E402
from mastery.service.auth import TokenVerifier, issue_token  # noqa: E402
from mastery.service.client import bearer, stream_events  # noqa: E402
from mastery.service.desk import durable_support_manager  # noqa: E402
from mastery.service.runs import Run  # noqa: E402
from mastery.service.settings import ServiceSettings  # noqa: E402
from mastery.service.store import open_store  # noqa: E402

REFUND_199 = "I'm customer C-1002. I want a refund of $199 for INV-2001, we moved to another vendor."
INVOICES = "I'm customer C-1002. Please show my invoices."




@pytest.fixture(params=["sqlite", "postgres"])
def database_url(request, tmp_path):
    if request.param == "sqlite":
        return f"sqlite:///{tmp_path / 'service.db'}"
    url = os.environ.get("MASTERY_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("set MASTERY_TEST_POSTGRES_URL to run the Postgres variant")
    return url


class Service:
    def __init__(self, url, **extra):
        self.app = create_app(durable_support_manager, ServiceSettings(database_url=url, **extra))

    def __enter__(self):
        self.base, self.stop = serve_in_background(self.app)
        self.client = httpx.Client(base_url=self.base, timeout=20)
        return self.client

    def __exit__(self, *exc):
        self.client.close()
        self.stop()


def test_threads_runs_keys_and_interrupts_survive_a_restart(database_url):
    with Service(database_url) as c:
        tid = c.post("/threads", headers=bearer("demo-customer")).json()["thread_id"]
        headers = bearer("demo-customer") | {"Idempotency-Key": f"k-{tid}"}
        paused = c.post(f"/threads/{tid}/runs", json={"message": REFUND_199}, headers=headers).json()["run_id"]
        before = stream_events(c, paused, "demo-customer")
        assert before[-1].event == "interrupt"
    with Service(database_url) as c:                                    # a new process, same database
        assert tid in c.get("/threads", headers=bearer("demo-customer")).json()["threads"]
        assert c.get(f"/runs/{paused}", headers=bearer("demo-customer")).json()["status"] == "interrupted"
        assert c.get(f"/runs/{paused}", headers=bearer("demo-other")).status_code == 404
        replay = stream_events(c, paused, "demo-customer")
        assert [e.id for e in replay] == [e.id for e in before]
        again = c.post(f"/threads/{tid}/runs", json={"message": REFUND_199}, headers=headers).json()
        assert again["run_id"] == paused                                  # the key outlived the process
        resumed = c.post(f"/threads/{tid}/runs", json={"resume": "approve"}, headers=bearer("demo-manager")).json()
        end = stream_events(c, resumed["run_id"], "demo-manager")[-1]
        assert "Refunded $199.00" in end.data["answer"]                  # the checkpoint outlived it too


def test_runs_cut_off_by_a_crash_are_closed_at_startup(database_url):
    import uuid

    run_id, thread_id = f"run-crashed-{uuid.uuid4().hex[:6]}", f"thread-{uuid.uuid4().hex[:6]}"

    async def plant():
        async with open_store(database_url) as store:
            run = Run(run_id, thread_id, "C-1002", status="running")
            run.emit("metadata", {"run_id": run.run_id})
            await store.add_thread(thread_id, "C-1002")
            await store.save_run(run.stored() | {"user_id": "C-1002"})
            await store.add_events(run.run_id, run.events)
    asyncio.run(plant())
    with Service(database_url) as c:
        status = c.get(f"/runs/{run_id}", headers=bearer("demo-customer")).json()
        assert status["status"] == "error" and "restarted" in status["error"]
        assert [e.event for e in stream_events(c, run_id, "demo-customer")] == ["metadata", "error"]


def test_delete_thread_removes_runs_and_checkpoints(database_url):
    with Service(database_url) as c:
        tid = c.post("/threads", headers=bearer("demo-customer")).json()["thread_id"]
        rid = c.post(f"/threads/{tid}/runs", json={"message": INVOICES}, headers=bearer("demo-customer")).json()["run_id"]
        stream_events(c, rid, "demo-customer")
        assert c.delete(f"/threads/{tid}", headers=bearer("demo-other")).status_code == 404
        assert c.delete(f"/threads/{tid}", headers=bearer("demo-customer")).json()["deleted_runs"] == 1
        assert c.get(f"/runs/{rid}", headers=bearer("demo-customer")).status_code == 404
        assert tid not in c.get("/threads", headers=bearer("demo-customer")).json()["threads"]


def test_jwt_tokens_valid_expired_wrong_audience_tampered(tmp_path):
    secret = "test-secret-at-least-32-bytes-long-0123456789"
    with Service(None, jwt_secret=secret) as c:
        good = issue_token(secret, "C-1002")
        assert c.post("/threads", headers=bearer(good)).status_code == 201
        manager = issue_token(secret, "ops", role="manager")
        assert c.get("/stats", headers=bearer(manager)).status_code == 200
        expired = issue_token(secret, "C-1002", ttl_s=60, now=0)
        wrong_aud = issue_token(secret, "C-1002", audience="someone-else")
        other_key = issue_token("another-secret-also-32-bytes-long-abcdefgh", "C-1002")
        tampered = good[:-4] + ("AAAA" if not good.endswith("AAAA") else "BBBB")
        for token in (expired, wrong_aud, other_key, tampered):
            assert c.post("/threads", headers=bearer(token)).status_code == 401


def test_verifier_rejects_none_algorithm_and_unknown_roles():
    import jwt

    with pytest.raises(ValueError):
        TokenVerifier(issuer="i", audience="a", secret="s" * 32, algorithms=("none",))
    verifier = TokenVerifier(issuer="mastery-demo", audience="agent-service", secret="s" * 32)
    unsigned = jwt.encode({"sub": "C-1002", "iss": "mastery-demo", "aud": "agent-service", "iat": 1, "exp": 4102444800},
                          key=None, algorithm="none")
    assert verifier.principal(unsigned) is None
    assert verifier.principal(issue_token("s" * 32, "C-1002", role="admin")) is None
