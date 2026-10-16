"""A tiny client for the service: auth headers and an SSE reader with resume (Lessons 12.04, 12.09).

Browsers have ``EventSource`` built in (it reconnects and sends ``Last-Event-ID`` by itself);
Python code reads the stream line by line. :func:`parse_sse` turns lines into events, following
the SSE format: ``event:``, ``data:`` and ``id:`` fields, a blank line ends an event, lines
starting with ``:`` are comments (keep-alives).
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any


@dataclass
class SSEEvent:
    event: str
    data: Any
    id: str | None


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def parse_sse(lines: Iterable[str]) -> Iterator[SSEEvent]:
    """Yield :class:`SSEEvent` from text lines; ``data`` is JSON-decoded when it is JSON."""
    fields: dict[str, list[str]] = {}
    for line in lines:
        if line == "":
            if "data" in fields or "event" in fields:
                raw = "\n".join(fields.get("data", []))
                try:
                    data: Any = json.loads(raw)
                except ValueError:
                    data = raw
                yield SSEEvent(fields.get("event", ["message"])[0], data, fields.get("id", [None])[0])
            fields = {}
        elif not line.startswith(":"):
            name, _, value = line.partition(":")
            fields.setdefault(name, []).append(value[1:] if value.startswith(" ") else value)


def stream_events(client: Any, run_id: str, key: str, *, last_event_id: str | None = None,
                  limit: int | None = None) -> list[SSEEvent]:
    """Read a run's events with an ``httpx.Client``; stop after ``limit`` events (simulates a disconnect)."""
    headers = bearer(key) | ({"Last-Event-ID": last_event_id} if last_event_id is not None else {})
    events: list[SSEEvent] = []
    with client.stream("GET", f"/runs/{run_id}/stream", headers=headers) as response:
        response.raise_for_status()
        for event in parse_sse(response.iter_lines()):
            events.append(event)
            if limit is not None and len(events) >= limit:
                break                                  # leaving the block closes the connection
    return events
