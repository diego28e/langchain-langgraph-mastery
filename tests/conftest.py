"""Shared pytest fixtures for the whole test suite."""

from __future__ import annotations

import pytest

# Every variable mastery reads. Tests start from a clean slate so the learner's
# real .env or shell can never change a test result (or leak a key into output).
_MASTERY_VARS = (
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "LANGSMITH_API_KEY",
    "LANGSMITH_TRACING",
    "LANGSMITH_PROJECT",
    "MASTERY_MODEL_FAST",
    "MASTERY_MODEL_REASONING",
    "MASTERY_MODEL_VISION",
    "MASTERY_BENCHMARK_MODEL",
    "MASTERY_BENCHMARK_MODEL_STRONG",
    "TYPESAFE_API_KEY",
    "TYPESAFE_BASE_URL",
    "MASTERY_DECISIONS_MODE",
    "MASTERY_DECISION_MODEL",
)


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove every course variable from the environment for one test."""
    for name in _MASTERY_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Print a loud warning at the top of the run if SSL_CERT_FILE is broken.

    We deliberately do NOT remove the variable for tests: a broken certificate
    setting must make the model tests fail with mastery.doctor's clear message,
    so the learner fixes their environment (Lesson 00.02, step 4b).
    """
    from mastery.doctor import check_ssl_env

    problems = check_ssl_env()
    if not problems:
        return ["mastery doctor: SSL certificate variables OK"]
    return ["!! mastery doctor: " + p for p in problems] + [
        "!! Model tests will fail until you fix this: see 00-02-create-course-env.md, step 4b."
    ]
