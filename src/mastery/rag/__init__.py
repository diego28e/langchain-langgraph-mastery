"""Retrieval helpers for Module 06: load → split → embed/index → retrieve → cite → measure.

Every function works offline with :class:`mastery.memory.HashingEmbeddings`; real local embeddings
and re-ranking use ``fastembed`` (the ``[embeddings]`` extra) when installed.
"""
from mastery.rag.citations import (
                                   NOT_FOUND,
                                   Citation,
                                   CitedAnswer,
                                   extractive_agent_reader,
                                   extractive_answer,
                                   extractive_reader,
                                   format_citations,
                                   format_context,
                                   is_dont_know,
                                   normalize_text,
                                   parse_context,
                                   verify_citations,
)
from mastery.rag.eval import evaluate_retrieval, mrr, recall_at_k, score_answers
from mastery.rag.index import (
                                   CachedEmbeddings,
                                   build_index,
                                   default_embeddings,
                                   embedding_label,
                                   folder_size,
                                   open_chroma,
                                   reset_chroma,
                                   vectorstore_dir,
)
from mastery.rag.loaders import load_corpus, load_html, load_markdown, load_pdf
from mastery.rag.retrieve import (
                                   BM25,
                                   OverlapReranker,
                                   cross_encoder_reranker,
                                   hybrid_search,
                                   make_retriever_tool,
                                   retrieve,
                                   rrf,
)
from mastery.rag.splitters import chunk_stats, split_documents

__all__ = [
                                   "BM25",
                                   "NOT_FOUND",
                                   "CachedEmbeddings",
                                   "Citation",
                                   "CitedAnswer",
                                   "OverlapReranker",
                                   "build_index",
                                   "chunk_stats",
                                   "cross_encoder_reranker",
                                   "default_embeddings",
                                   "embedding_label",
                                   "evaluate_retrieval",
                                   "extractive_agent_reader",
                                   "extractive_answer",
                                   "extractive_reader",
                                   "folder_size",
                                   "format_citations",
                                   "format_context",
                                   "hybrid_search",
                                   "is_dont_know",
                                   "load_corpus",
                                   "load_html",
                                   "load_markdown",
                                   "load_pdf",
                                   "make_retriever_tool",
                                   "mrr",
                                   "normalize_text",
                                   "open_chroma",
                                   "parse_context",
                                   "recall_at_k",
                                   "score_answers",
                                   "reset_chroma",
                                   "retrieve",
                                   "rrf",
                                   "split_documents",
                                   "vectorstore_dir",
                                   "verify_citations",
]
