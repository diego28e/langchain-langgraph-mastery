"""One place to create chat models for the course: ``get_model(role, provider)``.

Introduced in Module 01, Lesson 01.01 ("Chat models and init_chat_model").

Why this module exists:
    Model IDs change faster than course material (Lesson 00.06 found retired IDs
    in official docs). If every notebook wrote ``ChatGroq(model="...")`` by hand,
    one deprecation would mean editing dozens of files. Instead, notebooks ask
    for a *role* ("fast", "reasoning", "vision") and this module looks the model
    ID up in ``.env`` (``MASTERY_MODEL_*``) through :mod:`mastery.config`.

What it adds on top of LangChain's ``init_chat_model``:
    - Role-based lookup, so notebooks never hard-code model IDs (CONVENTIONS §4.6).
    - A friendly :class:`~mastery.config.MissingSettingError` *before* the
      provider SDK raises a cryptic one, plus an install hint when the provider
      package is missing.
    - A :class:`PreviewModelWarning` when you pick a preview model, so the
      "evaluation only" status is visible every time (docs/production-notes.md).
    - :func:`explain_model_error`, which classifies errors from *any* provider.
      WHY: LangChain defines standard exceptions (``langchain_core.exceptions``),
      but as of 2026-10-11 ``langchain-groq`` 1.1.3 still raises the ``groq``
      SDK's own exceptions while ``langchain-openai`` 1.7.0 raises the standard
      ones. Code that must handle both cannot rely on one hierarchy.

Facts used here (VERIFIED 2026-10-11):
    - ``init_chat_model("provider:model", **kwargs)`` and the standard parameters
      ``temperature``, ``max_tokens``, ``timeout``, ``max_retries``,
      ``rate_limiter``: https://docs.langchain.com/oss/python/langchain/models
    - ``ChatGroq.max_retries`` defaults to 2 (``langchain-groq`` 1.1.3 source),
      even though the generic Models page describes a default of 6.
    - Groq preview models: https://console.groq.com/docs/models
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from mastery.config import MissingSettingError, Settings, is_set, load_settings
from mastery.doctor import require_valid_ssl_env

if TYPE_CHECKING:  # Imported only for type checkers, so importing mastery stays fast.
    from langchain_core.language_models import BaseChatModel
    from langchain_core.rate_limiters import BaseRateLimiter

__all__ = [
    "PREVIEW_MODELS",
    "PROVIDER_KEY_ENV",
    "PROVIDER_PACKAGES",
    "ROLES",
    "ModelErrorInfo",
    "PreviewModelWarning",
    "describe_model",
    "explain_model_error",
    "get_model",
    "model_string",
    "split_model_string",
]

Role = Literal["fast", "reasoning", "vision"]
ROLES: tuple[str, ...] = ("fast", "reasoning", "vision")

# Which environment variable(s) hold the key for each provider prefix.
# A provider is ready if ANY of its variables is set (Gemini accepts either name).
PROVIDER_KEY_ENV: dict[str, tuple[str, ...]] = {
    "groq": ("GROQ_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "google_genai": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "ollama": (),  # Local server, no key.
}

# The pip package behind each provider prefix (shown when an import fails).
PROVIDER_PACKAGES: dict[str, str] = {
    "groq": "langchain-groq",
    "openai": "langchain-openai",
    "google_genai": "langchain-google-genai",
    "ollama": "langchain-ollama",
}

# VERIFIED 2026-10-11: listed under "Preview Models" on https://console.groq.com/docs/models
# ("evaluation purposes only ... may be discontinued at short notice").
PREVIEW_MODELS: frozenset[str] = frozenset(
    {
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-safeguard-20b",
        "meta-llama/llama-prompt-guard-2-22m",
        "meta-llama/llama-prompt-guard-2-86m",
        "canopylabs/orpheus-v1-english",
        "canopylabs/orpheus-arabic-saudi",
        "minimaxai/minimax-m2.7",
    }
)


class PreviewModelWarning(UserWarning):
    """Raised (as a warning) when a preview / evaluation-only model is selected."""


def split_model_string(spec: str) -> tuple[str, str]:
    """Split ``"provider:model"`` into its two parts.

    Only the FIRST colon separates them, because model IDs can contain slashes
    and (for some providers) colons, e.g. ``"groq:openai/gpt-oss-20b"``.

    Args:
        spec: A string such as ``"groq:openai/gpt-oss-20b"``.

    Returns:
        ``(provider, model_id)``.

    Raises:
        ValueError: If there is no provider prefix.
    """
    provider, sep, model_id = spec.partition(":")
    if not sep or not provider or not model_id:
        raise ValueError(
            f"Expected 'provider:model' (for example 'groq:openai/gpt-oss-20b'), got {spec!r}."
        )
    return provider.strip(), model_id.strip()


def model_string(role: Role | str = "fast", provider: str = "groq", *, settings: Settings | None = None) -> str:
    """Return the ``"provider:model"`` string for a role, read from configuration.

    Args:
        role: ``"fast"``, ``"reasoning"`` or ``"vision"``.
        provider: ``"groq"`` (course default, free tier) or ``"benchmark"``
            (the paid benchmark from ``MASTERY_BENCHMARK_MODEL*``; ``"fast"``
            maps to the cheap benchmark, ``"reasoning"`` to the strong one,
            ``"vision"`` to the cheap one because both OpenAI and Gemini
            benchmark models accept images).
        settings: Settings to read from. Defaults to :func:`load_settings`.

    Returns:
        A string such as ``"groq:openai/gpt-oss-20b"``.

    Raises:
        ValueError: For an unknown role or provider.
    """
    if role not in ROLES:
        raise ValueError(f"Unknown role {role!r}. Use one of: {', '.join(ROLES)}.")
    settings = settings or load_settings()
    if provider == "groq":
        model_id = {"fast": settings.model_fast, "reasoning": settings.model_reasoning, "vision": settings.model_vision}[role]
        return f"groq:{model_id}"
    if provider == "benchmark":
        spec = settings.benchmark_model_strong if role == "reasoning" else settings.benchmark_model
        split_model_string(spec)  # Validate the format early, with a clear message.
        return spec
    raise ValueError(
        f"Unknown provider {provider!r} for role lookup. Use 'groq' or 'benchmark', "
        "or pass an explicit model, e.g. get_model(model='ollama:llama3.2')."
    )


def _require_provider_key(provider: str) -> None:
    """Raise :class:`MissingSettingError` if no key for ``provider`` is set."""
    names = PROVIDER_KEY_ENV.get(provider)
    if not names:  # Unknown provider or no key needed: let LangChain decide.
        return
    if not any(is_set(name) for name in names):
        raise MissingSettingError([names[0]])


def get_model(
    role: Role | str = "fast",
    provider: str = "groq",
    *,
    model: str | None = None,
    settings: Settings | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = 60.0,
    max_retries: int | None = 2,
    rate_limiter: BaseRateLimiter | None = None,
    check_key: bool = True,
    **kwargs: Any,
) -> BaseChatModel:
    """Create a chat model for a course role, with friendly errors.

    Construction does NOT call the provider: no tokens, no cost. The first
    network call happens on ``invoke``/``stream``/``batch``.

    Args:
        role: ``"fast"``, ``"reasoning"`` or ``"vision"`` (ignored when ``model`` is given).
        provider: ``"groq"`` or ``"benchmark"`` (see :func:`model_string`).
        model: Explicit ``"provider:model"`` string; overrides role/provider.
        settings: Settings to read model IDs from. Defaults to :func:`load_settings`.
        temperature: Sampling temperature. ``None`` keeps the *integration's*
            default (``ChatGroq``: 0.7). Note ``ChatGroq`` silently turns 0 into
            1e-8. Groq's docs suggest 0.0 for extraction but 0.5-0.7 for
            reasoning models; Lesson 01.01 discusses the trade-off.
        max_tokens: Output token cap. ``None`` keeps the integration default.
        timeout: Seconds before a request is abandoned. 60 avoids hanging cells.
        max_retries: Automatic retries for 429/5xx/network errors (not 401/404).
        rate_limiter: Optional limiter shared across models (Lesson 01.06).
        check_key: Check that the provider's API key is set before building.
        **kwargs: Passed through to ``init_chat_model`` (e.g. ``reasoning_effort="low"``).

    Returns:
        A LangChain chat model (for Groq, a ``ChatGroq``).

    Raises:
        MissingSettingError: The provider's key is not set (and ``check_key``).
        ImportError: The provider package is not installed (message says what to install).
        ValueError: Bad role, provider or model string.
        mastery.doctor.CertificateSettingError: ``SSL_CERT_FILE``/``SSL_CERT_DIR``
            point to a missing path (Lesson 00.02, step 4b).
    """
    from langchain.chat_models import init_chat_model  # Lazy: keeps `import mastery` light.

    spec = model or model_string(role, provider, settings=settings)
    provider_name, model_id = split_model_string(spec)
    if check_key:
        _require_provider_key(provider_name)
    # A bad SSL_CERT_FILE would crash the SDK client below with a bare
    # FileNotFoundError; this explains the cause and the fix instead.
    require_valid_ssl_env()
    if model_id in PREVIEW_MODELS:
        warnings.warn(
            f"{model_id} is a PREVIEW model: evaluation only, may be retired at short notice. "
            "See docs/production-notes.md.",
            PreviewModelWarning,
            stacklevel=2,
        )

    # Only send parameters the caller actually set, so provider defaults apply otherwise.
    params: dict[str, Any] = {
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "max_retries": max_retries,
        "rate_limiter": rate_limiter,
    }
    params = {name: value for name, value in params.items() if value is not None}
    params.update(kwargs)
    try:
        return init_chat_model(spec, **params)
    except ImportError as error:
        package = PROVIDER_PACKAGES.get(provider_name, f"the package for provider '{provider_name}'")
        raise ImportError(
            f"Could not create {spec!r}: {package} is not installed in this kernel. "
            f'In a notebook run:  %pip install "{package}"  then restart the kernel.'
        ) from error


@dataclass(frozen=True)
class ModelErrorInfo:
    """A provider-independent description of a failed model call.

    Attributes:
        kind: One of ``auth``, ``permission``, ``not_found``, ``invalid_request``,
            ``context_overflow``, ``rate_limit``, ``timeout``, ``connection``,
            ``server``, ``unknown``.
        retryable: Whether retrying the same request can succeed.
        status_code: HTTP status, when the error carries one.
        retry_after: Seconds to wait, from the ``retry-after`` header (429 only).
        hint: What to do next, in one sentence.
    """

    kind: str
    retryable: bool
    status_code: int | None
    retry_after: float | None
    hint: str


_HINTS: dict[str, str] = {
    "auth": "The API key is missing, invalid or expired: fix it in .env and restart the kernel.",
    "permission": "The key works but lacks permission for this model or organization.",
    "not_found": "Unknown or retired model ID: check the live model list and the provider's deprecations page.",
    "invalid_request": "The provider rejected the request (parameters, schema or model). Read the message.",
    "context_overflow": "The input is longer than the model's context window: shorten or summarize it.",
    "rate_limit": "Rate limit hit: wait retry_after seconds, slow down, or send fewer tokens.",
    "timeout": "The request timed out: retry, raise `timeout`, or ask for a shorter answer.",
    "connection": "Network problem: check your connection, VPN or proxy.",
    "server": "Provider-side error: retry with backoff; check the provider's status page.",
    "unknown": "Unexpected error: read the full message and traceback.",
}
_RETRYABLE = {"rate_limit", "timeout", "connection", "server"}


def _retry_after(error: BaseException) -> float | None:
    """Read the ``retry-after`` header from an SDK error's HTTP response, if any."""
    response = getattr(error, "response", None)
    headers: Mapping[str, str] | None = getattr(response, "headers", None)
    if not headers:
        return None
    try:
        return float(headers.get("retry-after", ""))
    except ValueError:
        return None


