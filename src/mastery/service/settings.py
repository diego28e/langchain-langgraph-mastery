"""Service settings from environment variables (and ``.env``), validated once at startup (Lesson 12.04).

``pydantic-settings`` reads ``MASTERY_SERVICE_*`` variables, converts types and fails fast with a
clear message when one is wrong, before the first request rather than during it.

API keys map a secret to a user and a role: ``MASTERY_SERVICE_API_KEYS="key1=C-1002:customer,key2=ops:manager"``.
Lesson 12.05 adds signed tokens (JWT: ``JWT_SECRET`` for the demo, ``JWKS_URL`` for an identity
provider) and durable state (``DATABASE_URL``: ``sqlite:///file.db`` or ``postgresql://…``).
Lessons 12.06–12.07 add ``DRAIN_S`` (graceful shutdown), ``LOG_FORMAT`` (``json`` in containers),
``METRICS_TOKEN`` and ``RELEASE``.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Keys for the offline DEMO only: they grant nothing outside your own machine.
DEMO_API_KEYS = "demo-customer=C-1002:customer,demo-other=C-1001:customer,demo-manager=ops:manager"


@dataclass(frozen=True)
class Principal:
    """Who is calling: ``user_id`` (a customer id for customers) and ``role`` (``customer`` or ``manager``)."""

    user_id: str
    role: str


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MASTERY_SERVICE_", env_file=".env", extra="ignore")

    mode: str = Field("demo", description="demo (offline model) or live (Groq)")
    api_keys: SecretStr = SecretStr(DEMO_API_KEYS)
    max_concurrent: int = Field(4, ge=1, le=256)
    max_queue: int = Field(50, ge=0)
    run_timeout_s: float = Field(120.0, gt=0)
    max_message_chars: int = Field(4000, ge=1)
    budget_per_request_usd: float = 0.002
    budget_per_user_day_usd: float = 0.05
    budget_global_day_usd: float = 1.0
    database_url: SecretStr | None = Field(None, description="sqlite:///file.db or postgresql://user:pass@host/db")
    jwt_secret: SecretStr | None = None            # demo HS256 tokens
    jwks_url: str | None = None                    # an identity provider's public keys (RS256)
    jwt_issuer: str = "mastery-demo"
    jwt_audience: str = "agent-service"
    jwt_algorithms: str = "HS256"                  # comma-separated; with jwks_url use e.g. RS256
    # Lesson 12.06: graceful shutdown. Lesson 12.07: logs, metrics, trace metadata.
    drain_s: float = Field(10.0, ge=0, description="on shutdown, seconds to let active runs finish")
    log_format: str = Field("text", pattern="^(json|text)$")
    log_level: str = "WARNING"                     # INFO adds one line per request and per run
    metrics_token: SecretStr | None = None         # when set, GET /metrics needs this bearer token
    demo_fail_rate: float = Field(0.0, ge=0, le=1, description="DEMO only: share of model calls that fail (incident drills)")
    release: str = Field("dev", description="version label in logs, metrics and traces (e.g. a git sha)")
    paused: bool = Field(False, description="kill switch: refuse new runs with 503 (Lesson 12.09)")
    public: bool = Field(False, description="internet-facing: refuse demo keys, short keys and short JWT secrets")

    @model_validator(mode="after")
    def _public_is_locked_down(self) -> "ServiceSettings":
        """A public deployment must not start with the demo keys (anyone can read them in this repo)."""
        if not self.public:
            return self
        problems = []
        demo = {e.split("=", 1)[0] for e in DEMO_API_KEYS.split(",")}
        keys = [e.strip().split("=", 1)[0] for e in self.api_keys.get_secret_value().split(",") if e.strip()]
        if any(k in demo for k in keys):
            problems.append("MASTERY_SERVICE_API_KEYS still contains a demo key")
        if any(len(k) < 24 for k in keys):
            problems.append("every API key must have at least 24 characters (python -c \"import secrets; print(secrets.token_urlsafe(24))\")")
        if self.jwt_secret is not None and len(self.jwt_secret.get_secret_value()) < 32:
            problems.append("MASTERY_SERVICE_JWT_SECRET must have at least 32 characters")
        if problems:
            raise ValueError("public=True but: " + "; ".join(problems))
        return self

    @field_validator("mode")
    @classmethod
    def _mode(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"demo", "live"}:
            raise ValueError("mode must be 'demo' or 'live'")
        return value

    def database(self) -> str | None:
        return self.database_url.get_secret_value() if self.database_url else None

    def token_verifier(self):  # noqa: ANN201  (mastery.service.auth.TokenVerifier | None)
        """A verifier when JWT settings are given, else ``None`` (API keys only)."""
        if not self.jwt_secret and not self.jwks_url:
            return None
        from mastery.service.auth import TokenVerifier

        return TokenVerifier(issuer=self.jwt_issuer, audience=self.jwt_audience,
                             secret=self.jwt_secret.get_secret_value() if self.jwt_secret else None,
                             jwks_url=None if self.jwt_secret else self.jwks_url,
                             algorithms=tuple(a.strip() for a in self.jwt_algorithms.split(",") if a.strip()))

    def principals(self) -> dict[str, Principal]:
        """Parse ``api_keys`` into ``{secret: Principal}``; malformed entries raise ``ValueError``."""
        table: dict[str, Principal] = {}
        for entry in filter(None, (e.strip() for e in self.api_keys.get_secret_value().split(","))):
            secret, _, who = entry.partition("=")
            user, _, role = who.partition(":")
            if not secret or not user or role not in {"customer", "manager"}:
                raise ValueError("MASTERY_SERVICE_API_KEYS entries look like key=user:customer or key=user:manager")
            table[secret] = Principal(user, role)
        return table
