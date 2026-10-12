"""Retrieval: vector search with comparable scores, BM25, reciprocal-rank fusion, re-ranking, retriever tools."""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from langchain_core.documents import Document

from mastery.memory import _STOP, _WORD, _stem


def terms(text: str) -> list[str]:
    """Lower-case, stop words removed, crudely stemmed words (shared by BM25 and the offline reranker)."""
    return [_stem(w) for w in _WORD.findall(text.lower()) if w not in _STOP]


def _key(doc: Document) -> str:
    return doc.metadata.get("chunk_id") or doc.id or doc.page_content[:80]


def retrieve(store: Any, query: str, k: int = 5, filter: dict | None = None) -> list[Document]:
    """Top-``k`` chunks with ``metadata["score"]`` = cosine similarity (higher is better) for both stores.

    ``filter`` is a Chroma-style dict, e.g. ``{"type": "pdf"}`` or ``{"source": "data/.../returns.md"}``;
    for the in-memory store it is applied as exact matches on metadata.
    """
    if hasattr(store, "_collection"):          # Chroma returns cosine *distance*
        pairs = store.similarity_search_with_score(query, k=k, filter=filter)
        pairs = [(d, 1.0 - s) for d, s in pairs]
    else:                                       # InMemoryVectorStore returns cosine *similarity*
        fn = None
        if filter:
            def fn(doc: Document) -> bool:
                return all(doc.metadata.get(key) == value for key, value in filter.items())
        pairs = store.similarity_search_with_score(query, k=k, filter=fn)
    out = []
    for doc, score in pairs:
        doc.metadata["score"] = round(float(score), 4)
        out.append(doc)
    return out


class BM25:
    """Okapi BM25 over chunks, in pure Python (no ``rank_bm25`` dependency). Good at exact terms: codes, names."""

    def __init__(self, docs: list[Document], k1: float = 1.5, b: float = 0.75) -> None:
        self.docs = docs
        self.k1, self.b = k1, b
        self._tf = [Counter(terms(d.page_content)) for d in docs]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = (sum(self._len) / len(self._len)) if docs else 0.0
        df = Counter(t for tf in self._tf for t in tf)
        n = len(docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 5) -> list[Document]:
        q = terms(query)
        scored = []
        for i, tf in enumerate(self._tf):
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self._idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self._len[i] / self._avg))
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda x: -x[0])
        out = []
        for s, i in scored[:k]:
            doc = Document(page_content=self.docs[i].page_content, metadata={**self.docs[i].metadata, "score": round(s, 4)},
                           id=self.docs[i].id)
            out.append(doc)
        return out


def rrf(*rankings: list[Document], k: int = 60, top_n: int | None = None) -> list[Document]:
    """Reciprocal-rank fusion: ``score = Σ 1 / (k + rank)``. Merges rankings whose raw scores aren't comparable."""
    scores: dict[str, float] = {}
    first: dict[str, Document] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            key = _key(doc)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            first.setdefault(key, doc)
    ordered = sorted(scores, key=lambda key: -scores[key])[:top_n]
    out = []
    for key in ordered:
        doc = first[key]
        out.append(Document(page_content=doc.page_content, metadata={**doc.metadata, "score": round(scores[key], 5)},
                            id=doc.id))
    return out


def hybrid_search(store: Any, bm25: BM25, query: str, k: int = 5, fetch_k: int = 20) -> list[Document]:
    """Vector top-``fetch_k`` + BM25 top-``fetch_k``, fused with RRF, cut to ``k``."""
    return rrf(retrieve(store, query, k=fetch_k), bm25.search(query, k=fetch_k), top_n=k)


class OverlapReranker:
    """Offline stand-in for a cross-encoder: scores query-term coverage of each chunk (no download)."""

    name = "overlap (offline stand-in)"

    def rerank(self, query: str, docs: list[Document], top_n: int = 5) -> list[Document]:
        q = set(terms(query))
        scored = []
        for doc in docs:
            words = set(terms(doc.page_content))
            scored.append((len(q & words) / (len(q) or 1), doc))
        scored.sort(key=lambda x: -x[0])
        return [Document(page_content=d.page_content, metadata={**d.metadata, "rerank": round(s, 4)}, id=d.id)
                for s, d in scored[:top_n]]


class _FastEmbedReranker:
    def __init__(self, model_name: str, cache_dir: str | None) -> None:
        import os
        from pathlib import Path

        from fastembed.rerank.cross_encoder import TextCrossEncoder

        cache = Path(cache_dir or os.environ.get("FASTEMBED_CACHE_PATH") or Path.home() / ".cache" / "fastembed")
        cache.mkdir(parents=True, exist_ok=True)
        self.name = model_name
        self._model = TextCrossEncoder(model_name=model_name, cache_dir=str(cache))

    def rerank(self, query: str, docs: list[Document], top_n: int = 5) -> list[Document]:
        scores = list(self._model.rerank(query, [d.page_content for d in docs]))
        ranked = sorted(zip(scores, docs), key=lambda x: -x[0])[:top_n]
        return [Document(page_content=d.page_content, metadata={**d.metadata, "rerank": round(float(s), 4)}, id=d.id)
                for s, d in ranked]


def cross_encoder_reranker(model_name: str = "Xenova/ms-marco-MiniLM-L-6-v2", cache_dir: str | None = None) -> Any:
    """A local cross-encoder re-ranker (fastembed, ONNX, CPU; first use downloads ~80 MB)."""
    return _FastEmbedReranker(model_name, cache_dir)


def make_retriever_tool(search: Any, name: str = "search_docs", description: str | None = None, k: int = 4) -> Any:
    """Wrap a store (or any ``query -> list[Document]`` callable) as an agent tool.

    The model sees numbered, labelled chunks; the raw ``Document`` list rides along as the
    ``ToolMessage.artifact`` so code can verify citations against exactly what was retrieved.
    """
    from langchain_core.tools import StructuredTool

    from mastery.rag.citations import format_context

    def run(query: str) -> tuple[str, list[Document]]:
        docs = search(query) if callable(search) else retrieve(search, query, k=k)
        return (format_context(docs) if docs else "No matching passages."), docs

    return StructuredTool.from_function(
        func=run, name=name, response_format="content_and_artifact",
        description=description or "Search the product documentation. Input: a short search query.")

