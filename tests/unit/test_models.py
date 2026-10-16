"""Unit tests for mastery.models. Offline: no network, no real keys.

Building a chat model object never calls the provider, so get_model() can be
tested with an obviously fake key. Error classification is tested with
hand-made exception objects that look like the SDK errors.
"""

from __future__ import annotations

import warnings

import pytest

pytest.importorskip("langchain_groq", reason="needs the llm extra: pip install -e '.[dev]'")

from mastery.config import MissingSettingError, Settings
from mastery.models import (
    PREVIEW_MODELS,
    PreviewModelWarning,
    describe_model,
    explain_model_error,
    get_model,
    model_string,
    split_model_string,
)

FAKE_GROQ_KEY = "gsk_unit_test_fake_key_0000000000"


# --- split_model_string / model_string ---------------------------------------

def test_split_uses_only_the_first_colon() -> None:
    assert split_model_string("groq:openai/gpt-oss-20b") == ("groq", "openai/gpt-oss-20b")
    assert split_model_string("ollama:llama3.2:3b") == ("ollama", "llama3.2:3b")


@pytest.mark.parametrize("bad", ["openai/gpt-oss-20b", ":model", "groq:", ""])
def test_split_rejects_strings_without_provider(bad: str) -> None:
    with pytest.raises(ValueError, match="provider:model"):
        split_model_string(bad)


def test_model_string_reads_roles_from_settings() -> None:
    settings = Settings(model_fast="a/fast", model_reasoning="b/think", model_vision="c/see")
    assert model_string("fast", settings=settings) == "groq:a/fast"
    assert model_string("reasoning", settings=settings) == "groq:b/think"
    assert model_string("vision", settings=settings) == "groq:c/see"


def test_model_string_benchmark_maps_reasoning_to_strong_model() -> None:
    settings = Settings(benchmark_model="openai:cheap", benchmark_model_strong="openai:strong")
    assert model_string("fast", "benchmark", settings=settings) == "openai:cheap"
    assert model_string("reasoning", "benchmark", settings=settings) == "openai:strong"
    assert model_string("vision", "benchmark", settings=settings) == "openai:cheap"


def test_model_string_reads_env_through_load_settings(isolated_env: pytest.MonkeyPatch) -> None:
    isolated_env.setenv("MASTERY_MODEL_FAST", "from/env")
    # load_settings() also loads .env, but real env vars win (override=False).
    assert model_string("fast") == "groq:from/env"


@pytest.mark.parametrize(("role", "provider"), [("huge", "groq"), ("fast", "anthropic")])
def test_model_string_rejects_unknown_role_or_provider(role: str, provider: str) -> None:
    with pytest.raises(ValueError):
        model_string(role, provider, settings=Settings())


# --- get_model ----------------------------------------------------------------

def test_get_model_builds_chatgroq_with_course_defaults(isolated_env: pytest.MonkeyPatch) -> None:
    isolated_env.setenv("GROQ_API_KEY", FAKE_GROQ_KEY)
    llm = get_model("fast", settings=Settings(model_fast="openai/gpt-oss-20b"))
    assert type(llm).__name__ == "ChatGroq"
    assert llm.model_name == "openai/gpt-oss-20b"
    assert llm.max_retries == 2
    assert llm.request_timeout == 60.0
    assert llm.temperature == 0.7  # temperature=None keeps ChatGroq's own default (0.7).


def test_get_model_passes_explicit_parameters(isolated_env: pytest.MonkeyPatch) -> None:
    isolated_env.setenv("GROQ_API_KEY", FAKE_GROQ_KEY)
    llm = get_model(model="groq:openai/gpt-oss-120b", temperature=0.0, max_tokens=50, reasoning_effort="low")
    assert llm.model_name == "openai/gpt-oss-120b"
    assert llm.temperature == 1e-8  # ChatGroq replaces 0 with 1e-8 (langchain-groq source).
    assert llm.max_tokens == 50
    assert llm.reasoning_effort == "low"


