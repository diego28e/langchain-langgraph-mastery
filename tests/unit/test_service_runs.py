from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("pydantic_settings")

from mastery.service.desk import support_manager  # noqa: E402
from mastery.service.runs import ServiceBusy, ThreadBusy  # noqa: E402
from mastery.service.settings import ServiceSettings  # noqa: E402

REFUND_19 = {"messages": [{"role": "user", "content": "Hi, I'm C-1003. Please refund invoice INV-3001 ($19), I subscribed by mistake."}]}
REFUND_199 = {"messages": [{"role": "user", "content": "I'm customer C-1002. I want a refund of $199 for INV-2001, we moved to another vendor."}]}


def run(coro):
    return asyncio.run(coro)


def test_run_streams_tokens_and_ends_with_the_answer():
    async def go():
        m = support_manager(ServiceSettings())
        r = await m.submit(thread_id="t", user_id="C-1003", input=REFUND_19)
        await m.wait(r.run_id)
        return m, r
    m, r = run(go())
    events = [e.event for e in r.events]
    assert r.status == "success" and "Refunded $19.00" in r.answer
    assert events[0] == "metadata" and "token" in events and events[-1] == "end"
    assert [e.id for e in r.events] == list(range(len(r.events)))
    assert r.usage["input_tokens"] > 0 and r.cost_usd > 0
    assert m.records()[0].status == "ok"


def test_refund_over_threshold_pauses_then_resumes_once():
    from langgraph.types import Command

    async def go():
        m = support_manager(ServiceSettings())
        first = await m.submit(thread_id="t", user_id="C-1002", input=REFUND_199)
        await m.wait(first.run_id)
        assert first.status == "interrupted" and first.interrupt[0]["amount"] == 199
        assert m.desk.refunds == []
        second = await m.submit(thread_id="t", user_id="C-1002", input=Command(resume="approve"))
        await m.wait(second.run_id)
        return m, second
    m, second = run(go())
    assert second.status == "success" and len(m.desk.refunds) == 1


def test_idempotency_thread_busy_queue_full_cancel_and_timeout():
    async def go():
        m = support_manager(ServiceSettings(max_concurrent=1, max_queue=1, run_timeout_s=0.5), delay_s=0.3)
        a = await m.submit(thread_id="a", user_id="C-1003", input=REFUND_19, idempotency_key="k")
        assert (await m.submit(thread_id="a", user_id="C-1003", input=REFUND_19, idempotency_key="k")) is a
        await asyncio.sleep(0.05)                                  # a acquires the only slot
        b = await m.submit(thread_id="b", user_id="C-1003", input=REFUND_19)
        with pytest.raises(ServiceBusy):
            await m.submit(thread_id="c", user_id="C-1003", input=REFUND_19)
        with pytest.raises(ThreadBusy):
            await m.submit(thread_id="a", user_id="C-1003", input=REFUND_19)
        await m.cancel(b.run_id)
        await m.wait(a.run_id)
        return m, a, b
    m, a, b = run(go())
    assert a.status == "timeout" and b.status == "cancelled"
    assert [e.event for e in b.events] == ["metadata", "end"] and m.queued == 0


def test_follow_replays_after_an_event_id():
    async def go():
        m = support_manager(ServiceSettings())
        r = await m.submit(thread_id="t", user_id="C-1003", input=REFUND_19)
        live = [e.id async for e in m.follow(r.run_id) if e is not None]
        replay = [e.id async for e in m.follow(r.run_id, after=2) if e is not None]
        return live, replay
    live, replay = run(go())
    assert live == list(range(len(live))) and replay == live[3:]


def test_concurrency_limit_shows_up_as_queue_time():
    async def go(limit):
        m = support_manager(ServiceSettings(max_concurrent=limit), delay_s=0.05)
        runs = [await m.submit(thread_id=f"t{i}", user_id=f"C-100{i % 3 + 1}", input=REFUND_19) for i in range(6)]
        for r in runs:
            await m.wait(r.run_id)
        return max(rec.stages["queue"] for rec in m.records())
    assert run(go(1)) > run(go(6)) + 0.1


def test_settings_parse_keys_and_reject_bad_ones():
    s = ServiceSettings(api_keys="a=C-1:customer,b=ops:manager")
    assert s.principals()["b"].role == "manager"
    with pytest.raises(ValueError):
        ServiceSettings(api_keys="broken").principals()
    with pytest.raises(ValueError):
        ServiceSettings(mode="prod")
