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

import os
import re
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
    "friendly_model_error",
    "install_notebook_error_hints",
    "is_tool_use_failed",
    "parse_try_again_in",
    "safe_print",
    "is_transient",
    "structured_model",
    "get_model",
    "model_string",
    "split_model_string",
]

Role = Literal["fast", "reasoning", "vision", "multimodal"]
ROLES: tuple[str, ...] = ("fast", "reasoning", "vision", "multimodal")

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
        role: ``"fast"``, ``"reasoning"``, ``"vision"`` or ``"multimodal"`` (Module 13: always
            ``MASTERY_MODEL_MULTIMODAL``, a full ``"provider:model"`` string).
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
    if role == "multimodal":
        # Module 13: PDFs, audio and video. Groq has no such model, so this role is a full
        # "provider:model" string (default Gemini, free tier) whatever ``provider`` says.
        split_model_string(settings.model_multimodal)
        return settings.model_multimodal
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
        role: ``"fast"``, ``"reasoning"``, ``"vision"`` or ``"multimodal"`` (ignored when ``model`` is given).
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
            The SDK waits as long as a 429's ``retry-after`` says (up to 60 s), so per-minute limits
            recover on their own. With the default (2), the ``MASTERY_MAX_RETRIES`` environment
            variable can raise it for a whole run (the live-check runner sets 6).
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

    if max_tokens is None and os.environ.get("MASTERY_MAX_TOKENS", "").strip().isdigit():
        # e.g. an org whose output-tokens-per-minute (OTPM) limit is below the model's default output budget.
        max_tokens = int(os.environ["MASTERY_MAX_TOKENS"])
    if max_retries == 2 and os.environ.get("MASTERY_MAX_RETRIES", "").strip().isdigit():
        max_retries = int(os.environ["MASTERY_MAX_RETRIES"])
    # Groq's Qwen 3.8 returns its reasoning inline ("raw") by default, and Groq requires "parsed" or "hidden"
    # with tool calling or JSON mode. VERIFIED 2026-10-16: https://console.groq.com/docs/reasoning
    if provider_name == "groq" and model_id.startswith("qwen/") and "reasoning_format" not in kwargs:
        kwargs["reasoning_format"] = "parsed"
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
        primary = init_chat_model(spec, **params)
        return _with_env_fallbacks(primary, params, explicit=model is not None)
    except ImportError as error:
        package = PROVIDER_PACKAGES.get(provider_name, f"the package for provider '{provider_name}'")
        raise ImportError(
            f"Could not create {spec!r}: {package} is not installed in this kernel. "
            f'In a notebook run:  %pip install "{package}"  then restart the kernel.'
        ) from error


def _rate_limit_errors() -> tuple[type[BaseException], ...]:
    found: list[type[BaseException]] = []
    for module in ("groq", "openai"):
        try:
            found.append(__import__(module).RateLimitError)
        except (ImportError, AttributeError):
            pass
    try:   # the standard type integration packages raise (langchain-core >= 1.6)
        from langchain_core.exceptions import ModelRateLimitError

        found.append(ModelRateLimitError)
    except ImportError:
        pass
    return tuple(found)


def _fallback_class() -> Any:
    from langchain_core.runnables import RunnableWithFallbacks

    class ModelWithFallbacks(RunnableWithFallbacks):
        """RunnableWithFallbacks that also answers plain attributes (``.model_name``...) from the primary model."""

        def __getattr__(self, name: str) -> Any:
            try:
                return super().__getattr__(name)
            except AttributeError:
                if name.startswith("_") or name in ("runnable", "fallbacks"):
                    raise
                return getattr(self.runnable, name)

    return ModelWithFallbacks


def __getattr__(name: str) -> Any:  # lazy module attribute: keeps `import mastery.models` light
    if name == "_ModelWithFallbacks":
        cls = _fallback_class()
        globals()[name] = cls
        return cls
    raise AttributeError(name)


