"""Project 11 building blocks: the Deep Research Analyst's tools, questions and offline models.

The analyst researches the Orbita Labs document set (``data/samples/rag/corpus``, Module 06) and
the web, and delivers a cited brief. Everything here is infrastructure; the project notebook wires
the agent, the review policy and the evaluation.

* :func:`research_tools` -> ``search_docs`` (BM25 over the corpus) and ``web_search`` (live:
  :func:`mastery.web_search.make_web_search_tool`; offline: a fixture that finds nothing), both
  recording every source they return in a :class:`SourceLedger`, so citations can be checked
  against what the tools really returned, even when a subagent made the call.
* :func:`load_questions` -> the 20 golden questions (16 answerable, 4 that must be declined) and
  the 3-question smoke set.
* :func:`offline_models` -> scripted coordinator, researcher and critic that follow the brief
  workflow without a key (deterministic; a real LLM writes better briefs).
"""
from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool

from mastery.config import find_repo_root

__all__ = ["BRIEF_SECTIONS", "SMOKE_IDS", "SourceLedger", "brief_markdown", "cited_docs", "load_questions",
           "offline_models", "research_tools", "section"]

BRIEF_SECTIONS: tuple[str, ...] = ("Answer", "Evidence", "Sources", "Confidence")
SMOKE_IDS: tuple[str, ...] = ("g01", "g06", "g17")       # a Markdown fact, a PDF fact, a question to decline
DOC_REF = re.compile(r"\[doc:\s*([^\]\s]+)\]")
NOT_FOUND_TEXT = "Not found in the documents or on the web."


@dataclass
class SourceLedger:
    """Every source the research tools returned during a run (doc paths and URLs)."""
    docs: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)

    def clear(self) -> None:
        self.docs.clear()
        self.urls.clear()


def corpus_dir():
    return find_repo_root() / "data" / "samples" / "rag" / "corpus"


def load_questions(*, smoke: bool = False) -> list[dict[str, Any]]:
    """The golden questions (``data/samples/rag/golden-set.jsonl``); ``smoke=True`` -> 3 of them."""
    path = find_repo_root() / "data" / "samples" / "rag" / "golden-set.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if r["id"] in SMOKE_IDS] if smoke else rows


def research_tools(ledger: SourceLedger, *, live_web: bool = False, k: int = 4) -> list[BaseTool]:
    """``search_docs`` and ``web_search``; both append what they return to ``ledger``."""
    from mastery.rag.citations import format_context
    from mastery.rag.loaders import load_corpus
    from mastery.rag.retrieve import BM25

    index = BM25(load_corpus(corpus_dir()))

    def search_docs(query: str) -> tuple[str, list[Any]]:
        docs = index.search(query, k=k)
        ledger.docs.extend(d.metadata.get("source", "?") for d in docs)
        return (format_context(docs) if docs else "No matching passages."), docs

    docs_tool = StructuredTool.from_function(
        func=search_docs, name="search_docs", response_format="content_and_artifact",
        description="Search the Orbita Labs documents (products, manuals, policies). Input: a short query.")

    if live_web:
        from mastery.mcp import extract_urls
        from mastery.web_search import make_web_search_tool

        inner = make_web_search_tool()

        def web_search(query: str) -> tuple[str, dict[str, Any]]:
            message = inner.invoke({"name": "web_search", "args": {"query": query}, "id": "w", "type": "tool_call"})
            ledger.urls.extend(extract_urls(message.content))
            return message.content, (message.artifact or {})
    else:
        def web_search(query: str) -> tuple[str, dict[str, Any]]:
            return "No results (offline fixture: set LIVE_WEB = True for real search).\nSources:\n- (none)", {"sources": []}

    web_tool = StructuredTool.from_function(
        func=web_search, name="web_search", response_format="content_and_artifact",
        description="Search the public web for information that is not in the Orbita documents. One focused query.")
    return [docs_tool, web_tool]


def section(markdown: str, name: str) -> str:
    """Text of ``## name`` up to the next ``## `` heading ('' if missing)."""
    found = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", markdown, flags=re.M | re.S)
    return found.group(1).strip() if found else ""