def _kind_from_status(status: int, message: str) -> str:
    """Map an HTTP status code (plus message clues) to an error kind."""
    lowered = message.lower()
    if status == 401:
        return "auth"
    if status == 403:
        return "permission"
    if status == 404 or "decommissioned" in lowered or "model_not_found" in lowered:
        return "not_found"
    if status == 408:
        return "timeout"
    if status == 413 or "context length" in lowered or "context_length" in lowered:
        return "context_overflow"
    if status == 429:
        return "rate_limit"
    # Groq flex tier: 498 "capacity_exceeded" means "retry later with jittered backoff".
    # VERIFIED 2026-10-11: https://console.groq.com/docs/flex-processing
    if status >= 500 or status == 498:
        return "server"
    if 400 <= status < 500:
        return "invalid_request"
    return "unknown"


def explain_model_error(error: BaseException) -> ModelErrorInfo:
    """Classify an exception from any chat model provider.

    Works with LangChain's standard exceptions (``langchain_core.exceptions``),
    with SDK errors that carry ``status_code`` (``groq``, ``openai``), and with
    plain timeout/connection errors.

    Args:
        error: The exception you caught.

    Returns:
        A :class:`ModelErrorInfo` (never raises).
    """
    status = getattr(error, "status_code", None)
    status = status if isinstance(status, int) else None
    name = type(error).__name__
    message = str(error)

    kind = "unknown"
    try:  # Step 1: LangChain's standard exception types, when the integration uses them.
        from langchain_core import exceptions as lc_exc

        standard = [
            ("ContextOverflowError", "context_overflow"),
            ("ModelAuthenticationError", "auth"),
            ("ModelPermissionDeniedError", "permission"),
            ("ModelNotFoundError", "not_found"),
            ("ModelRateLimitError", "rate_limit"),
            ("ModelTimeoutError", "timeout"),
            ("ModelConnectionError", "connection"),
            ("ModelInvalidRequestError", "invalid_request"),
            ("ModelAPIError", "server"),
        ]
        for class_name, standard_kind in standard:
            cls = getattr(lc_exc, class_name, None)
            if cls is not None and isinstance(error, cls):
                kind = standard_kind
                break
    except ImportError:  # langchain-core not installed: fall through to the generic rules.
        pass

    # Step 2: SDK errors with an HTTP status code (groq, openai, ...).
    if kind == "unknown" and status is not None:
        kind = _kind_from_status(status, message)
    # Step 3: Errors without a status code, recognized by class name.
    if kind == "unknown":
        if "Timeout" in name or isinstance(error, TimeoutError):
            kind = "timeout"
        elif "Connection" in name or isinstance(error, ConnectionError):
            kind = "connection"

    return ModelErrorInfo(
        kind=kind,
        retryable=kind in _RETRYABLE,
        status_code=status,
        retry_after=_retry_after(error) if kind == "rate_limit" else None,
        hint=_HINTS[kind],
    )


def describe_model(model: Any) -> dict[str, Any]:
    """Summarize a chat model object for display (no network call).

    Args:
        model: A LangChain chat model.

    Returns:
        A dict with the class, model ID, a few key parameters and selected
        profile fields (``None`` when the profile does not know the model,
        which happens for models newer than the installed package).
    """
    profile = getattr(model, "profile", None) or {}
    return {
        "class": type(model).__name__,
        "model": getattr(model, "model_name", None) or getattr(model, "model", None),
        "temperature": getattr(model, "temperature", None),
        "max_tokens": getattr(model, "max_tokens", None),
        "timeout": getattr(model, "request_timeout", None) or getattr(model, "timeout", None),
        "max_retries": getattr(model, "max_retries", None),
        "max_input_tokens": profile.get("max_input_tokens"),
        "image_inputs": profile.get("image_inputs"),
        "tool_calling": profile.get("tool_calling"),
        "structured_output": profile.get("structured_output"),
        "reasoning_output": profile.get("reasoning_output"),
    }