def _with_env_fallbacks(primary: Any, params: dict[str, Any], *, explicit: bool) -> Any:
    """Opt-in: ``MASTERY_FALLBACK_MODELS="groq:openai/gpt-oss-120b,groq:qwen/qwen3.8-27b"`` in ``.env``.

    On a rate-limit error (429, e.g. the free tier's daily quota) the call is retried on the next model in the
    list. Each Groq model has its OWN quota (https://console.groq.com/docs/rate-limits), so rotating models keeps
    a lesson going. Only role-based models get fallbacks (an explicit ``model=`` is a deliberate choice), and
    models whose provider key is missing are skipped. The result is a ``RunnableWithFallbacks``: ``invoke``,
    ``bind_tools``, ``with_structured_output`` and ``create_agent`` work, and plain attributes such as
    ``.model_name`` come from the primary model.
    """
    raw = os.environ.get("MASTERY_FALLBACK_MODELS", "").strip()
    errors = _rate_limit_errors()
    if explicit or not raw or not errors:
        return primary
    from langchain.chat_models import init_chat_model

    backups = []
    for spec in (s.strip() for s in raw.split(",") if s.strip()):
        provider_name, model_id = split_model_string(spec if ":" in spec else f"groq:{spec}")
        if not any(is_set(name) for name in PROVIDER_KEY_ENV.get(provider_name, ())):
            continue
        extra = dict(params)
        if provider_name == "groq" and model_id.startswith("qwen/"):
            extra.setdefault("reasoning_format", "parsed")
        if not (provider_name == "groq" and model_id.startswith(("openai/gpt-oss", "qwen/"))):
            extra.pop("reasoning_effort", None)       # a Groq-only parameter other providers reject
        backups.append(init_chat_model(f"{provider_name}:{model_id}", **extra))
    if not backups:
        return primary
    return __getattr__("_ModelWithFallbacks")(runnable=primary, fallbacks=backups, exceptions_to_handle=errors)


@dataclass(frozen=True)
class ModelErrorInfo:
    """A provider-independent description of a failed model call.

    Attributes:
        kind: One of ``auth``, ``permission``, ``not_found``, ``invalid_request``,
            ``context_overflow``, ``rate_limit``, ``timeout``, ``connection``,
            ``server``, ``daily_limit``, ``output_limit``, ``unknown``.
        retryable: Whether retrying the same request can succeed.
        status_code: HTTP status, when the error carries one.
        retry_after: Seconds to wait (429 only): the ``retry-after`` header, else Groq's "try again in" text.
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
    "context_overflow": ("The request is too large: longer than the model's context window, or (Groq HTTP 413) more "
                         "tokens in one request than your tokens-per-minute limit. Shorten or summarize it, or use "
                         "a model or tier with higher limits."),
    "rate_limit": "Rate limit hit: wait retry_after seconds, slow down, or send fewer tokens.",
    "output_limit": ("The request asks for more OUTPUT tokens than your organization's output-tokens-per-minute "
                     "(OTPM) limit allows. A configuration issue, not a bug: set max_tokens below the limit "
                     "(MASTERY_MAX_TOKENS in .env), or use a model without that limit."),
    "daily_limit": ("The DAILY quota for this model is used up (tokens or requests per day): retrying today won't "
                    "help. Wait until it resets, or switch model, e.g. MASTERY_MODEL_FAST=qwen/qwen3.8-27b in .env "
                    "(each model has its own daily allowance), or upgrade the plan."),
    "timeout": "The request timed out: retry, raise `timeout`, or ask for a shorter answer.",
    "connection": "Network problem: check your connection, VPN or proxy.",
    "server": "Provider-side error: retry with backoff; check the provider's status page.",
    "unknown": "Unexpected error: read the full message and traceback.",
}
_RETRYABLE = {"rate_limit", "timeout", "connection", "server"}


_TRY_AGAIN = re.compile(r"try again in\s+((?:\d+(?:\.\d+)?(?:h|ms|m|s))+)", re.I)
_DAILY = re.compile(r"\((TPD|RPD)\)|per day", re.I)


def parse_try_again_in(message: str) -> float | None:
    """Seconds from Groq's 429 text, e.g. "Please try again in 1m23.5s" -> 83.5 (None if absent)."""
    m = _TRY_AGAIN.search(message or "")
    if not m:
        return None
    units = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
    return sum(float(n) * units[u] for n, u in re.findall(r"(\d+(?:\.\d+)?)(ms|h|m|s)", m.group(1)))


