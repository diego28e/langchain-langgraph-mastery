# Project 06 — Cited Knowledge Assistant

> **Module 06 · Documents, Embeddings & RAG** · ⏱️ 6–8 hours · Docs verified 2026-10-12

**Goal:** Q&A over a mixed PDF + Markdown corpus with **trustworthy citations**: every quote is checked against the retrieved chunks in code, out-of-corpus questions get "I don't know", and two variants (2-step and agentic RAG) are measured on the same questions so you can recommend one.

| File | What it is |
|---|---|
| [`06-project-cited-knowledge-assistant.ipynb`](06-project-cited-knowledge-assistant.ipynb) | **Starter.** Runs top to bottom from the start. Four `# TODO` blocks are yours to complete |
| [`solutions/06-project-cited-knowledge-assistant-solution.ipynb`](solutions/06-project-cited-knowledge-assistant-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried, or when you are stuck on one TODO |

Data: [`data/samples/rag/corpus/`](../../../data/samples/rag/corpus/) (Orbita Labs, a fictional weather-station maker: 24 Markdown files + 8 PDFs = 32 files, 47 documents after PDF pages) and [`golden-set.jsonl`](../../../data/samples/rag/golden-set.jsonl) (20 questions: 16 with expected sources and an `answer_contains` string, 4 out of corpus). The index goes to the git-ignored `data/vectorstores/project06-<model>/`; the comparison table to `data/outputs/m06/`. Project 08 reuses this index.

## Requirements

1. **Index ≥ 30 documents** with `source` / `page` (1-based) metadata: `load_corpus` → `split_documents(..., "markdown", 800, 100)` → **Chroma persisted** (cosine, ids = `chunk_id`, so re-indexing upserts).
2. **Two variants on the same store:** 2-step (`retrieve` top-5 → one `with_structured_output(CitedAnswer)` call) and agentic (`create_agent` + `search_docs` retriever tool + `ToolStrategy(CitedAnswer)`, max 3 searches).
3. **`CitedAnswer(answer, citations: list[Citation(source, page, quote)])`.** `enforce_citations` keeps only citations that `verify_citations` confirms (right file, right page, quote is a substring after whitespace normalization).
4. **Golden set:** recall@5 over the 16 in-corpus questions, correctness (`answer_contains`), for both variants.
5. **Don't-know policy:** no verifiable evidence → `NOT_FOUND`; the 4 out-of-corpus questions must get it.

| TODO | Where | What |
|---|---|---|
| 1 | Step 1 | `index_corpus`: `build_index(kind="chroma", collection=..., persist_dir=...)` |
| 2 | Step 2 | `enforce_citations`: drop fabricated citations; no valid evidence → don't-know |
| 3 | Step 3 | `two_step`: retrieve, call the chain, enforce citations |
| 4 | Step 5 | `score`: recall@5, correct n/16, don't-know n/4, fabricated citations |

## Acceptance criteria (5 checks in Step 6)

- **Recall@5 ≥ 0.8** for both variants (or a written explanation of why not, plus what you tried).
- **Zero fabricated citations** in final answers, and every answer is either cited or a don't-know.
- **Don't-know on 4/4** out-of-corpus questions, both variants.
- **Comparison table + recommendation** (the Findings cell): quality, cost (model calls), latency, predictability.
- **Restart & Run All** passes with `GROQ_API_KEY` and without any key. Outputs cleared; `data/outputs/` and `data/vectorstores/` never committed.

## Modes

- **LIVE** (`GROQ_API_KEY` set): `openai/gpt-oss-20b` (`reasoning_effort="low"`) for both variants. Roughly 80–150k tokens for 2 × 20 questions on the free tier; set `LIVE_QUESTIONS = 6` to try it cheaply first. Read the ❌ lines yourself: `answer_contains` is a strict string match.
- **OFFLINE DEMO** (no key): scripted extractive readers quote the best retrieved sentence (never invent text). Reference results with bge-small: recall@5 **1.00**, correct **12/16** for both variants, don't-know **4/4**, **0** fabricated. The untouched starter passes 2/5 checks, with ❌ pointing at the TODOs.
- **Embeddings:** local `BAAI/bge-small-en-v1.5` via fastembed (`pip install -e ".[dev,embeddings]"`, ~67 MB download once). Without it the notebook falls back to `HashingEmbeddings` with a ⚠️: still 5/5 checks here, but weaker ranking (vector R@1 0.78 vs 0.91 in Step 7).

## Stretch goals

- **`RUN_STRETCH = True` (default):** hybrid (BM25 + vector, RRF) and cross-encoder re-ranking ablation, retrieval metrics only (no tokens; the re-ranker is a ~80 MB download, else the offline `OverlapReranker`). Our result: identical totals; re-ranking swaps which question ranks 2nd. Report what you measure.
- **pgvector via Docker** (text instructions in Step 7): `pgvector/pgvector:pg17` + `langchain-postgres`, then rerun Steps 3–6.

## Stack

Free: Groq (gpt-oss-20b), fastembed local embeddings and re-ranker, Chroma. Paid alternatives: hosted embeddings (OpenAI `text-embedding-3-small`, Lesson 06.04), Cohere Rerank (06.08), Pinecone or another managed vector DB.
