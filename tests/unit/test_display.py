"""Unit tests for mastery.display: the HTML is correct and always escaped."""

from __future__ import annotations

import pytest

pytest.importorskip("langchain_core")

from langchain_core.messages import AIMessage, HumanMessage

from mastery.display import message_summary, render_message_html


def _ai_message() -> AIMessage:
    return AIMessage(
        content="Paris.",
        additional_kwargs={"reasoning_content": "The user asks for a capital."},
        response_metadata={"model_provider": "groq", "model_name": "openai/gpt-oss-20b", "finish_reason": "stop"},
        tool_calls=[{"name": "lookup", "args": {"city": "Paris"}, "id": "call_1"}],
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 8,
            "total_tokens": 18,
            "output_token_details": {"reasoning": 6},
        },
    )


def test_summary_reads_content_blocks_and_metadata() -> None:
    info = message_summary(_ai_message())
    assert info["type"] == "ai"
    assert info["text"] == "Paris."
    assert info["reasoning"] == "The user asks for a capital."
    assert info["tool_calls"][0]["name"] == "lookup"
    assert info["model_name"] == "openai/gpt-oss-20b"
    assert info["usage"]["total_tokens"] == 18


def test_html_contains_the_important_parts() -> None:
    html = render_message_html(_ai_message())
    for expected in ("Paris.", "<details>", "lookup", "6 reasoning", "openai/gpt-oss-20b"):
        assert expected in html


def test_model_output_is_escaped() -> None:
    html = render_message_html(HumanMessage("<script>alert('x')</script>"))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_long_text_is_shortened() -> None:
    html = render_message_html(HumanMessage("a" * 50), max_chars=10)
    assert "40 more characters" in html