def _retry_after(error: BaseException) -> float | None:
    """Seconds to wait: the ``retry-after`` header of an SDK error's HTTP response, else "try again in" text."""
    response = getattr(error, "response", None)
    headers: Mapping[str, str] | None = getattr(response, "headers", None)
    try:
        if headers and headers.get("retry-after") is not None:
            return float(headers.get("retry-after", ""))
    except ValueError:
        pass
    return parse_try_again_in(str(error))


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
    if status == 413 and ("otpm" in lowered or "output tokens per minute" in lowered):
        return "output_limit"
    if status == 413 or "context length" in lowered or "context_length" in lowered:
        return "context_overflow"
    if status == 429:
        # Groq: "... on tokens per day (TPD): Limit 200000, Used 199914 ..." -> a daily quota, not a per-minute one.
        return "daily_limit" if _DAILY.search(message) else "rate_limit"
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
    if kind == "rate_limit" and _DAILY.search(message):
        kind = "daily_limit"
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
        retry_after=_retry_after(error) if kind in ("rate_limit", "daily_limit") else None,
        hint=_HINTS[kind],
    )


def is_transient(error: BaseException) -> bool:
    """True for errors worth retrying: timeouts, connection errors, 429 rate limits and 5xx server errors.

    A ``retry_on`` predicate for LangGraph's ``RetryPolicy`` and LangChain's ``ModelRetryMiddleware``.
    Provider SDK errors (``groq.APIConnectionError``, ``groq.BadRequestError``...) are not subclasses of
    the built-in ``ConnectionError``/``TimeoutError``, so a tuple of built-in types never matches them,
    while the default ``retry_on`` retries them all, 400 and 401 included. This classifies them through
    :func:`explain_model_error`. LangGraph's ``NodeTimeoutError`` (a node ran past its ``TimeoutPolicy``)
    counts as a timeout.

    Retry in ONE layer: if a graph node retries with this, build its model with ``max_retries=0``,
    or every graph attempt makes up to three SDK attempts.
    """
    if type(error).__name__ == "NodeTimeoutError":
        return True
    return explain_model_error(error).retryable


def _wait_text(seconds: float | None) -> str:
    if not seconds:
        return ""
    minutes, secs = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return " (Groq says: try again in " + (f"{hours}h {minutes}m" if hours else f"{minutes}m {secs}s" if minutes else f"{secs}s") + ")"


def friendly_model_error(error: BaseException) -> str | None:
    """A short, student-friendly explanation for a rate-limit error (429), or None for any other error.

    ``load_env()`` installs it in Jupyter, so a 429 in a notebook prints this instead of a long traceback.
    """
    info = explain_model_error(error)
    if info.kind not in ("rate_limit", "daily_limit"):
        return None
    used = re.search(r"Limit (\d+), Used (\d+)", str(error))
    usage = f" Used {int(used.group(2)):,} of {int(used.group(1)):,}." if used else ""
    if info.kind == "daily_limit":
        return ("⏸️ Groq's free-tier DAILY limit for this model is used up." + usage + _wait_text(info.retry_after)
                + "\n   Nothing is wrong with your code. Options: wait for the reset, or use another model's daily "
                  "allowance: put MASTERY_MODEL_FAST=qwen/qwen3.8-27b (or openai/gpt-oss-120b) in .env and restart "
                  "the kernel, or run the notebook OFFLINE (remove GROQ_API_KEY) to check your code for free.")
    return ("⏸️ Groq's per-minute rate limit (tokens or requests per minute) was hit, even after automatic retries."
            + usage + _wait_text(info.retry_after)
            + "\n   Nothing is wrong with your code. Wait a minute and re-run this cell, or run fewer questions at once.")


