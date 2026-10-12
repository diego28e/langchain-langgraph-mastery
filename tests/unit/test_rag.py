"""Offline tests for mastery.rag (Module 06): loaders, splitters, indexes, retrieval, citations, metrics."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from mastery.memory import HashingEmbeddings
from mastery.rag import (
    BM25,
    NOT_FOUND,
    Citation,
    CitedAnswer,
    OverlapReranker,
    build_index,
    chunk_stats,
    evaluate_retrieval,
    extractive_answer,
    format_citations,
    format_context,
    hybrid_search,
    is_dont_know,
    load_corpus,
    load_html,
    load_markdown,
    load_pdf,
    make_retriever_tool,
    mrr,
    parse_context,
    recall_at_k,
    retrieve,
    rrf,
    split_documents,
    verify_citations,
)
from mastery.rag.citations import extractive_reader
from mastery.rag.index import CachedEmbeddings, folder_size, open_chroma, reset_chroma
from mastery.testing import ScriptedChatModel

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "data" / "samples" / "rag"
CORPUS = SAMPLES / "corpus"


@pytest.fixture(scope="module")
def corpus() -> list[Document]:
    return load_corpus(CORPUS)


@pytest.fixture(scope="module")
def chunks(corpus) -> list[Document]:
    return split_documents(corpus, "markdown", 800, 100)


@pytest.fixture(scope="module")
def golden() -> list[dict]:
    return [json.loads(line) for line in (SAMPLES / "golden-set.jsonl").read_text(encoding="utf-8").splitlines()]


def test_corpus_meets_project_size(corpus):
    files = {d.metadata["source"] for d in corpus}
    assert len(files) >= 30
    assert {d.metadata["type"] for d in corpus} == {"markdown", "pdf"}
    assert all("\\" not in s for s in files)          # POSIX paths, also on Windows


def test_pdf_pages_are_one_based(corpus):
    pages = [d for d in corpus if d.metadata["source"] == "manuals/nimbus-pro-manual.pdf"]
    assert [d.metadata["page"] for d in pages] == [1, 2, 3, 4]
    assert any("E12" in d.page_content for d in pages)
    assert load_pdf(CORPUS / "manuals/nimbus-pro-manual.pdf", root=CORPUS)[0].metadata["pages"] == 4


def test_markdown_crlf_and_title(tmp_path):
    f = tmp_path / "x.md"
    f.write_bytes(b"# Hello\r\n\r\nBody line.\r\n")
    doc = load_markdown(f, root=tmp_path)[0]
    assert doc.metadata == {"source": "x.md", "type": "markdown", "title": "Hello"}
    assert "\r" not in doc.page_content


def test_html_drops_noise():
    doc = load_html(SAMPLES / "html" / "status-page.html", root=SAMPLES)[0]
    assert doc.metadata["source"] == "html/status-page.html"
    text = doc.page_content
    assert "Scheduled maintenance" in text and "console.log" not in text
    assert "Cookie" not in text and "Sign in" not in text and "<" not in text


@pytest.mark.parametrize("preset", ["recursive", "markdown", "tokens"])
def test_split_keeps_metadata_and_ids(corpus, preset):
    size = 200 if preset == "tokens" else 600
    out = split_documents(corpus, preset, size, 60)
    assert len(out) >= len(corpus)
    ids = [c.metadata["chunk_id"] for c in out]
    assert len(ids) == len(set(ids))
    assert all("source" in c.metadata and "start_index" in c.metadata for c in out)
    if preset == "markdown":
        assert any(c.metadata.get("section") for c in out)
    assert chunk_stats(out)["chunks"] == len(out)


def test_split_rejects_bad_overlap(corpus):
    with pytest.raises(ValueError):
        split_documents(corpus, chunk_size=100, chunk_overlap=100)


def test_cached_embeddings(tmp_path):
    cached = CachedEmbeddings(HashingEmbeddings(64), cache_dir=tmp_path)
    first = cached.embed_documents(["alpha beta", "gamma"])
    again = cached.embed_documents(["alpha beta", "gamma", "delta"])
    assert cached.misses == 3 and cached.hits == 2
    assert all(a == pytest.approx(b, abs=1e-6) for a, b in zip(again[:2], first))
    cached.close()


def test_memory_index_and_filter(chunks):
    store = build_index(chunks, HashingEmbeddings(1024))
    top = retrieve(store, "What does error E12 mean?", k=3)
    assert top[0].metadata["source"] == "manuals/nimbus-pro-manual.pdf"
    assert top[0].metadata["score"] >= top[-1].metadata["score"]
    only_md = retrieve(store, "error E12", k=3, filter={"type": "markdown"})
    assert all(d.metadata["type"] == "markdown" for d in only_md)


def test_chroma_persists_and_upserts(chunks, tmp_path):
    emb = HashingEmbeddings(256)
    store = build_index(chunks[:20], emb, kind="chroma", collection="test-rag", persist_dir=tmp_path / "vs")
    build_index(chunks[:20], emb, kind="chroma", collection="test-rag", persist_dir=tmp_path / "vs")
    again = open_chroma("test-rag", emb, persist_dir=tmp_path / "vs")
    assert again._collection.count() == 20
    hit = retrieve(again, chunks[0].page_content[:80], k=1)[0]
    assert 0.0 <= hit.metadata["score"] <= 1.0001
    assert retrieve(again, "anything", k=2, filter={"source": chunks[0].metadata["source"]})
    assert folder_size(tmp_path / "vs").endswith(("KB", "MB"))
    reset_chroma(store)


def test_golden_recall_offline(chunks, golden):
    store = build_index(chunks, HashingEmbeddings(1024))
    report = evaluate_retrieval(lambda q: retrieve(store, q, k=5), golden, k=5)
    assert report["questions"] == 16
    assert report["recall"] >= 0.8


def test_bm25_and_rrf(chunks):
    bm = BM25(chunks)
    assert bm.search("E40", k=1)[0].metadata["source"] == "manuals/nimbus-pro-manual.pdf"
    store = build_index(chunks, HashingEmbeddings(1024))
    fused = hybrid_search(store, bm, "restocking fee opened products", k=5)
    assert "policies/returns.md" in [d.metadata["source"] for d in fused[:2]] and len(fused) == 5
    a = [Document("x", metadata={"chunk_id": "a"}), Document("y", metadata={"chunk_id": "b"})]
    b = [Document("y", metadata={"chunk_id": "b"})]
    assert [d.metadata["chunk_id"] for d in rrf(a, b)] == ["b", "a"]


def test_overlap_reranker():
    docs = [Document("weather in general"), Document("battery saver mode extends battery life")]
    assert "battery" in OverlapReranker().rerank("battery saver", docs, top_n=1)[0].page_content


def test_metrics():
    assert recall_at_k(["a", "b", "c"], ["c", "z"], k=3) == 0.5
    assert recall_at_k(["a"], [], k=1) == 1.0
    assert mrr(["x", "a"], ["a"]) == 0.5 and mrr(["x"], ["a"]) == 0.0


def test_context_roundtrip_and_verification():
    docs = [Document("Error E12 means the rain\ngauge is blocked.", metadata={"source": "m.pdf", "page": 3}),
            Document("Returns within 30 days.", metadata={"source": "r.md"})]
    text = format_context(docs)
    assert "[1] source=m.pdf page=3" in text and "[2] source=r.md" in text
    back = parse_context(text)
    assert back[0].metadata == {"source": "m.pdf", "page": 3, "type": "pdf"} and back[1].page_content == "Returns within 30 days."
    good = CitedAnswer(answer="Blocked gauge.", citations=[Citation(source="m.pdf", page=3, quote="the rain gauge is blocked")])
    assert verify_citations(good, docs)["ok"]                          # PDF line break tolerated
    wrong_page = CitedAnswer(answer="x", citations=[Citation(source="m.pdf", page=2, quote="rain gauge")])
    invented = CitedAnswer(answer="x", citations=[Citation(source="r.md", quote="Returns within 60 days")])
    assert not verify_citations(wrong_page, docs)["ok"]
    assert verify_citations(invented, docs)["fabricated"][0].quote == "Returns within 60 days"
    assert "[1] m.pdf, p. 3" in format_citations(good)


def test_extractive_reader_answers_and_abstains(chunks, golden):
    store = build_index(chunks, HashingEmbeddings(1024))
    correct = fabricated = 0
    for g in golden:
        docs = retrieve(store, g["question"], k=5)
        ans = extractive_answer(g["question"], docs)
        fabricated += len(verify_citations(ans, docs)["fabricated"])
        if not g["in_corpus"]:
            assert is_dont_know(ans), g["id"]
        elif g["answer_contains"].lower() in ans.answer.lower():
            correct += 1
    assert fabricated == 0
    assert correct >= 12                        # a dull baseline: 12/16 on our run (+4/4 abstentions); LLMs write better
    assert is_dont_know(NOT_FOUND)


def test_scripted_chain_with_reader():
    from langchain_core.prompts import ChatPromptTemplate

    docs = [Document("The restocking fee is 10% for opened products.", metadata={"source": "policies/returns.md"})]
    prompt = ChatPromptTemplate.from_messages([("system", "Use only the sources."),
                                               ("human", "Sources:\n{context}\n\nQuestion: {question}")])
    model = ScriptedChatModel(responses=[extractive_reader()], repeat_last=True)
    chain = prompt | model.with_structured_output(CitedAnswer)
    out = chain.invoke({"context": format_context(docs), "question": "What is the restocking fee for opened products?"})
    assert "10%" in out.answer and verify_citations(out, docs)["ok"]
    assert isinstance(model.calls[0][-1], HumanMessage)


def test_retriever_tool_artifact(chunks):
    store = build_index(chunks, HashingEmbeddings(1024))
    tool = make_retriever_tool(store, k=2)
    msg = tool.invoke({"type": "tool_call", "id": "t1", "name": tool.name, "args": {"query": "error E12"}})
    assert "[1] source=" in msg.content and len(msg.artifact) == 2


def test_extractive_agent_reader_with_create_agent(chunks):
    from langchain.agents import create_agent
    from langchain.agents.structured_output import ToolStrategy
    from langchain_core.messages import ToolMessage
    from mastery.rag import extractive_agent_reader

    store = build_index(chunks, HashingEmbeddings(1024))
    tool = make_retriever_tool(store, name="search_docs", k=4)
    model = ScriptedChatModel(responses=[extractive_agent_reader("search_docs")], repeat_last=True)
    agent = create_agent(model, tools=[tool], response_format=ToolStrategy(CitedAnswer))
    out = agent.invoke({"messages": [HumanMessage("What does error E12 mean on the Nimbus Pro?")]})
    answer = out["structured_response"]
    docs = [d for m in out["messages"] if isinstance(m, ToolMessage) and isinstance(m.artifact, list) for d in m.artifact]
    assert "blocked" in answer.answer and verify_citations(answer, docs)["ok"]
    out = agent.invoke({"messages": [HumanMessage("Who founded Orbita Labs?")]})
    assert is_dont_know(out["structured_response"])
