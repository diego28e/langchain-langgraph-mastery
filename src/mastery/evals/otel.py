"""OpenTelemetry helpers for Lesson 10.02 (needs ``opentelemetry-sdk``; ``pip install "langsmith[otel]"``).

- :func:`in_memory_tracing`: a private ``TracerProvider`` that keeps finished spans in
  memory, so you can see exactly what an exporter would send, offline, with no backend.
- :func:`span_table`: those spans as rows (name, parent, duration, selected attributes).
- :func:`langsmith_otlp_env`: the environment variables that send OTLP spans to
  LangSmith (the API key is never included: you set it yourself).
- :func:`check_otlp_endpoint`: catches the classic 404 (a base endpoint ending in ``/v1/traces``).

GenAI attribute names (``gen_ai.*``) follow the OpenTelemetry GenAI semantic conventions,
which are still evolving: re-check them before you build dashboards on them.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

__all__ = ["GENAI", "check_otlp_endpoint", "in_memory_tracing", "langsmith_otlp_env", "span_table"]

#: A few GenAI semantic-convention attribute names (check the conventions' status before relying on them).
GENAI = {
    "operation": "gen_ai.operation.name",
    "provider": "gen_ai.provider.name",
    "model": "gen_ai.request.model",
    "input_tokens": "gen_ai.usage.input_tokens",
    "output_tokens": "gen_ai.usage.output_tokens",
    "tool": "gen_ai.tool.name",
    "agent": "gen_ai.agent.name",
}

LANGSMITH_OTLP_BASE = "https://api.smith.langchain.com/otel"


def in_memory_tracing(service_name: str = "orbita-support-desk") -> tuple[Any, Any]:
    """Return ``(provider, exporter)``; get a tracer with ``provider.get_tracer(__name__)``.

    The provider is NOT installed globally, so it never interferes with other tracing.
    """
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def span_table(spans: Iterable[Any], attributes: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Finished spans as rows, oldest first: ``name``, ``parent``, ``ms`` and the chosen attributes."""
    spans = sorted(spans, key=lambda s: s.start_time)
    names = {s.context.span_id: s.name for s in spans}
    rows = []
    for span in spans:
        row = {"name": span.name, "parent": names.get(span.parent.span_id, "-") if span.parent else "-",
               "ms": round((span.end_time - span.start_time) / 1e6, 2)}
        for key in attributes:
            row[key] = span.attributes.get(key, "")
        rows.append(row)
    return rows


def langsmith_otlp_env(project: str, *, base: str = LANGSMITH_OTLP_BASE) -> dict[str, str]:
    """Env vars for any OTLP/HTTP exporter -> LangSmith. Replace ``<LANGSMITH_API_KEY>`` yourself."""
    return {
        "OTEL_EXPORTER_OTLP_ENDPOINT": base,
        "OTEL_EXPORTER_OTLP_HEADERS": f"x-api-key=<LANGSMITH_API_KEY>,Langsmith-Project={project}",
    }


def check_otlp_endpoint(value: str) -> str | None:
    """Return a warning if ``OTEL_EXPORTER_OTLP_ENDPOINT`` would 404, else ``None``.

    The variable is a BASE url; OTLP/HTTP exporters append ``/v1/traces`` themselves. A
    per-signal exporter ``endpoint=`` argument (or ``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT``)
    is the full url instead, and does end in ``/v1/traces``.
    """
    if value.rstrip("/").endswith("/v1/traces"):
        return ("OTEL_EXPORTER_OTLP_ENDPOINT is a base url: drop '/v1/traces' (the exporter adds it, "
                "so this would POST to .../v1/traces/v1/traces and get 404)")
    return None
