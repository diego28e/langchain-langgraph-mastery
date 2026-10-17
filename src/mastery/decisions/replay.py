"""Replay and record TypeSafe System One calls, so Jev lessons run without a key, a balance or the network.

A recordings file maps each request (state + questions) to the response the API gave, or for
``synthetic`` records the response the course *expects*, hand-written from the documented schema
before a live run existed. Synthetic answers teach the API shape; never quote them as benchmark numbers.

Both transports plug into ``TypeSafeClassifier(client=httpx2.Client(transport=...))``: the
classifier builds and parses requests as usual, only the bytes come from (or go to) the file.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx2

__all__ = ["AsyncRecordingTransport", "RECORDINGS_DIR", "RecordingTransport", "ReplayMiss", "ReplayStore", "ReplayTransport", "request_key"]

RECORDINGS_DIR = Path(__file__).resolve().parents[3] / "data" / "samples" / "decisions"
FORMAT = 1


def request_key(body: dict[str, Any]) -> str:
    """Stable key for a request: sha256 of the canonical JSON of ``state`` and ``questions``.

    The model ID is left out on purpose, so ``jev-latest`` moving to a new release does not
    invalidate every recording (each record still stores the model that answered).
    """
    canonical = json.dumps({"state": body.get("state"), "questions": body.get("questions")},
                           sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class ReplayMiss(LookupError):
    """No recording for this request (new state or edited questions)."""

    def __init__(self, key: str, path: Path) -> None:
        self.key = key
        self.path = path
        super().__init__(
            f"No recorded Jev answer for this request (key {key}) in {path.name}. Replay mode only knows the "
            "lesson's own inputs: set TYPESAFE_API_KEY (live mode) to ask Jev about new text."
        )


class ReplayStore:
    """A JSON recordings file: ``{"format": 1, "questions": {ref: {...}}, "records": {key: {...}}}``.

    A question set is stored once under ``questions`` and referenced by each record (``questions_ref``),
    so 234 tickets asked the same questions don't repeat them 234 times.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.records: dict[str, dict[str, Any]] = {}
        self.questions: dict[str, Any] = {}
        if self.path.is_file():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.records = dict(data.get("records", {}))
            self.questions = dict(data.get("questions", {}))

    def __len__(self) -> int:
        return len(self.records)

    def get(self, body: dict[str, Any]) -> dict[str, Any] | None:
        return self.records.get(request_key(body))

    def put(self, body: dict[str, Any], response: dict[str, Any], *, synthetic: bool, recorded: str | None = None) -> str:
        key = request_key(body)
        ref = request_key({"state": None, "questions": body.get("questions")})
        self.questions[ref] = body.get("questions")
        self.records[key] = {"recorded": recorded or date.today().isoformat(), "synthetic": synthetic,
                             "request": {"model": body.get("model"), "state": body.get("state"), "questions_ref": ref},
                             "response": response}
        return key

    def synthetic_share(self) -> float:
        return sum(r["synthetic"] for r in self.records.values()) / len(self.records) if self.records else 0.0

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"format": FORMAT,
                "note": "Recorded TypeSafe System One calls (mastery.decisions). synthetic=true records were written "
                        "by hand from the documented schema, not returned by Jev: never quote them as measurements.",
                "questions": {ref: q for ref, q in sorted(self.questions.items())
                              if any(r["request"].get("questions_ref") == ref for r in self.records.values())},
                "records": dict(sorted(self.records.items()))}
        self.path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return self.path


def _body(request: httpx2.Request) -> dict[str, Any]:
    return json.loads(request.content.decode("utf-8") or "{}")


class ReplayTransport(httpx2.MockTransport):
    """Answer every request from a :class:`ReplayStore`; raise :class:`ReplayMiss` for unknown ones.

    Works for both clients (``MockTransport`` is sync and async): pass it to ``httpx2.Client`` **and**
    ``httpx2.AsyncClient``, or ``ainvoke``/``abatch`` would bypass replay and go to the network.

    The served ``x-typesafe-request-id`` header (``response.request_id``) is ``replay-synthetic-<key>`` or ``replay-recorded-<key>``, so
    :func:`mastery.decisions.provenance` can tell a learner where an answer came from.
    """

    def __init__(self, store: ReplayStore) -> None:
        self.store = store
        super().__init__(self._handle)

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        body = _body(request)
        record = self.store.get(body)
        if record is None:
            raise ReplayMiss(request_key(body), self.store.path)
        kind = "synthetic" if record["synthetic"] else "recorded"
        # langchain-typesafe reads request_id from this header (as the real API sends it).
        return httpx2.Response(200, json=record["response"],
                               headers={"x-typesafe-request-id": f"replay-{kind}-{request_key(body)}"})


class RecordingTransport(httpx2.BaseTransport):
    """Forward to ``upstream`` (a real transport) and save every successful answer to ``store``.

    Maintainer use: refresh the recordings with a real key (``MASTERY_DECISIONS_MODE=record``).
    Call ``store.save()`` afterwards; nothing is written on errors.
    """

    def __init__(self, upstream: httpx2.BaseTransport, store: ReplayStore, *, synthetic: bool = False) -> None:
        self.upstream = upstream
        self.store = store
        self.synthetic = synthetic

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        response = self.upstream.handle_request(request)
        if response.status_code == 200:
            response.read()
            payload = json.loads(response.content)
            payload.pop("request_id", None)
            self.store.put(_body(request), payload, synthetic=self.synthetic)
        return response

    def close(self) -> None:
        self.upstream.close()


class AsyncRecordingTransport(httpx2.AsyncBaseTransport):
    """The ``ainvoke``/``abatch`` twin of :class:`RecordingTransport` (``TypeSafeClassifier.async_client``)."""

    def __init__(self, upstream: httpx2.AsyncBaseTransport, store: ReplayStore, *, synthetic: bool = False) -> None:
        self.upstream = upstream
        self.store = store
        self.synthetic = synthetic

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        response = await self.upstream.handle_async_request(request)
        if response.status_code == 200:
            await response.aread()
            payload = json.loads(response.content)
            payload.pop("request_id", None)
            self.store.put(_body(request), payload, synthetic=self.synthetic)
        return response

    async def aclose(self) -> None:
        await self.upstream.aclose()
