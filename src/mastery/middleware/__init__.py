"""mastery.middleware: reusable agent middleware for the course (Module 04).

- :class:`TokenBudgetMiddleware`: end or fail a run before it crosses a token budget.
- :class:`AuditLogMiddleware`: redacted JSONL log of model and tool events.
- :class:`RoleToolFilterMiddleware`: tools allowed per role from ``runtime.context``.
- :mod:`~mastery.middleware.redaction`: ``redact_text`` / ``redact_obj`` for logs and traces.
- :mod:`~mastery.middleware.injection`: cheap injection signals, ``fence_untrusted``,
  ``parse_guard_score`` (Llama Prompt Guard 2 replies).

All of them run offline; Lesson 04.03 builds simpler versions by hand first.
"""

from mastery.middleware.audit import AuditLogMiddleware, read_audit_log
from mastery.middleware.budget import BudgetState, TokenBudgetExceededError, TokenBudgetMiddleware
from mastery.middleware.injection import INJECTION_PATTERNS, fence_untrusted, injection_signals, parse_guard_score
from mastery.middleware.redaction import PII_PATTERNS, redact_obj, redact_text
from mastery.middleware.roles import RoleToolFilterMiddleware, role_from_context

__all__ = [
    "INJECTION_PATTERNS",
    "PII_PATTERNS",
    "AuditLogMiddleware",
    "BudgetState",
    "RoleToolFilterMiddleware",
    "TokenBudgetExceededError",
    "TokenBudgetMiddleware",
    "fence_untrusted",
    "injection_signals",
    "parse_guard_score",
    "read_audit_log",
    "redact_obj",
    "redact_text",
    "role_from_context",
]
