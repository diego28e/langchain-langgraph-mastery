"""Custom auth for the Agent Server (Lesson 12.08): the same callers as apps/m12_service.

``@auth.authenticate`` turns the ``Authorization: Bearer …`` header into a user (demo API keys, or a
JWT when ``MASTERY_SERVICE_JWT_SECRET`` / ``JWKS_URL`` are set). ``@auth.on`` stamps every new
resource with its owner and filters reads by it; managers see everything. Runs act as the signed-in
customer: the server, not the client, sets the run's ``context``.
"""
from __future__ import annotations

from langgraph_sdk import Auth

from mastery.config import load_env
from mastery.service.settings import ServiceSettings

load_env()
_settings = ServiceSettings()
_principals = _settings.principals()
_verifier = _settings.token_verifier()

auth = Auth()


@auth.authenticate
async def authenticate(authorization: str | None) -> Auth.types.MinimalUserDict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    principal = _principals.get(token) if token else None
    if principal is None and _verifier is not None and token.count(".") == 2:
        principal = _verifier.principal(token)
    if principal is None:
        raise Auth.exceptions.HTTPException(status_code=401, detail="missing, unknown or expired credentials")
    return {"identity": principal.user_id, "role": principal.role, "permissions": [principal.role]}


@auth.on
async def owner_only(ctx: Auth.types.AuthContext, value: dict):
    """Default for every resource and action: stamp the owner on create, filter by it on read."""
    if "manager" in ctx.permissions:
        return None                                   # managers: no filter
    if isinstance(value, dict) and ctx.action in {"create", "create_run"}:
        value.setdefault("metadata", {})["owner"] = ctx.user.identity
    return {"owner": ctx.user.identity}


@auth.on.threads.create_run
async def act_as_owner(ctx: Auth.types.AuthContext, value: dict):
    """A customer's run always acts as that customer, whatever the request body says.

    Only a manager may answer the refund approval: a customer who sends ``command={"resume": …}``
    would otherwise approve their own refund.
    """
    if "manager" not in ctx.permissions:
        kwargs = value.setdefault("kwargs", {})
        if (kwargs.get("command") or {}).get("resume") is not None:
            raise Auth.exceptions.HTTPException(status_code=403, detail="only a manager can answer an approval")
        kwargs["context"] = {"customer_id": ctx.user.identity}
        value.setdefault("metadata", {})["owner"] = ctx.user.identity
        return {"owner": ctx.user.identity}
    return None


@auth.on.assistants
async def read_only_assistants(ctx: Auth.types.AuthContext, value: dict):
    """Everyone may use the deployed assistants; only managers may create or change them."""
    if ctx.action in {"create", "update", "delete"} and "manager" not in ctx.permissions:
        raise Auth.exceptions.HTTPException(status_code=403, detail="managers only")
    return None