def test_get_model_without_key_raises_friendly_error(isolated_env: pytest.MonkeyPatch) -> None:
    with pytest.raises(MissingSettingError) as info:
        get_model("fast", settings=Settings())
    assert "GROQ_API_KEY" in str(info.value)
    assert "https://console.groq.com/keys" in str(info.value)


def test_get_model_check_key_false_skips_the_check(isolated_env: pytest.MonkeyPatch) -> None:
    # ChatGroq itself still wants a key; passing one explicitly is the offline-inspection pattern.
    llm = get_model("fast", settings=Settings(), check_key=False, api_key=FAKE_GROQ_KEY)
    assert type(llm).__name__ == "ChatGroq"


def test_gemini_accepts_either_key_name(isolated_env: pytest.MonkeyPatch) -> None:
    from mastery.models import _require_provider_key

    with pytest.raises(MissingSettingError):
        _require_provider_key("google_genai")
    isolated_env.setenv("GEMINI_API_KEY", "fake-gemini-key-for-tests-123456")
    _require_provider_key("google_genai")  # No error now.


def test_preview_model_emits_warning(isolated_env: pytest.MonkeyPatch) -> None:
    isolated_env.setenv("GROQ_API_KEY", FAKE_GROQ_KEY)
    assert "qwen/qwen3.8-27b" in PREVIEW_MODELS
    with pytest.warns(PreviewModelWarning, match="PREVIEW"):
        get_model("vision", settings=Settings(model_vision="qwen/qwen3.8-27b"))


def test_production_model_emits_no_preview_warning(isolated_env: pytest.MonkeyPatch) -> None:
    isolated_env.setenv("GROQ_API_KEY", FAKE_GROQ_KEY)
    with warnings.catch_warnings():
        warnings.simplefilter("error", PreviewModelWarning)
        get_model("fast", settings=Settings())


