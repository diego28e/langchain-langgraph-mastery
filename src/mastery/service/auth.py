"""Signed tokens (JWT) for the service: verify on every request, issue only in demos (Lesson 12.05).

In production an identity provider (Auth0, Clerk, Supabase Auth, Microsoft Entra, Google…) signs
short-lived tokens with its **private** key (RS256/ES256) and publishes the public keys at a JWKS URL;
the service only **verifies**. :class:`TokenVerifier` does that with PyJWT and pins everything an
attacker could otherwise choose: the algorithm list, issuer, audience, and required claims.

For the offline demo we also sign tokens ourselves with a shared secret (HS256, :func:`issue_token`).
A service that can mint tokens is a bigger target, so real deployments don't.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from mastery.service.settings import Principal

ROLES = frozenset({"customer", "manager"})


def issue_token(secret: str, subject: str, *, role: str = "customer", issuer: str = "mastery-demo",
                audience: str = "agent-service", ttl_s: int = 900, now: float | None = None) -> str:
    """Sign a demo HS256 token for ``subject`` (user id) with ``role``, valid for ``ttl_s`` seconds."""
    import jwt

    issued = int(now if now is not None else time.time())
    claims = {"sub": subject, "role": role, "iss": issuer, "aud": audience,
              "iat": issued, "nbf": issued, "exp": issued + ttl_s, "jti": uuid.uuid4().hex}
    return jwt.encode(claims, secret, algorithm="HS256")


@dataclass
class TokenVerifier:
    """Verify JWTs and turn their claims into a :class:`Principal`.

    Give exactly one key source: ``secret`` (HS256, demo), ``public_key`` (PEM, RS256/ES256) or
    ``jwks_url`` (your identity provider; keys are fetched and cached by ``PyJWKClient``).
    """

    issuer: str
    audience: str
    secret: str | None = None
    public_key: Any = None
    jwks_url: str | None = None
    algorithms: tuple[str, ...] = ("HS256",)
    leeway_s: int = 30
    role_claim: str = "role"
    last_error: str | None = field(default=None, repr=False)
    _jwks: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if sum(x is not None for x in (self.secret, self.public_key, self.jwks_url)) != 1:
            raise ValueError("give exactly one of secret, public_key or jwks_url")
        if "none" in {a.lower() for a in self.algorithms}:
            raise ValueError("the 'none' algorithm is never acceptable")

    def _key(self, token: str) -> Any:
        if self.secret is not None:
            return self.secret
        if self.public_key is not None:
            return self.public_key
        import jwt

        if self._jwks is None:
            self._jwks = jwt.PyJWKClient(self.jwks_url, cache_keys=True)
        return self._jwks.get_signing_key_from_jwt(token).key

    def claims(self, token: str) -> dict[str, Any]:
        """Decoded claims; raises ``jwt.InvalidTokenError`` (expired, wrong audience, bad signature…)."""
        import jwt

        return jwt.decode(token, self._key(token), algorithms=list(self.algorithms), audience=self.audience,
                          issuer=self.issuer, leeway=self.leeway_s,
                          options={"require": ["exp", "iat", "sub", "iss", "aud"]})

    def principal(self, token: str) -> Principal | None:
        """The caller, or ``None`` when the token is not valid (the reason is kept in ``last_error``)."""
        import jwt

        try:
            claims = self.claims(token)
        except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None
        role = claims.get(self.role_claim, "customer")
        if role not in ROLES:
            self.last_error = f"unknown role {role!r}"
            return None
        self.last_error = None
        return Principal(str(claims["sub"]), role)
