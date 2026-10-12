"""Citation schema, context formatting and quote verification ("every quote is in a retrieved chunk")."""
from __future__ import annotations

import math
import re
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from mastery.rag.retrieve import terms

NOT_FOUND = "I don't know: the answer is not in the provided sources."


class Citation(BaseModel):
    """One piece of evidence: where it comes from and the exact words used."""

    source: str = Field(description="The source path exactly as shown in the context header, e.g. data/samples/rag/policies/returns.md")
    page: int | None = Field(default=None, description="PDF page number from the context header; null for Markdown/HTML")
    quote: str = Field(description="A short passage copied word for word from that source's text (no paraphrase)")


class CitedAnswer(BaseModel):
    """An answer grounded in the retrieved sources."""

    answer: str = Field(description=f"The answer, using only the sources. If they don't contain it, reply exactly: {NOT_FOUND}")
    citations: list[Citation] = Field(default_factory=list, description="Evidence for the answer; empty when you don't know")


def format_context(docs: list[Document]) -> str:
    """Number and label chunks: ``[1] source=… page=…`` + text. The model cites what it can see."""
    blocks = []
    for n, doc in enumerate(docs, start=1):
        page = doc.metadata.get("page")
        header = f"[{n}] source={doc.metadata.get('source', '?')}" + (f" page={page}" if page else "")
        blocks.append(f"{header}\n{doc.page_content.strip()}")
    return "\n\n".join(blocks)


_HEADER = re.compile(r"^\[(\d+)\] source=(\S+)(?: page=(\d+))?$", re.MULTILINE)


def parse_context(text: str) -> list[Document]:
    """Inverse of :func:`format_context` (used by offline scripted models that read their prompt)."""
    matches = list(_HEADER.finditer(text))
    docs = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        meta = {"source": m.group(2)} | ({"page": int(m.group(3)), "type": "pdf"} if m.group(3) else {})
        docs.append(Document(page_content=text[m.end():end].strip(), metadata=meta))
    return docs


def normalize_text(text: str) -> str:
    """Collapse whitespace and unify quotes/dashes, so PDF line breaks don't fail an honest quote."""
    table = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"})
    return re.sub(r"\s+", " ", text.translate(table)).strip().lower()


def verify_citations(answer: CitedAnswer, docs: list[Document]) -> dict[str, Any]:
    """Check every citation against the *retrieved* chunks.

    A citation is valid only if its quote (normalised) is a substring of a retrieved chunk with the
    same ``source`` (and ``page``, when given). Returns ``{"valid": [...], "fabricated": [...], "ok": bool}``.
    """
    valid, fabricated = [], []
    for cite in answer.citations:
        quote = normalize_text(cite.quote)
        hit = bool(quote) and any(
            doc.metadata.get("source") == cite.source
            and (cite.page is None or doc.metadata.get("page") in (None, cite.page))
            and quote in normalize_text(doc.page_content)
            for doc in docs)
        (valid if hit else fabricated).append(cite)
    return {"valid": valid, "fabricated": fabricated, "ok": not fabricated}


def is_dont_know(answer: CitedAnswer | str) -> bool:
    """True when the answer is the "not in the sources" reply (tolerant of small wording changes)."""
    text = normalize_text(answer.answer if isinstance(answer, CitedAnswer) else answer)
    return text.startswith("i don't know") or "not in the provided sources" in text


def format_citations(answer: CitedAnswer) -> str:
    """Markdown: the answer, then numbered sources with quotes."""
    lines = [answer.answer]
    for n, c in enumerate(answer.citations, start=1):
        where = c.source.rsplit("/", 1)[-1] + (f", p. {c.page}" if c.page else "")
        lines.append(f'  [{n}] {where}: "{c.quote}"')
    return "\n".join(lines)


# Words that shape a question but rarely appear in the answer text.
_QUESTION_WORDS = frozenset(["how", "much", "many", "long", "often", "shou", "will", "woul", "can", "coul", "need", "doe", "does"])


def _keys(text: str) -> set[str]:
    """Content words cut to 4 letters, so "stored"/"store" and "added"/"adds" match (crude but robust)."""
    return {w[:4] for w in terms(text)}
