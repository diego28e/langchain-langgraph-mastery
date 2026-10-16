"""Logs, request ids and metrics for the agent service (Lesson 12.07).

Three signals, each answering a different question:

* **Structured logs** (one JSON object per line): *what happened to this request or run?*
  Every line carries the ``request_id``; run lines also carry ``run_id``, ``thread_id`` and ``user_id``.
* **Metrics** (Prometheus text format on ``GET /metrics``): *how is the service doing overall?*
  Request rate and latency per route, run outcomes, TTFT, queue wait, tokens and dollars.
* **Traces** (LangSmith or OpenTelemetry, Module 10): *what did the agent do inside one run?*
  :meth:`mastery.service.runs.RunManager.config_for` puts the same ids in each trace's metadata,
  so a log line leads to its trace.

Nothing here logs message text, answers or credentials: ids, timings, sizes and counts only.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

LOGGER_NAME = "mastery.service"
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
# Fields copied from a log call's ``extra=`` into the JSON line (an allowlist: nothing else leaks in).
FIELDS = ("event", "request_id", "method", "route", "status", "duration_ms", "user_id", "run_id",
          "thread_id", "run_status", "queue_s", "ttft_s", "duration_s", "tokens", "cost_usd", "error", "count")


class JsonFormatter(logging.Formatter):
    """One JSON object per line: easy for Docker, Loki, CloudWatch or ``jq`` to search."""

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(), "logger": record.name, "msg": record.getMessage(),
        }
        if "request_id" not in record.__dict__ and request_id_var.get():
            line["request_id"] = request_id_var.get()
        for name in FIELDS:
            if name in record.__dict__ and record.__dict__[name] is not None:
                line[name] = record.__dict__[name]
        if record.exc_info:
            line["exc"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


def configure_logging(fmt: str = "json", level: str = "INFO") -> logging.Logger:
    """Send ``mastery.service`` logs to stderr as JSON (``fmt="json"``) or plain text. Safe to call twice."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level.upper())
    for handler in [h for h in logger.handlers if getattr(h, "_mastery", False)]:
        logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler._mastery = True  # type: ignore[attr-defined]
    handler.setFormatter(JsonFormatter() if fmt == "json" else
                         logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class ServiceMetrics:
    """Prometheus metrics in their own registry (two apps in one process don't collide).

    Labels stay low-cardinality: the route *template* (``/runs/{run_id}``), never the raw path,
    and never a user or thread id (one time series per user would swamp the metrics store).
    """

    def __init__(self, registry: CollectorRegistry | None = None, prefix: str = "agent") -> None:
        self.registry = registry or CollectorRegistry()
        r, p = self.registry, prefix
        self.requests = Counter(f"{p}_http_requests", "HTTP requests", ["method", "route", "status"], registry=r)
        self.request_seconds = Histogram(f"{p}_http_request_seconds", "HTTP request latency", ["method", "route"],
                                         buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10), registry=r)
        self.runs = Counter(f"{p}_runs", "Finished runs by status", ["status"], registry=r)
        latency = (0.25, 0.5, 1, 2, 3, 5, 8, 13, 20, 30, 60, 120)
        self.ttft = Histogram(f"{p}_run_ttft_seconds", "Submit to first token (or approval request)",
                              buckets=latency, registry=r)
        self.run_seconds = Histogram(f"{p}_run_duration_seconds", "Submit to end", buckets=latency, registry=r)
        self.queue_seconds = Histogram(f"{p}_run_queue_seconds", "Submit to start", buckets=(0, *latency), registry=r)
        self.tokens = Counter(f"{p}_tokens", "Model tokens", ["kind"], registry=r)
        self.cost = Counter(f"{p}_cost_usd", "Estimated model spend (USD)", registry=r)
        self.active = Gauge(f"{p}_runs_running", "Runs executing now", registry=r)
        self.queued = Gauge(f"{p}_runs_queued", "Runs waiting for a slot", registry=r)

    def watch(self, manager: Any) -> None:
        """Read the running and queued gauges from ``manager`` at scrape time, and record each run as it ends."""
        self.active.set_function(lambda: sum(run.status == "running" for run in manager.runs.values()))
        self.queued.set_function(lambda: manager.queued)
        manager.listeners.append(self.observe_run)

    def observe_request(self, method: str, route: str, status: int, seconds: float) -> None:
        self.requests.labels(method, route, str(status)).inc()
        self.request_seconds.labels(method, route).observe(seconds)

    def observe_run(self, run: Any) -> None:
        self.runs.labels(run.status).inc()
        if run.first_token_at is not None:
            self.ttft.observe(run.first_token_at - run.created_at)
        if run.ended_at is not None:
            self.run_seconds.observe(run.ended_at - run.created_at)
        self.queue_seconds.observe((run.started_at or run.created_at) - run.created_at)
        for kind in ("input_tokens", "output_tokens"):
            if run.usage.get(kind):
                self.tokens.labels(kind.removesuffix("_tokens")).inc(run.usage[kind])
        if run.cost_usd:
            self.cost.inc(run.cost_usd)

    def render(self) -> tuple[bytes, str]:
        return generate_latest(self.registry), CONTENT_TYPE_LATEST


def log_run(run: Any) -> None:
    """A run listener: one ``run.finished`` log line with ids, timings, tokens and cost (no text)."""
    public = run.public()
    level = logging.WARNING if run.status in {"error", "timeout"} else logging.INFO
    logging.getLogger(LOGGER_NAME).log(level, "run finished", extra={
        "event": "run.finished", "request_id": getattr(run, "request_id", None), "run_id": run.run_id,
        "thread_id": run.thread_id, "user_id": run.user_id, "run_status": run.status,
        "queue_s": public["queue_s"], "ttft_s": public["ttft_s"], "duration_s": public["duration_s"],
        "tokens": run.usage.get("total_tokens"), "cost_usd": public["cost_usd"], "error": run.error})


class RequestContextMiddleware:
    """Pure ASGI middleware (safe with SSE streams): request id, one access log line, request metrics.

    Reuses a well-formed incoming ``X-Request-ID`` (from a proxy or the client), else makes one, and
    returns it on the response so a user's bug report can quote it.
    """

    def __init__(self, app: Any, metrics: ServiceMetrics | None = None, skip: tuple[str, ...] = ("/metrics",)) -> None:
        self.app, self.metrics, self.skip = app, metrics, skip
        self.log = logging.getLogger(LOGGER_NAME)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started, status = time.perf_counter(), 500

        async def send_with_id(message: dict) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], (b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            seconds = time.perf_counter() - started
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            if scope["path"] not in self.skip:
                if self.metrics is not None:
                    self.metrics.observe_request(scope["method"], route, status, seconds)
                self.log.info("request", extra={
                    "event": "http.request", "request_id": request_id, "method": scope["method"], "route": route,
                    "status": status, "duration_ms": round(seconds * 1000, 1),
                    "user_id": (scope.get("state") or {}).get("user_id")})
            request_id_var.reset(token)
