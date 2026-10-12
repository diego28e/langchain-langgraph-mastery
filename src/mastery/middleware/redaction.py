"""Deterministic redaction for logs and traces (no model, no network).

``PIIMiddleware`` (LangChain) changes what the *model* sees. These helpers clean
what *you* write down: audit logs, debug prints, trace payloads. Both are needed,
because a tool argument or a model reply can contain PII the user never typed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

__all__ = ["PII_PATTERNS", "redact_obj", "redact_text"]

#: Name -> compiled pattern. Order matters: card numbers before phone numbers.
PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "ip": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "phone": re.compile(r"(?<![\w-])(?:\+?\d{1,3}[ .-]?)?(?:\(\d{2,4}\)|\d{2,4})[ .-]?\d{3,4}[ .-]?\d{3,4}\b"),
    "api_key": re.compile(r"\b(?:gsk|sk|lsv2|tvly)[_-][A-Za-z0-9_-]{8,}\b"),
}


def redact_text(text: str, patterns: Mapping[str, re.Pattern[str]] | None = None) -> str:
    """Replace every match with ``[REDACTED_<NAME>]``.

    Args:
        text: Any string.
        patterns: Name -> compiled regex. Defaults to :data:`PII_PATTERNS`.

    Returns:
        The text with matches replaced, for example
        ``"mail ana@example.com"`` -> ``"mail [REDACTED_EMAIL]"``.
    """
    for name, pattern in (patterns or PII_PATTERNS).items():
        text = pattern.sub(f"[REDACTED_{name.upper()}]", text)
    return text


def redact_obj(obj: Any, patterns: Mapping[str, re.Pattern[str]] | None = None) -> Any:
    """Redact strings inside dicts, lists and tuples (returns a new object)."""
    if isinstance(obj, str):
        return redact_text(obj, patterns)
    if isinstance(obj, Mapping):
        return {k: redact_obj(v, patterns) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(redact_obj(v, patterns) for v in obj)
    return obj