def test_missing_provider_package_gives_install_hint(
    isolated_env: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    import langchain.chat_models as chat_models

    def fake_init_chat_model(*args: object, **kwargs: object) -> None:
        raise ImportError("No module named 'langchain_openai'")

    monkeypatch.setattr(chat_models, "init_chat_model", fake_init_chat_model)
    isolated_env.setenv("OPENAI_API_KEY", "sk-not-a-real-key")
    with pytest.raises(ImportError, match='pip install "langchain-openai"'):
        get_model(model="openai:gpt-6-luna")


def test_describe_model_reports_profile_fields(isolated_env: pytest.MonkeyPatch) -> None:
    isolated_env.setenv("GROQ_API_KEY", FAKE_GROQ_KEY)
    info = describe_model(get_model("reasoning", settings=Settings()))
    assert info["class"] == "ChatGroq"
    assert info["model"] == "openai/gpt-oss-120b"
    assert info["max_retries"] == 2
    assert set(info) >= {"max_input_tokens", "image_inputs", "structured_output"}


# --- explain_model_error --------------------------------------------------------

class _FakeResponse:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


class _FakeSDKError(Exception):
    """Looks like groq.APIStatusError: has status_code and response.headers."""

    def __init__(self, status_code: int, message: str = "", headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = _FakeResponse(headers or {})


@pytest.mark.parametrize(
    ("status", "message", "kind", "retryable"),
    [
        (401, "Invalid API Key", "auth", False),
        (403, "forbidden", "permission", False),
        (404, "model not found", "not_found", False),
        (400, "The model `x` has been decommissioned", "not_found", False),
        (400, "bad schema", "invalid_request", False),
        (413, "too large", "context_overflow", False),
        (500, "oops", "server", True),
        (503, "busy", "server", True),
        (498, "capacity_exceeded", "server", True),
    ],
)
def test_sdk_errors_are_classified_by_status(status: int, message: str, kind: str, retryable: bool) -> None:
    info = explain_model_error(_FakeSDKError(status, message))
    assert (info.kind, info.retryable, info.status_code) == (kind, retryable, status)
    assert info.hint


def test_rate_limit_reads_retry_after_header() -> None:
    info = explain_model_error(_FakeSDKError(429, "Rate limit reached", {"retry-after": "7"}))
    assert info.kind == "rate_limit"
    assert info.retryable is True
    assert info.retry_after == 7.0


def test_langchain_standard_exceptions_are_recognized() -> None:
    from langchain_core.exceptions import ModelRateLimitError

    error = ModelRateLimitError.__new__(ModelRateLimitError)  # Avoid provider-specific __init__ args.
    Exception.__init__(error, "slow down")
    assert explain_model_error(error).kind == "rate_limit"


@pytest.mark.parametrize(
    ("error", "kind"),
    [(TimeoutError("t"), "timeout"), (ConnectionError("c"), "connection"), (ValueError("v"), "unknown")],
)
def test_errors_without_status_code(error: Exception, kind: str) -> None:
    assert explain_model_error(error).kind == kind


def test_is_transient_classifies_provider_errors() -> None:
    import httpx
    from langgraph.errors import NodeTimeoutError

    groq = pytest.importorskip("groq")
    from mastery.models import is_transient

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")

    def status_error(cls, code):
        return cls("x", response=httpx.Response(code, request=request), body=None)

    assert not is_transient(status_error(groq.BadRequestError, 400))
    assert not is_transient(status_error(groq.AuthenticationError, 401))
    assert is_transient(status_error(groq.RateLimitError, 429))
    assert is_transient(status_error(groq.InternalServerError, 503))
    assert is_transient(groq.APIConnectionError(request=request))
    assert is_transient(groq.APITimeoutError(request=request))
    assert is_transient(ConnectionError("reset")) and is_transient(TimeoutError("slow"))
    assert is_transient(NodeTimeoutError("search_web", 0.3, kind="run", run_timeout=0.3))
    assert not is_transient(ValueError("bug")) and not is_transient(KeyError("k"))


def test_is_tool_use_failed_only_matches_groq_tool_use_failed() -> None:
    import httpx

    groq = pytest.importorskip("groq")
    from mastery.models import is_tool_use_failed

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    body = {"error": {"message": "Tool choice is required, but model did not call a tool", "code": "tool_use_failed"}}
    failed = groq.BadRequestError(f"Error code: 400 - {body}", response=httpx.Response(400, request=request), body=body)
    other = groq.BadRequestError("Error code: 400 - bad schema", response=httpx.Response(400, request=request), body=None)
    assert is_tool_use_failed(failed)
    assert not is_tool_use_failed(other) and not is_tool_use_failed(ValueError("tool_use_failed"))


def test_structured_model_uses_strict_json_schema_on_gpt_oss() -> None:
    from langchain_core.runnables import RunnableWithFallbacks
    from pydantic import BaseModel

    from mastery.models import structured_model

    class Grade(BaseModel):
        relevant: bool

    bound = structured_model(get_model(model="groq:openai/gpt-oss-20b", check_key=False, api_key=FAKE_GROQ_KEY), Grade)
    assert isinstance(bound, RunnableWithFallbacks)
    response_format = bound.runnable.first.kwargs["response_format"]
    assert response_format["type"] == "json_schema" and response_format["json_schema"]["strict"] is True
    fallback_tools = bound.fallbacks[0].first.kwargs["tools"]
    assert fallback_tools[0]["function"]["name"] == "Grade"
    # Models without strict mode keep the integration's default method (no fallback layer).
    other = structured_model(get_model(model="groq:llama-3.1-8b-instant", check_key=False, api_key=FAKE_GROQ_KEY), Grade)
    assert not isinstance(other, RunnableWithFallbacks)


def _groq_429(message: str, headers: dict | None = None):
    import httpx

    groq = pytest.importorskip("groq")
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return groq.RateLimitError(message, response=httpx.Response(429, request=request, headers=headers or {}), body=None)


TPD_429 = ("Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` in organization "
           "`org_x` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199914, Requested 1043. "
           "Please try again in 6m19.872s.', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}")
TPM_429 = ("Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-20b` ... on tokens per "
           "minute (TPM): Limit 8000, Used 7200, Requested 1500. Please try again in 5.25s.', 'code': 'rate_limit_exceeded'}}")


def test_parse_try_again_in() -> None:
    from mastery.models import parse_try_again_in

    assert parse_try_again_in("Please try again in 6m19.872s.") == pytest.approx(379.872)
    assert parse_try_again_in("try again in 1h2m3s") == pytest.approx(3723)
    assert parse_try_again_in("try again in 250ms") == pytest.approx(0.25)
    assert parse_try_again_in("no hint here") is None


def test_daily_limit_429_is_not_transient_but_minute_limit_is() -> None:
    from mastery.models import friendly_model_error, is_transient

    daily, minute = _groq_429(TPD_429), _groq_429(TPM_429, {"retry-after": "6"})
    assert explain_model_error(daily).kind == "daily_limit" and not is_transient(daily)
    assert explain_model_error(daily).retry_after == pytest.approx(379.872)
    assert explain_model_error(minute).kind == "rate_limit" and is_transient(minute)
    assert explain_model_error(minute).retry_after == 6.0
    assert "DAILY" in friendly_model_error(daily) and "199,914 of 200,000" in friendly_model_error(daily)
    assert "per-minute" in friendly_model_error(minute)
    assert friendly_model_error(ValueError("bug")) is None


def test_qwen_gets_parsed_reasoning_and_env_raises_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MASTERY_MAX_RETRIES", "6")
    with pytest.warns(PreviewModelWarning):
        llm = get_model(model="groq:qwen/qwen3.8-27b", check_key=False, api_key=FAKE_GROQ_KEY)
    assert llm.reasoning_format == "parsed" and llm.max_retries == 6
    assert get_model(model="groq:openai/gpt-oss-20b", check_key=False, api_key=FAKE_GROQ_KEY, max_retries=1).max_retries == 1


def test_safe_print_survives_a_cp1252_stream() -> None:
    import io

    from mastery.models import safe_print

    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")
    safe_print("⏸️ limit → 💸 ok", stream=stream)
    stream.flush()
    assert raw.getvalue().decode("cp1252").strip().endswith("ok")


def test_otpm_413_is_an_output_limit() -> None:
    import httpx

    groq = pytest.importorskip("groq")
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    message = ("Error code: 413 - Request too large for model `qwen/qwen3.8-27b` ... on output tokens per minute "
               "(OTPM): Limit 1000, Requested 1319")
    error = groq.APIStatusError(message, response=httpx.Response(413, request=request), body=None)
    assert explain_model_error(error).kind == "output_limit"


from pydantic import BaseModel as BaseModelForTest  # noqa: E402


def test_fallback_models_env_wraps_role_models_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from langchain_core.runnables import RunnableWithFallbacks

    monkeypatch.setenv("GROQ_API_KEY", FAKE_GROQ_KEY)
    monkeypatch.setenv("MASTERY_FALLBACK_MODELS", "groq:openai/gpt-oss-120b, openai/gpt-oss-20b")
    llm = get_model("fast", settings=Settings(model_fast="openai/gpt-oss-20b"), reasoning_effort="low")
    assert isinstance(llm, RunnableWithFallbacks) and len(llm.fallbacks) == 2
    assert [f.model_name for f in llm.fallbacks] == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    assert llm.model_name == "openai/gpt-oss-20b"                      # plain attributes: from the primary
    from mastery.models import structured_model

    class Grade(BaseModelForTest):
        relevant: bool

    bound = structured_model(llm, Grade)
    assert isinstance(bound, RunnableWithFallbacks) and len(bound.fallbacks) == 2
    assert type(llm.bind_tools([])).__name__.endswith("Fallbacks")
    assert not isinstance(get_model(model="groq:openai/gpt-oss-20b"), RunnableWithFallbacks)
    monkeypatch.delenv("MASTERY_FALLBACK_MODELS")
    assert not isinstance(get_model("fast", settings=Settings(model_fast="openai/gpt-oss-20b")), RunnableWithFallbacks)
