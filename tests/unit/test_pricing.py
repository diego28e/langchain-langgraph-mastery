"""Unit tests for mastery.pricing (pure arithmetic, offline)."""

from __future__ import annotations

import pytest

from mastery.pricing import PRICES, cost_report, estimate_cost, get_price


def test_every_price_is_dated_and_sourced() -> None:
    for key, price in PRICES.items():
        assert ":" in key, f"{key} must be 'provider:model'"
        assert price.verified and price.source.startswith("https://")
        assert price.input_per_m >= 0 and price.output_per_m >= 0


def test_bare_model_id_matches_when_unique() -> None:
    assert get_price("openai/gpt-oss-20b") is PRICES["groq:openai/gpt-oss-20b"]
    assert get_price("gpt-6-luna") is PRICES["openai:gpt-6-luna"]
    assert get_price("does-not-exist") is None


def test_estimate_cost_uses_input_and_output_prices() -> None:
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000}
    assert estimate_cost(usage, "groq:openai/gpt-oss-20b") == pytest.approx(0.075 + 0.30)


def test_reasoning_tokens_are_not_double_counted() -> None:
    # output_tokens already includes the 900 reasoning tokens.
    usage = {"input_tokens": 0, "output_tokens": 1_000, "output_token_details": {"reasoning": 900}}
    assert estimate_cost(usage, "openai:gpt-6-luna") == pytest.approx(1_000 / 1e6 * 0.50)


@pytest.mark.parametrize(("usage", "model"), [(None, "openai:gpt-6-luna"), ({"input_tokens": 5}, "nope")])
def test_unknown_usage_or_model_returns_none(usage: dict | None, model: str) -> None:
    assert estimate_cost(usage, model) is None


def test_cost_report_builds_sorted_rows() -> None:
    rows = cost_report(
        {
            "openai/gpt-oss-120b": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            "mystery-model": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }
    )
    assert [row["model"] for row in rows] == ["mystery-model", "openai/gpt-oss-120b"]
    assert rows[0]["cost_usd"] is None and rows[0]["price_verified"] is None
    assert rows[1]["cost_usd"] == pytest.approx(100 / 1e6 * 0.15 + 50 / 1e6 * 0.60)
