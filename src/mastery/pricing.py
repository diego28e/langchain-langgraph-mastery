"""Turn token usage into an estimated cost, from one dated price table.

Introduced in Module 01, Lesson 01.06 ("Tokens, cost, and rate limits") and
used by Project 01 (Multi-Model Comparison Lab).

Why a table in code:
    Providers report token counts (``AIMessage.usage_metadata``), not money.
    To compare models you need ``tokens x price``. Keeping the prices in one
    dated table makes it obvious when they go stale (Lesson 00.07).

Limits of this estimate (read before trusting it):
    - List prices for the standard tier. Cached-input discounts, batch/flex
      discounts and long-context surcharges are ignored.
    - ``output_tokens`` already INCLUDES reasoning tokens for the providers used
      in the course (they are billed as output), so they are not added twice.
    - Free tiers cost $0; the estimate shows what the same work would cost on
      a paid tier. Real spend lives in the provider's billing dashboard.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = ["PRICES", "ModelPrice", "cost_report", "estimate_cost", "get_price"]


@dataclass(frozen=True)
class ModelPrice:
    """List price in USD per 1M tokens.

    Attributes:
        input_per_m: Price per 1M input (prompt) tokens.
        output_per_m: Price per 1M output tokens (reasoning included).
        status: ``"production"``/``"stable"`` or ``"preview"``.
        source: Where the price was read.
        verified: Date the price was checked (ISO format).
    """

    input_per_m: float
    output_per_m: float
    status: str
    source: str
    verified: str = "2026-10-11"


_GROQ = "https://console.groq.com/docs/models"
_OPENAI = "https://developers.openai.com/api/docs/pricing"
_GEMINI = "https://ai.google.dev/gemini-api/docs/pricing"

# Keys are "provider:model" strings, the same format as get_model(model=...).
# VERIFIED 2026-10-11 on the source pages. Re-check at every research checkpoint.
PRICES: dict[str, ModelPrice] = {
    "groq:openai/gpt-oss-20b": ModelPrice(0.075, 0.30, "production", _GROQ),
    "groq:openai/gpt-oss-120b": ModelPrice(0.15, 0.60, "production", _GROQ),
    "groq:qwen/qwen3.8-27b": ModelPrice(0.80, 4.00, "preview", _GROQ),
    "groq:openai/gpt-oss-safeguard-20b": ModelPrice(0.075, 0.30, "preview", _GROQ),
    "openai:gpt-6-luna": ModelPrice(0.10, 0.50, "stable", _OPENAI),
    "openai:gpt-6.1-sol": ModelPrice(2.00, 10.00, "stable", _OPENAI),
    # Gemini 3.8 Flash and 3.6 Flash list prices double on 2027-01-01 (to $1.50 / $7.50).
    "google_genai:gemini-3.8-flash": ModelPrice(0.75, 3.75, "stable", _GEMINI),
    "google_genai:gemini-3.6-flash": ModelPrice(0.75, 3.75, "stable", _GEMINI),
    "google_genai:gemini-3.5-flash-lite": ModelPrice(0.30, 2.50, "stable", _GEMINI),
}


def get_price(model: str) -> ModelPrice | None:
    """Look up the price for ``"provider:model"`` or a bare model ID.

    A bare ID (what providers report in ``response_metadata["model_name"]``,
    e.g. ``"openai/gpt-oss-20b"``) matches when exactly one table entry ends
    with it, so ambiguous names return ``None`` instead of a wrong price.

    Args:
        model: ``"groq:openai/gpt-oss-20b"`` or ``"openai/gpt-oss-20b"``.

    Returns:
        The :class:`ModelPrice`, or ``None`` if unknown or ambiguous.
    """
    if model in PRICES:
        return PRICES[model]
    matches = [price for key, price in PRICES.items() if key.split(":", 1)[1] == model]
    return matches[0] if len(matches) == 1 else None


def estimate_cost(usage: Mapping[str, Any] | None, model: str) -> float | None:
    """Estimate the paid-tier cost (USD) of one call or a summed usage dict.

    Args:
        usage: A ``usage_metadata`` dict with ``input_tokens`` and ``output_tokens``.
        model: Model key, see :func:`get_price`.

    Returns:
        Cost in USD, or ``None`` if the usage or the price is unknown.
    """
    price = get_price(model)
    if price is None or not usage:
        return None
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    return input_tokens / 1_000_000 * price.input_per_m + output_tokens / 1_000_000 * price.output_per_m


def cost_report(usage_by_model: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build one row per model from ``get_usage_metadata_callback().usage_metadata``.

    Args:
        usage_by_model: ``{model_name: usage_metadata}``, as collected by
            ``langchain_core.callbacks.get_usage_metadata_callback``.

    Returns:
        Rows with ``model``, token counts, ``cost_usd`` (``None`` if unpriced)
        and ``price_verified``.
    """
    rows = []
    for model_name, usage in sorted(usage_by_model.items()):
        price = get_price(model_name)
        rows.append(
            {
                "model": model_name,
                "input_tokens": int(usage.get("input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
                "reasoning_tokens": int((usage.get("output_token_details") or {}).get("reasoning") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
                "cost_usd": estimate_cost(usage, model_name),
                "price_verified": price.verified if price else None,
            }
        )
    return rows
