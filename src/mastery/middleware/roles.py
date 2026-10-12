"""``RoleToolFilterMiddleware``: least privilege for tools, decided per request.

The role comes from ``runtime.context`` (set by *your* code when you invoke the
agent, never by the model or the user's text). Two layers:

1. ``wrap_model_call`` hides tools the role may not use, so the model never sees them.
2. ``wrap_tool_call`` refuses any call to a hidden tool anyway (defence in depth:
   a model can still emit a call by name, for example after a prompt injection).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

__all__ = ["RoleToolFilterMiddleware", "role_from_context"]


def role_from_context(context: Any, key: str = "role") -> str | None:
    """Read ``key`` from a dict, dataclass, Pydantic model or any object."""
    if context is None:
        return None
    if isinstance(context, Mapping):
        value = context.get(key)
    else:
        value = getattr(context, key, None)
    return None if value is None else str(value)


def _tool_name(tool: Any) -> str | None:
    if isinstance(tool, Mapping):
        return tool.get("name") or (tool.get("function") or {}).get("name")
    return getattr(tool, "name", None)


class RoleToolFilterMiddleware(AgentMiddleware):
    """Allow each role only the tools in ``policy``; unknown roles get ``default_role``.

    Args:
        policy: Role -> tool names. Use ``"*"`` to allow every tool.
        role_key: Field of ``runtime.context`` that holds the role.
        default_role: Role used when the context has none or an unknown one.
            ``None`` (default) means *fail closed*: no tools at all.
        always_allowed: Tool names every role keeps (for example ``write_todos``).

    Example:
        >>> RoleToolFilterMiddleware({"viewer": ["list_emails"], "admin": ["*"]})  # doctest: +ELLIPSIS
        <...RoleToolFilterMiddleware object at ...>
    """

    def __init__(
        self,
        policy: Mapping[str, Iterable[str]],
        *,
        role_key: str = "role",
        default_role: str | None = None,
        always_allowed: Iterable[str] = (),
    ) -> None:
        super().__init__()
        self.policy = {role: frozenset(names) for role, names in policy.items()}
        if default_role is not None and default_role not in self.policy:
            raise ValueError(f"default_role {default_role!r} is not in the policy.")
        self.role_key = role_key
        self.default_role = default_role
        self.always_allowed = frozenset(always_allowed)

    def role_for(self, context: Any) -> str | None:
        """The effective role for a context (after applying ``default_role``)."""
        role = role_from_context(context, self.role_key)
        return role if role in self.policy else self.default_role

    def allowed(self, context: Any, tool_name: str) -> bool:
        """True if the role in ``context`` may use ``tool_name``."""
        if tool_name in self.always_allowed:
            return True
        role = self.role_for(context)
        names = self.policy.get(role, frozenset()) if role else frozenset()
        return "*" in names or tool_name in names

    def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        context = getattr(request.runtime, "context", None)
        tools = [t for t in request.tools if self.allowed(context, _tool_name(t) or "")]
        return handler(request.override(tools=tools))

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        context = getattr(getattr(request, "runtime", None), "context", None)
        name = request.tool_call["name"]
        if self.allowed(context, name):
            return handler(request)
        role = self.role_for(context) or "none"
        return ToolMessage(
            content=f"Tool '{name}' is not allowed for role '{role}'. Do not call it again.",
            tool_call_id=request.tool_call["id"], name=name, status="error",
        )