def cited_docs(markdown: str) -> list[str]:
    """Doc paths cited as ``[doc: path]``."""
    return list(dict.fromkeys(DOC_REF.findall(markdown)))


def brief_markdown(question: str, answer: str, citations: Sequence[dict[str, Any]], *, confidence: str) -> str:
    """The brief format: ``# Brief`` + Answer, Evidence, Sources, Confidence."""
    evidence = "\n".join(f'- "{c["quote"]}" [doc: {c["source"]}]' for c in citations) or "- (none)"
    sources = "\n".join(f"- [doc: {s}]" for s in dict.fromkeys(c["source"] for c in citations)) or "- (none)"
    return (f"# Brief: {question}\n\n## Answer\n{answer}\n\n## Evidence\n{evidence}\n\n"
            f"## Sources\n{sources}\n\n## Confidence\n{confidence}\n")


# --------------------------------------------------------------------------------------------- offline models
def _question(messages: list[Any]) -> tuple[int, str]:
    last = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    return last, messages[last].text


def _researcher(messages: list[Any]) -> AIMessage:
    from mastery.rag.citations import extractive_answer, is_dont_know, parse_context

    last, question = _question(messages)
    results = [m for m in messages[last + 1:] if isinstance(m, ToolMessage)]
    if not results:
        return AIMessage("", tool_calls=[{"name": "search_docs", "args": {"query": question}, "id": "docs-1"}])
    docs = [d for m in results if m.name == "search_docs" for d in parse_context(m.text)]
    found = extractive_answer(question, docs)
    if is_dont_know(found) and not any(m.name == "web_search" for m in results):
        return AIMessage("", tool_calls=[{"name": "web_search", "args": {"query": question}, "id": "web-1"}])
    payload = {"answer": NOT_FOUND_TEXT if is_dont_know(found) else found.answer,
               "citations": [c.model_dump() for c in found.citations]}
    return AIMessage(json.dumps(payload))


def _critic(messages: list[Any]) -> AIMessage:
    _, draft = _question(messages)
    try:
        data = json.loads(draft[draft.index("{"):])
    except ValueError:
        return AIMessage("REJECT: the findings are not readable.")
    if data.get("answer") == NOT_FOUND_TEXT:
        return AIMessage("OK: nothing found; say so and set confidence to low.")
    cited = data.get("citations", [])
    return AIMessage("OK: every claim has a quoted source." if cited and all(c.get("quote") for c in cited)
                     else "REJECT: a claim has no quoted source.")


def _coordinator(messages: list[Any]) -> AIMessage:
    _, question = _question(messages)
    tools = [m for m in messages if isinstance(m, ToolMessage)]
    by_id = {m.tool_call_id: m for m in tools}
    if "research" not in by_id:
        return AIMessage("", tool_calls=[{"name": "task", "id": "research",
                                          "args": {"subagent_type": "researcher", "description": question}}])
    findings = by_id["research"].text
    if "critic" not in by_id:
        return AIMessage("", tool_calls=[{"name": "task", "id": "critic", "args": {
            "subagent_type": "critic", "description": f"Check these findings for: {question}\n{findings}"}}])
    if "write" not in by_id:
        data = json.loads(findings[findings.index("{"):])
        ok = by_id["critic"].text.startswith("OK") and data["answer"] != NOT_FOUND_TEXT
        content = brief_markdown(question, data["answer"], data["citations"] if ok else [],
                                 confidence="high: quoted from the documents" if ok else "low: no reliable source found")
        slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:40]
        return AIMessage("", tool_calls=[{"name": "write_file", "id": "write",
                                          "args": {"file_path": f"/reports/{slug}.md", "content": content}}])
    return AIMessage("The brief is saved in /reports/.")


def offline_models() -> dict[str, Any]:
    """Scripted ``coordinator``, ``researcher`` and ``critic`` (no key, deterministic, reusable)."""
    from mastery.testing import ScriptedChatModel

    return {name: ScriptedChatModel(responses=[fn], repeat_last=True)
            for name, fn in (("coordinator", _coordinator), ("researcher", _researcher), ("critic", _critic))}
