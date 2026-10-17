"""Ollama server checks and speed measurements (Lesson 14.01). VERIFIED 2026-10-16 against
https://docs.ollama.com/api (``/api/version``, ``/api/tags``, ``/api/show`` with ``capabilities``)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

__all__ = ["LocalModel", "ModelMissing", "OllamaStatus", "OllamaUnavailable", "Speed", "fits_in_memory", "measure",
           "ollama_status", "require_model"]


class OllamaUnavailable(RuntimeError):
    """No Ollama server answered at the configured address."""


class ModelMissing(RuntimeError):
    """The server is up but the model has not been pulled."""

    def __init__(self, name: str, available: list[str]) -> None:
        self.name, self.available = name, available
        have = ", ".join(available) or "none"
        super().__init__(f"{name} is not pulled. In a terminal run:  ollama pull {name}   (pulled now: {have})")


@dataclass(frozen=True)
class LocalModel:
    name: str
    size_gb: float
    family: str = ""
    parameters: str = ""
    quantization: str = ""
    capabilities: tuple[str, ...] = ()
    context_length: int | None = None

    @property
    def tools(self) -> bool:
        return "tools" in self.capabilities


@dataclass
class OllamaStatus:
    base_url: str
    running: bool
    version: str | None = None
    models: list[LocalModel] = field(default_factory=list)
    error: str | None = None

    def names(self) -> list[str]:
        return [m.name for m in self.models]

    def get(self, name: str) -> LocalModel | None:
        wanted = name if ":" in name else f"{name}:latest"
        return next((m for m in self.models if m.name in (name, wanted)), None)


def _base(base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/")
    from mastery.config import load_settings

    return load_settings().ollama_base_url


def ollama_status(base_url: str | None = None, *, timeout: float = 3.0, details: bool = True,
                  client: httpx.Client | None = None) -> OllamaStatus:
    """Is the server up, which version, which models (with capabilities from ``/api/show``)? Never raises."""
    url = _base(base_url)
    http = client or httpx.Client(timeout=timeout)
    try:
        version = http.get(f"{url}/api/version").json().get("version")
        tags = http.get(f"{url}/api/tags").json().get("models", [])
    except (httpx.HTTPError, ValueError) as error:
        return OllamaStatus(url, False, error=f"{type(error).__name__}: {error}"[:200])
    models = []
    for tag in tags:
        info: dict[str, Any] = {}
        if details:
            try:
                info = http.post(f"{url}/api/show", json={"model": tag["name"]}).json()
            except (httpx.HTTPError, ValueError):
                info = {}
        d = info.get("details") or tag.get("details") or {}
        ctx = next((v for k, v in (info.get("model_info") or {}).items() if k.endswith(".context_length")), None)
        models.append(LocalModel(tag["name"], round(tag.get("size", 0) / 1e9, 2), d.get("family", ""),
                                 d.get("parameter_size", ""), d.get("quantization_level", ""),
                                 tuple(info.get("capabilities") or ()), ctx))
    return OllamaStatus(url, True, version, models)


def require_model(name: str, status: OllamaStatus | None = None, *, need: tuple[str, ...] = ()) -> LocalModel:
    """The model, or a clear error: server down, not pulled (with the pull command), or missing a capability."""
    status = status or ollama_status()
    if not status.running:
        raise OllamaUnavailable(f"No Ollama server at {status.base_url}. Start the Ollama app (Windows: Start menu) "
                                f"or run `ollama serve`, then re-run. ({status.error})")
    model = status.get(name)
    if model is None:
        raise ModelMissing(name, status.names())
    missing = [c for c in need if c not in model.capabilities]
    if missing:
        raise ValueError(f"{name} lacks {missing} (it has {list(model.capabilities)}); pick a model tagged "
                         f"{missing} on https://ollama.com/library")
    return model


@dataclass(frozen=True)
class Speed:
    model: str
    seconds: float
    load_s: float
    prompt_tokens: int
    output_tokens: int
    tokens_per_s: float | None
    text: str


def measure(model: Any, prompt: str) -> Speed:
    """One call, timed. Uses Ollama's own counters when present (``eval_count``/``eval_duration``)."""
    start = time.perf_counter()
    reply = model.invoke(prompt)
    seconds = time.perf_counter() - start
    meta = getattr(reply, "response_metadata", {}) or {}
    usage = getattr(reply, "usage_metadata", None) or {}
    out = int(meta.get("eval_count") or usage.get("output_tokens") or 0)
    eval_s = (meta.get("eval_duration") or 0) / 1e9
    tps = out / eval_s if eval_s else (out / seconds if out and seconds else None)
    name = str(meta.get("model_name") or getattr(model, "model", "") or getattr(model, "model_name", ""))
    return Speed(name, round(seconds, 2), round((meta.get("load_duration") or 0) / 1e9, 2),
                 int(meta.get("prompt_eval_count") or usage.get("input_tokens") or 0), out,
                 round(tps, 1) if tps else None, getattr(reply, "text", None) or str(reply.content))


def fits_in_memory(size_gb: float, ram_gb: float, *, vram_gb: float = 0.0, overhead_gb: float = 2.0) -> str:
    """Rough rule: weights + ~20% for context/KV cache + OS headroom. 'gpu', 'cpu' (RAM, slower) or 'no'."""
    need = size_gb * 1.2
    if vram_gb and need <= vram_gb:
        return "gpu"
    if need + overhead_gb <= ram_gb:
        return "cpu"
    return "no"
