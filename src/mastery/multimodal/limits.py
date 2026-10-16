"""Provider limits for multimodal requests, checked *before* you pay for a 400 (Lesson 13.01).

Numbers VERIFIED 2026-10-16 (re-check before relying on them; previews change without notice):
- Groq vision https://console.groq.com/docs/vision : qwen/qwen3.8-27b (preview) only, up to 3 images per
  request, 2,048 tokens per image, 20 MB per request with an image URL (no separate base64 limit is
  documented, so the course applies the same 20 MB and keeps images small).
- Gemini https://ai.google.dev/gemini-api/docs/document-processing : PDF up to 50 MB or 1,000 pages,
  258 tokens per page; inline request data up to 20 MB (bigger goes through the Files API, kept 48 h);
  audio 32 tokens per second https://ai.google.dev/gemini-api/docs/audio
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from typing import Any

from mastery.multimodal.blocks import block_bytes

__all__ = ["LIMITS", "LimitError", "ProviderLimits", "RequestEstimate", "check_request", "limits_for", "pdf_pages"]

MB = 1024 * 1024


@dataclass(frozen=True)
class ProviderLimits:
    """What one provider's multimodal model accepts."""

    provider: str
    model: str
    accepts: frozenset[str]
    max_images: int | None
    image_tokens: int | None
    max_inline_mb: float
    pdf_max_pages: int | None = None
    pdf_max_mb: float | None = None
    pdf_tokens_per_page: int | None = None
    audio_tokens_per_second: int | None = None
    preview: bool = False
    source: str = ""


LIMITS: dict[str, ProviderLimits] = {
    "groq": ProviderLimits(
        provider="groq", model="qwen/qwen3.8-27b", accepts=frozenset({"image"}),
        max_images=3, image_tokens=2048, max_inline_mb=20.0, preview=True,
        source="https://console.groq.com/docs/vision",
    ),
    "google_genai": ProviderLimits(
        provider="google_genai", model="gemini-3.6-flash",
        accepts=frozenset({"image", "file", "audio", "video"}),
        max_images=None, image_tokens=None, max_inline_mb=20.0,
        pdf_max_pages=1000, pdf_max_mb=50.0, pdf_tokens_per_page=258, audio_tokens_per_second=32,
        source="https://ai.google.dev/gemini-api/docs/document-processing",
    ),
}


class LimitError(ValueError):
    """The request would be rejected by the provider; ``problems`` lists why."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class RequestEstimate:
    """What a request contains and roughly what its media costs in input tokens."""

    provider: str
    images: int = 0
    pdf_pages: int = 0
    audio_seconds: float = 0.0
    inline_mb: float = 0.0
    media_tokens: int | None = 0
    notes: list[str] = field(default_factory=list)


def limits_for(spec: str) -> ProviderLimits:
    """Limits for ``"groq"``, ``"google_genai"``, a ``"provider:model"`` string or a bare Groq model ID.

    Bare IDs (``settings.model_vision`` is ``"qwen/qwen3.8-27b"``) are Groq models, as everywhere in the course.
    """
    if ":" not in spec and spec not in LIMITS:
        spec = "groq"
    provider = spec.split(":", 1)[0]
    if provider not in LIMITS:
        raise KeyError(f"No multimodal limits recorded for {provider!r}; known: {sorted(LIMITS)}")
    return LIMITS[provider]


def pdf_pages(block: dict[str, Any]) -> int:
    """Page count of a base64 PDF block (needs pypdf)."""
    from pypdf import PdfReader

    return len(PdfReader(io.BytesIO(base64.b64decode(block["base64"]))).pages)


def _blocks(messages_or_blocks: Any) -> list[dict[str, Any]]:
    items = messages_or_blocks if isinstance(messages_or_blocks, list) else [messages_or_blocks]
    out: list[dict[str, Any]] = []
    for item in items:
        content = getattr(item, "content", item)
        if isinstance(content, dict) and "role" in content:
            content = content.get("content")
        if isinstance(content, dict):
            out.append(content)
        elif isinstance(content, list):
            out.extend(b for b in content if isinstance(b, dict))
    return out


def check_request(
    messages_or_blocks: Any, spec: str, *, audio_seconds: float | None = None, raise_on_error: bool = True
) -> RequestEstimate:
    """Estimate a multimodal request and raise :class:`LimitError` if ``spec`` would reject it.

    ``audio_seconds`` is the total audio duration when you send audio (the block does not say).
    """
    lim = limits_for(spec)
    est = RequestEstimate(provider=lim.provider)
    problems: list[str] = []
    tokens = 0
    for block in _blocks(messages_or_blocks):
        kind = block.get("type")
        if kind not in ("image", "file", "audio", "video"):
            continue
        if kind not in lim.accepts:
            problems.append(f"{lim.provider} ({lim.model}) does not accept {kind} blocks")
            continue
        est.inline_mb += block_bytes(block) / MB
        if kind == "image":
            est.images += 1
            if lim.image_tokens:
                tokens += lim.image_tokens
            else:
                est.notes.append("image tokens depend on resolution: read usage_metadata")
        elif kind == "file" and block.get("mime_type") == "application/pdf" and "base64" in block:
            pages = pdf_pages(block)
            est.pdf_pages += pages
            if lim.pdf_max_pages and pages > lim.pdf_max_pages:
                problems.append(f"PDF has {pages} pages; limit is {lim.pdf_max_pages}")
            if lim.pdf_max_mb and block_bytes(block) / MB > lim.pdf_max_mb:
                problems.append(f"PDF is over {lim.pdf_max_mb:g} MB")
            tokens += pages * (lim.pdf_tokens_per_page or 0)
        elif kind == "audio":
            if audio_seconds is None:
                est.notes.append("pass audio_seconds to estimate audio tokens")
            else:
                est.audio_seconds += audio_seconds
                tokens += int(audio_seconds * (lim.audio_tokens_per_second or 0))
        elif kind == "video":
            est.notes.append("video tokens depend on length and media resolution: read usage_metadata")
    if lim.max_images is not None and est.images > lim.max_images:
        problems.append(f"{est.images} images; {lim.model} accepts at most {lim.max_images} per request")
    if est.inline_mb > lim.max_inline_mb:
        problems.append(
            f"{est.inline_mb:.1f} MB inline; limit is {lim.max_inline_mb:g} MB (use a URL or the Files API)"
        )
    est.media_tokens = tokens
    est.inline_mb = round(est.inline_mb, 3)
    if problems and raise_on_error:
        raise LimitError(problems)
    est.notes.extend(problems)
    return est
