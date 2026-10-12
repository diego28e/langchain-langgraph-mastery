# Module 06 — Documents, Embeddings & RAG

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 06](../../COURSE_OUTLINE.md#module-06--documents-embeddings--rag)

**Goals:** Build retrieval systems that are grounded, cited, and measurable: loading and parsing documents, chunking, embeddings, vector stores, 2-step RAG vs agentic RAG vs hybrid RAG, re-ranking, and basic RAG evaluation.

**Estimated time:** 2–2.5 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 06.01 | Retrieval concepts and RAG architectures | `06-01-retrieval-concepts.ipynb` | 📝 Planned |
| 06.02 | Loading and parsing documents (PDF, HTML, Markdown) | `06-02-document-loaders.ipynb` | 📝 Planned |
| 06.03 | Chunking strategies | `06-03-chunking.ipynb` | 📝 Planned |
| 06.04 | Embeddings: local vs hosted | `06-04-embeddings.ipynb` | 📝 Planned |
| 06.05 | Vector stores: in-memory → Chroma → production options | `06-05-vector-stores.ipynb` | 📝 Planned |
| 06.06 | 2-step RAG with citations | `06-06-two-step-rag.ipynb` | 📝 Planned |
| 06.07 | Agentic RAG with `create_agent` | `06-07-agentic-rag.ipynb` | 📝 Planned |
| 06.08 | Hybrid search, query rewriting, and re-ranking | `06-08-hybrid-and-reranking.ipynb` | 📝 Planned |
| 06.09 | Measuring RAG quality (preview of Module 11) | `06-09-rag-evaluation-preview.ipynb` | 📝 Planned |

## Project

**Project 06 — Cited Knowledge Assistant**: Q&A over your own notes (or a public corpus such as a set of official PDFs) with trustworthy citations.

Project files go in `project/`.

## Jupyter skill

Data hygiene, caching embeddings, persisting stores outside git.

## `src/mastery` increment

`mastery/rag/` (loaders, splitter presets, `build_index()`, `retrieve()`, citation formatter).

## Research checkpoint

The `/oss/python/langchain/rag` URL now redirects to a Deep Agents RAG page. Find the current recommended LangChain RAG entry points and log them. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 05](../05-mcp-and-external-tools/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 07](../07-langgraph-fundamentals/) →
