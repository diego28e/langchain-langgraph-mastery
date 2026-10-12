"""Unit tests for mastery.groq_catalog (Lesson 00.07, Project 00).

No real network calls: ``httpx.MockTransport`` answers every request with a
canned response, so these tests run offline and without a Groq key.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mastery.groq_catalog import (
    GROQ_MODELS_URL,
    GroqAPIError,
    fetch_groq_models,
    looks_like_chat_model,
    parse_models_payload,
)

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "data" / "samples" / "groq-models-sample.json"
FAKE_KEY = "gsk_FAKE_unit_test_key"  # Not a real key.


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    """Build an httpx client whose requests are answered by ``handler`` (no network)."""
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sample_payload_parses() -> None:
    payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    models = parse_models_payload(payload)

    ids = [m.id for m in models]
    assert "openai/gpt-oss-20b" in ids
    assert ids == sorted(ids)
    gpt = next(m for m in models if m.id == "openai/gpt-oss-20b")
    assert gpt.context_window == 131072
    assert gpt.owned_by == "OpenAI"


def test_parse_tolerates_missing_and_odd_fields() -> None:
    payload = {
        "object": "list",
        "data": [
            {"id": "b-model", "created": 1693721698, "active": True, "context_window": "8192"},
            {"id": "a-model", "active": "yes", "context_window": True},  # Odd types -> None.
            {"no_id": "skipped"},
            "not-a-dict",
        ],
    }
    models = parse_models_payload(payload)

    assert [m.id for m in models] == ["a-model", "b-model"]
    a_model, b_model = models
    assert a_model.active is None and a_model.context_window is None
    assert b_model.context_window == 8192
    assert b_model.created == datetime.fromtimestamp(1693721698, tz=UTC)


def test_parse_rejects_non_list_payload() -> None:
    with pytest.raises(ValueError, match="no 'data' list"):
        parse_models_payload({"error": {"message": "nope"}})


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("openai/gpt-oss-20b", True),
        ("qwen/qwen3.8-27b", True),
        ("whisper-large-v3-turbo", False),
        ("canopylabs/orpheus-v1-english", False),
        ("meta-llama/llama-prompt-guard-2-86m", False),
        ("openai/gpt-oss-safeguard-20b", False),
    ],
)
def test_looks_like_chat_model(model_id: str, expected: bool) -> None:
    assert looks_like_chat_model(model_id) is expected


def test_fetch_sends_bearer_key_and_parses() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(200, json={"object": "list", "data": [{"id": "openai/gpt-oss-20b"}]})

    with make_client(handler) as client:
        models = fetch_groq_models(FAKE_KEY, client=client)

    assert seen == {"url": GROQ_MODELS_URL, "auth": f"Bearer {FAKE_KEY}"}
    assert [m.id for m in models] == ["openai/gpt-oss-20b"]


def test_fetch_without_key_fails_before_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        raise AssertionError("No request should be sent without a key")

    with make_client(handler) as client, pytest.raises(GroqAPIError, match="GROQ_API_KEY is not set"):
        fetch_groq_models(client=client)


def test_fetch_401_gives_actionable_message_without_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API Key", "type": "invalid_request_error"}})

    with make_client(handler) as client, pytest.raises(GroqAPIError) as excinfo:
        fetch_groq_models(FAKE_KEY, client=client)

    assert excinfo.value.status_code == 401
    assert "Invalid API Key" in str(excinfo.value)
    assert "console.groq.com/keys" in str(excinfo.value)
    assert FAKE_KEY not in str(excinfo.value)


def test_fetch_429_exposes_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "7"}, text="slow down")

    with make_client(handler) as client, pytest.raises(GroqAPIError) as excinfo:
        fetch_groq_models(FAKE_KEY, client=client)

    assert excinfo.value.status_code == 429
    assert excinfo.value.retry_after == 7.0
    assert "rate-limits" in str(excinfo.value)


def test_fetch_network_error_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with make_client(handler) as client, pytest.raises(GroqAPIError, match="Could not reach Groq"):
        fetch_groq_models(FAKE_KEY, client=client)
