from __future__ import annotations

import pytest

pytest.importorskip("deepagents")

from mastery.deep.research import (  # noqa: E402
    BRIEF_SECTIONS,
    SourceLedger,
    brief_markdown,
    cited_docs,
    load_questions,
    offline_models,
    research_tools,
    section,
)


def test_questions_and_smoke_set():
    rows = load_questions()
    assert len(rows) == 20 and sum(r["in_corpus"] for r in rows) == 16
    assert [r["id"] for r in load_questions(smoke=True)] == ["g01", "g06", "g17"]


def test_tools_record_sources():
    ledger = SourceLedger()
    docs, web = research_tools(ledger)
    out = docs.invoke({"name": "search_docs", "args": {"query": "Nimbus Pro price"}, "id": "1", "type": "tool_call"})
    assert "products/nimbus-pro.md" in ledger.docs and "source=products/nimbus-pro.md" in out.content
    assert "No results" in web.invoke({"query": "anything"})
    ledger.clear()
    assert ledger.docs == []


def test_brief_helpers():
    text = brief_markdown("Q?", "A.", [{"source": "a/b.md", "quote": "the quote"}], confidence="high")
    assert [s for s in BRIEF_SECTIONS if section(text, s)] == list(BRIEF_SECTIONS)
    assert cited_docs(text) == ["a/b.md"] and section(text, "Answer") == "A."
    assert set(offline_models()) == {"coordinator", "researcher", "critic"}
