"""A small async load test for the service: N concurrent conversations over HTTP + SSE (Lessons 12.04, 12.09).

Each virtual user creates a thread, starts a run, follows its SSE stream and records what a user
would feel: time to the first event with content (TTFT), total time, final status. The report uses
the SLO code of Lesson 12.01, so the numbers are comparable with the targets.

Command line (service running, from the repo root)::

    python -m mastery.service.loadtest --base-url http://127.0.0.1:8000 --users 20 --key demo-customer

Use the DEMO mode for load tests (no tokens). Against LIVE mode, 20 users spend real quota.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

from mastery.service.slo import RunRecord, default_slos, evaluate_slo, percentile

MESSAGES = [
    "Hi, I'm C-1002. What plan am I on?",
    "I'm customer C-1002. Please show my invoices.",
    "I'm C-1002 and I can't log in, my account is locked.",
    "C-1002 here: how do I export my data?",
]


async def one_user(client: Any, i: int, key: str, message: str) -> RunRecord:
    headers = {"Authorization": f"Bearer {key}"}
    start = time.perf_counter()
    ttft, status = None, "error"
    try:
        thread = (await client.post("/threads", headers=headers)).json()["thread_id"]
        response = await client.post(f"/threads/{thread}/runs", json={"message": message}, headers=headers)
        if response.status_code == 429:
            return RunRecord(f"u{i}", key, start, "rejected", None, None)
        response.raise_for_status()
        run_id = response.json()["run_id"]
        event = None
        async with client.stream("GET", f"/runs/{run_id}/stream", headers=headers) as stream:
            async for line in stream.aiter_lines():
                if line.startswith("event: "):
                    event = line[7:]
                    if event in {"token", "interrupt"} and ttft is None:
                        ttft = time.perf_counter() - start
                elif line.startswith("data: ") and event in {"end", "error", "interrupt"}:
                    status = {"success": "ok", "interrupted": "ok", "cancelled": "cancelled"}.get(
                        json.loads(line[6:]).get("status"), "error")
    except Exception:  # noqa: BLE001  (a failed user is a data point, not a crash)
        status = "error"
    return RunRecord(f"u{i}", key, start, status, ttft, time.perf_counter() - start)


async def run_load(base_url: str, users: int = 20, key: str = "demo-customer", transport: Any = None) -> dict[str, Any]:
    """Run ``users`` concurrent conversations; return a report dict (see :func:`print_report`)."""
    import httpx

    async with httpx.AsyncClient(base_url=base_url, timeout=120, transport=transport) as client:
        start = time.perf_counter()
        records = await asyncio.gather(*(one_user(client, i, key, MESSAGES[i % len(MESSAGES)]) for i in range(users)))
        wall = time.perf_counter() - start
    ttfts = [r.ttft_s for r in records if r.ttft_s is not None]
    durations = [r.duration_s for r in records if r.duration_s is not None and r.status == "ok"]
    slos = [evaluate_slo(slo, records) for slo in default_slos()]
    return {"users": users, "wall_s": round(wall, 2),
            "by_status": {s: sum(r.status == s for r in records) for s in ("ok", "error", "cancelled", "rejected")},
            "ttft_p50": round(percentile(ttfts, 50), 3) if ttfts else None,
            "ttft_p95": round(percentile(ttfts, 95), 3) if ttfts else None,
            "duration_p95": round(percentile(durations, 95), 3) if durations else None,
            "slos": [{"name": s.name, "ratio": round(s.ratio, 3) if s.eligible else None, "met": s.met if s.eligible else None}
                     for s in slos],
            "records": records}


def print_report(report: dict[str, Any]) -> None:
    print(f"{report['users']} users in {report['wall_s']} s · {report['by_status']}")
    print(f"TTFT p50 {report['ttft_p50']} s · p95 {report['ttft_p95']} s · duration p95 {report['duration_p95']} s")
    for slo in report["slos"]:
        print(f"  {slo['name']:<13} {slo['ratio']}  met={slo['met']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Concurrent conversations against the agent service.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--key", default="demo-customer", help="API key to use (DEMO keys by default)")
    args = parser.parse_args()
    print_report(asyncio.run(run_load(args.base_url, args.users, args.key)))


if __name__ == "__main__":
    main()