_SENTENCE = re.compile(r"[^.\n!?]+(?:\.\d[^.\n!?]*)*[.!?]?")


def extractive_answer(question: str, docs: list[Document], min_coverage: float = 0.5,
                      max_unseen: float = 0.25) -> CitedAnswer:
    """Offline, model-free baseline reader: return the retrieved sentence that best covers the question.

    It never invents text (the quote *is* the answer). It says "don't know" when more than
    ``max_unseen`` of the question's content words appear in no retrieved chunk ("Nimbus *Ultra*"),
    or the best sentence covers less than ``min_coverage`` of them. Used to run the RAG pipelines
    without a key; a real LLM writes much better answers.
    """
    q = _keys(question) - _QUESTION_WORDS
    seen = set().union(*(_keys(d.page_content) for d in docs)) if docs else set()
    if not q or not docs or len(q - seen) / len(q) > max_unseen:
        return CitedAnswer(answer=NOT_FOUND, citations=[])
    candidates: list[tuple[str, Document, set[str]]] = []
    for doc in docs:
        text = doc.page_content
        if doc.metadata.get("type") == "pdf":       # PDF line breaks are layout, not sentence ends
            text = re.sub(r"\s+", " ", text)
        for m in _SENTENCE.finditer(text):
            sentence = m.group(0).strip(" -*#\t")
            if len(sentence) >= 12:
                candidates.append((sentence, doc, _keys(sentence)))
    # Rare words ("E12") say more than common ones ("Nimbus"): weight question words by inverse frequency.
    weight = {w: math.log(1 + len(candidates) / (1 + sum(w in c[2] for c in candidates))) for w in q}
    total = sum(weight.values()) or 1.0
    best: tuple[float, str | None, Document | None] = (0.0, None, None)
    for sentence, doc, words in candidates:
        cover = sum(weight[w] for w in q & words) / total
        if cover > best[0]:
            best = (cover, sentence, doc)
    cover, sentence, doc = best
    if doc is None or sentence is None or cover < min_coverage:
        return CitedAnswer(answer=NOT_FOUND, citations=[])
    return CitedAnswer(answer=sentence, citations=[Citation(source=doc.metadata.get("source", "?"),
                                                            page=doc.metadata.get("page"), quote=sentence)])


def extractive_reader(schema_name: str = "CitedAnswer"):
    """A ``ScriptedChatModel`` response function: read the context from the prompt, answer extractively.

    ``ScriptedChatModel(responses=[extractive_reader()], repeat_last=True).with_structured_output(CitedAnswer)``
    behaves like a (dull, honest) model in a RAG chain, offline.
    """
    def respond(messages: list) -> AIMessage:
        text = "\n\n".join(m.text for m in messages if isinstance(getattr(m, "text", None), str))
        cut = text.rfind("Question:")
        question = text[cut + len("Question:"):].strip().splitlines()[0] if cut >= 0 else messages[-1].text
        result = extractive_answer(question, parse_context(text[:cut] if cut >= 0 else text))
        return AIMessage("", tool_calls=[{"name": schema_name, "id": "x1", "args": result.model_dump()}])

    return respond


def extractive_agent_reader(search_tool: str | Any = "search_docs", schema_name: str = "CitedAnswer"):
    """A ``ScriptedChatModel`` response function that behaves like a careful RAG **agent**, offline.

    First turn: call ``search_tool`` with the user's question (or, if ``search_tool`` is a callable
    ``question -> tool name``, the tool it picks). After tool results: answer with ``schema_name``
    (a ``ToolStrategy`` tool call) using :func:`extractive_answer` over everything retrieved.
    """
    from langchain_core.messages import HumanMessage, ToolMessage

    def respond(messages: list) -> AIMessage:
        last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        question = messages[last_human].text
        results = [m for m in messages[last_human + 1:] if isinstance(m, ToolMessage)]
        if not results:
            name = search_tool(question) if callable(search_tool) else search_tool
            return AIMessage("", tool_calls=[{"name": name, "args": {"query": question}, "id": "search-1"}])
        docs = [d for m in results for d in parse_context(m.text)]
        result = extractive_answer(question, docs)
        return AIMessage("", tool_calls=[{"name": schema_name, "args": result.model_dump(), "id": "answer-1"}])

    return respond