def safe_print(text: str, stream: Any = None) -> None:
    """print() that never crashes on a console that can't show emoji (Windows cp1252 when output is redirected)."""
    import sys

    stream = stream or sys.stdout
    try:
        print(text, file=stream)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"), file=stream)


def install_notebook_error_hints() -> bool:
    """In IPython/Jupyter, print :func:`friendly_model_error` above the traceback of a 429 (idempotent).

    The cell still fails (so "Run All" stops and test runners see the error); the student first sees
    what happened and what to do. Returns True when installed. Outside IPython it does nothing.
    """
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    shell = get_ipython()
    if shell is None:
        return False
    if getattr(shell, "_mastery_error_hints", False):
        return True

    def handler(self, etype, value, tb, tb_offset=None):
        message = None
        error = value
        while error is not None and message is None:   # the 429 may be wrapped (graph node, tool, ...)
            message = friendly_model_error(error)
            error = error.__cause__ or error.__context__
        if message:
            safe_print(message)
        return self.showtraceback((etype, value, tb), tb_offset=tb_offset)

    shell.set_custom_exc((Exception,), handler)
    shell._mastery_error_hints = True
    return True


def is_tool_use_failed(error: BaseException) -> bool:
    """True for Groq's ``400 tool_use_failed``: the model's tool call (or "answer" tool) came out malformed.

    The request itself was fine, so ONE retry usually succeeds. Use it as (part of) a ``retry_on``
    predicate, e.g. ``ModelRetryMiddleware(retry_on=lambda e: is_transient(e) or is_tool_use_failed(e))``.
    VERIFIED 2026-10-16 on a live run: ``Error code: 400 - {... 'code': 'tool_use_failed', 'failed_generation': ...}``.
    """
    return getattr(error, "status_code", None) == 400 and "tool_use_failed" in str(error)


# Groq models whose JSON-schema mode supports strict=True (constrained decoding: the reply always matches).
# VERIFIED 2026-10-16: https://console.groq.com/docs/structured-outputs ("Models with Strict Mode").
STRICT_SCHEMA_MODELS = ("openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b")


def structured_model(model: Any, schema: Any, *, include_raw: bool = False) -> Any:
    """``model.with_structured_output(schema)`` with the most reliable method the model supports.

    For Groq's gpt-oss and Qwen 3.8 models this is ``method="json_schema", strict=True``: Groq constrains decoding to
    the schema, so the reply cannot be malformed. The default ``function_calling`` can fail on these
    models with ``Unknown tool type: 'functions.<Schema>'`` or ``400 tool_use_failed`` (the model
    answered in prose). If the strict request is refused (e.g. a schema feature strict mode does not
    support), it falls back to ``function_calling``. Other models get the plain default.
    Do NOT use it on a model bound to tools: Groq does not combine structured outputs with tool use.
    """
    from langchain_core.runnables import RunnableWithFallbacks

    if isinstance(model, RunnableWithFallbacks):            # MASTERY_FALLBACK_MODELS: each model its best method
        return RunnableWithFallbacks(runnable=structured_model(model.runnable, schema, include_raw=include_raw),
                                     fallbacks=[structured_model(f, schema, include_raw=include_raw) for f in model.fallbacks],
                                     exceptions_to_handle=model.exceptions_to_handle)
    name = str(getattr(model, "model_name", "") or getattr(model, "model", ""))
    if name not in STRICT_SCHEMA_MODELS:
        return model.with_structured_output(schema, include_raw=include_raw)
    strict = model.with_structured_output(schema, method="json_schema", strict=True, include_raw=include_raw)
    return strict.with_fallbacks([model.with_structured_output(schema, method="function_calling",
                                                               include_raw=include_raw)])


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
