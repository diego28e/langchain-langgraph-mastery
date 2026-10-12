"""List the models that are live on Groq right now, using the Groq Models API.

Introduced in Module 00, Lesson 00.07 and used by Project 00 (Groq Model
Explorer). Module 01's ``mastery.models`` will use it to check that the model
IDs in your ``.env`` still exist before a notebook spends time on them.

Why call the API instead of trusting a list in the docs:
    Model IDs change faster than tutorials. In 2026 alone Groq shut down
    ``qwen/qwen3-32b``, ``llama-3.3-70b-versatile`` and others on its free and
    developer tiers (https://console.groq.com/docs/deprecations), while many
    examples online still use them. The Models API is the source of truth for
    *your* account, today.

API facts used here (VERIFIED 2026-10-11, https://console.groq.com/docs/api-reference#models-list):
    - ``GET https://api.groq.com/openai/v1/models`` with header
      ``Authorization: Bearer <GROQ_API_KEY>``.
    - Response: ``{"object": "list", "data": [ {model}, ... ]}``.
    - Each model has ``id``, ``object``, ``created`` (Unix seconds), ``owned_by``,
      ``active``, ``context_window``, ``public_apps``, and sometimes
      ``max_completion_tokens``. We treat every field except ``id`` as optional,
      because providers add and remove fields without notice.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

__all__ = [
    "GROQ_MODELS_URL",
    "GroqAPIError",
    "GroqModel",
    "fetch_groq_models",
    "looks_like_chat_model",
    "parse_models_payload",
]

# VERIFIED 2026-10-11: https://console.groq.com/docs/models ("Get All Available Models").
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"

# Seconds to wait for Groq before giving up. Listing models is a tiny request,
# so a long wait almost always means a network or proxy problem.
DEFAULT_TIMEOUT_S = 20.0

# Substrings that identify models that are NOT general chat models (speech,
# text-to-speech, and safety classifiers). A heuristic, so the project asks
# you to double-check against https://console.groq.com/docs/models.
NON_CHAT_MARKERS: tuple[str, ...] = ("whisper", "orpheus", "tts", "prompt-guard", "safeguard", "guard")

# Friendly explanations for the HTTP errors you are most likely to see.
# Status codes from https://console.groq.com/docs/errors (VERIFIED 2026-10-11).
_STATUS_HINTS: dict[int, str] = {
    401: "Groq rejected the API key. Check GROQ_API_KEY in your .env (Lesson 00.04), "
    "or create a new key at https://console.groq.com/keys, then restart the kernel.",
    403: "The key is valid but not allowed to do this. Check your organization's "
    "permissions at https://console.groq.com/settings.",
    404: "The endpoint was not found. Check GROQ_MODELS_URL against https://console.groq.com/docs/api-reference.",
    429: "Rate limit reached. Wait for the number of seconds in the 'retry-after' header, then try again. "
    "Limits: https://console.groq.com/docs/rate-limits",
    500: "Groq had an internal error. Wait a minute and retry.",
    502: "Groq had a temporary gateway error. Wait a minute and retry.",
    503: "Groq is temporarily unavailable (maintenance or overload). Wait and retry.",
}


class GroqAPIError(RuntimeError):
    """A Groq API call failed. The message explains what to do next.

    Attributes:
        status_code: HTTP status code, or ``None`` for network errors.
        retry_after: Seconds to wait (from the ``retry-after`` header on 429), if given.
    """

    def __init__(self, message: str, *, status_code: int | None = None, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


@dataclass(frozen=True)
class GroqModel:
    """One entry from the Groq Models API, with optional fields made explicit.

    Attributes:
        id: The model ID you pass to ``ChatGroq(model=...)``.
        owned_by: Organization that published the model (for example ``"OpenAI"``).
        active: Whether Groq reports the model as active. ``None`` if not reported.
        context_window: Maximum context length in tokens, if reported.
        max_completion_tokens: Maximum output tokens per request, if reported.
        created: When the model was added, as an aware UTC datetime, if reported.
    """

    id: str
    owned_by: str | None = None
    active: bool | None = None
    context_window: int | None = None
    max_completion_tokens: int | None = None
    created: datetime | None = None


def _as_int(value: Any) -> int | None:
    """Convert a JSON value to int, or return None if it is missing or not numeric."""
    if isinstance(value, bool):  # bool is a subclass of int; never treat True as 1 token.
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def parse_models_payload(payload: Mapping[str, Any]) -> list[GroqModel]:
    """Turn the raw JSON from ``GET /openai/v1/models`` into sorted :class:`GroqModel` objects.

    Args:
        payload: The decoded JSON body, shaped like ``{"object": "list", "data": [...]}``.

    Returns:
        Models sorted by ``id``. Entries without a string ``id`` are skipped.

    Raises:
        ValueError: If ``payload`` has no ``data`` list (the response is not a model list).
    """
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("Unexpected response: no 'data' list. Is this really the /models endpoint?")

    models: list[GroqModel] = []
    for item in data:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
            continue  # Defensive: skip anything that is not a model object.
        created_raw = _as_int(item.get("created"))
        active_raw = item.get("active")
        models.append(
            GroqModel(
                id=item["id"],
                owned_by=item.get("owned_by") if isinstance(item.get("owned_by"), str) else None,
                active=active_raw if isinstance(active_raw, bool) else None,
                context_window=_as_int(item.get("context_window")),
                max_completion_tokens=_as_int(item.get("max_completion_tokens")),
                created=datetime.fromtimestamp(created_raw, tz=UTC) if created_raw else None,
            )
        )
    return sorted(models, key=lambda m: m.id)


def looks_like_chat_model(model_id: str, markers: Sequence[str] = NON_CHAT_MARKERS) -> bool:
    """Guess whether a model ID is a general chat (text generation) model.

    Args:
        model_id: A Groq model ID, for example ``"openai/gpt-oss-20b"``.
        markers: Substrings that mark non-chat models (speech, TTS, safety).

    Returns:
        ``False`` if the ID contains any marker, otherwise ``True``. This is a
        heuristic: always confirm on https://console.groq.com/docs/models.
    """
    lowered = model_id.lower()
    return not any(marker in lowered for marker in markers)


def fetch_groq_models(
    api_key: str | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
    client: httpx.Client | None = None,
) -> list[GroqModel]:
    """Fetch the live model list for your Groq account.

    Args:
        api_key: Groq API key. Defaults to ``os.environ["GROQ_API_KEY"]``. Pass
            it explicitly only in tests; in notebooks let it come from ``.env``.
        timeout: Seconds before the request is abandoned.
        client: An existing ``httpx.Client``. Tests pass one built on
            ``httpx.MockTransport`` so no real network call happens.

    Returns:
        Models sorted by ID (see :func:`parse_models_payload`).

    Raises:
        GroqAPIError: If the key is missing, the network fails, or Groq returns
            an error status. The message says what to do next and never
            contains the key.
    """
    key = api_key if api_key is not None else os.environ.get("GROQ_API_KEY", "")
    if not key.strip():
        raise GroqAPIError(
            "GROQ_API_KEY is not set. Add it to your .env file (Lesson 00.04), "
            "restart the kernel, and run the notebook again."
        )

    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    owns_client = client is None
    http = client or httpx.Client(timeout=timeout)
    try:
        response = http.get(GROQ_MODELS_URL, headers=headers)
    except httpx.TimeoutException as exc:
        raise GroqAPIError(
            f"Groq did not answer within {timeout:.0f} s. Check your internet connection, VPN, or proxy."
        ) from exc
    except httpx.HTTPError as exc:  # DNS failure, refused connection, TLS/proxy problems...
        raise GroqAPIError(
            f"Could not reach Groq ({type(exc).__name__}). Check your internet connection, VPN, or proxy."
        ) from exc
    finally:
        if owns_client:
            http.close()

    if response.status_code != 200:
        retry_after = _as_int(response.headers.get("retry-after"))
        hint = _STATUS_HINTS.get(response.status_code, "See https://console.groq.com/docs/errors.")
        # Groq's error body is {"error": {"message": ..., "type": ...}}. The
        # message is safe to show: it never echoes the key back.
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            detail = ""
        message = f"Groq returned HTTP {response.status_code}" + (f" ({detail})" if detail else "") + f". {hint}"
        raise GroqAPIError(
            message,
            status_code=response.status_code,
            retry_after=float(retry_after) if retry_after is not None else None,
        )

    return parse_models_payload(response.json())
