"""Deep Agents helpers for Module 11 (``deepagents`` 0.7.x). Introduced in Lesson 11.01.

The course keeps every ``deepagents`` call behind this small package, so a breaking change in the
pre-1.0 library touches one place (see the Module 11 README production note).
"""
from mastery.deep.factory import (
    DEFAULT_DEEP_MODEL,
    DOTFILE_PATTERNS,
    deny_everything_else,
    SECRET_PATTERNS,
    course_backend,
    secret_deny_rules,
    build_deep_agent,
    budget_middleware,
    deep_key_ready,
    deep_model,
    deep_model_spec,
    fallback_middleware,
    fallback_specs,
    run_stats,
)
from mastery.deep.evals import check_case, file_text, grounding, trajectory, trajectory_matches
from mastery.deep.sandbox import DockerSandbox, docker_available

__all__ = [
    "DEFAULT_DEEP_MODEL",
    "DOTFILE_PATTERNS",
    "deny_everything_else",
    "SECRET_PATTERNS",
    "course_backend",
    "secret_deny_rules",
    "build_deep_agent",
    "budget_middleware",
    "deep_key_ready",
    "deep_model",
    "deep_model_spec",
    "fallback_middleware",
    "fallback_specs",
    "run_stats",
    "DockerSandbox",
    "check_case",
    "file_text",
    "grounding",
    "trajectory",
    "trajectory_matches",
    "docker_available",
]
