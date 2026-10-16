# Project 06 — Cited Knowledge Assistant

> **Module 06 · Documents, Embeddings & RAG** · ⏱️ 7–9 hours · Docs verified 2026-10-12

**Goal:** Q&A over a mixed PDF + Markdown corpus with **trustworthy citations**: every quote is checked against the retrieved chunks in code, out-of-corpus questions get "I don't know", and two variants (2-step and agentic RAG) are measured on the same questions so you can recommend one.

| File | What it is |
|---|---|
| [`06-project-cited-knowledge-assistant.ipynb`](06-project-cited-knowledge-assistant.ipynb) | **Starter.** Runs top to bottom from the start. Five `# TODO` blocks are yours to complete, each with a collapsed hint |
| [`solutions/06-project-cited-knowledge-assistant-solution.ipynb`](solutions/06-project-cited-knowledge-assistant-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried, or when you are stuck on one TODO |

Data: [`data/samples/rag/corpus/`](../../../data/samples/rag/corpus/) (Orbita Labs, a fictional weather-station maker: 24 Markdown files + 8 PDFs = 32 files, 47 documents after PDF pages) and [`project06-test-set.jsonl`](../../../data/samples/rag/project06-test-set.jsonl) (the held-out test set; the lessons' [`golden-set.jsonl`](../../../data/samples/rag/golden-set.jsonl) (20 questions: 16 with expected sources and an `answer_contains` string, 4 out of corpus). The index goes to the git-ignored `data/vectorstores/project06-md800-100-<model>/` (the name includes the splitter settings and the embedding model, built by `mastery.rag.collection_name`); the comparison table to `data/outputs/m06/`. Project 08 reuses this index.

## Requirements

1. **Index ≥ 30 documents** with `source` / `page` (1-based) metadata: `load_corpus` → `split_documents(..., "markdown", 800, 100)` → **Chroma persisted** (cosine, ids = `chunk_id`). Re-indexing never duplicates, and re-indexing a shortened document deletes its old chunks (`mastery.rag.sync_index`), so nothing stale is ever retrieved.
2. **Two variants on the same store, both yours:** 2-step (`retrieve` top-5 → `format_context(docs, with_ids=True)` → one `with_structured_output(ChunkCitedAnswer)` call) and agentic (`create_agent` + the provided `search_docs` retriever tool + `ToolStrategy(ChunkCitedAnswer)`, max 3 searches, citations verified against the chunks the agent actually saw). A provided **long-context baseline** (the whole ~4k-token corpus in every prompt, no retrieval) is reported next to them: RAG has to beat it.
3. **`ChunkCitedAnswer(answer, citations: list[ChunkCitation(source, page, quote, chunk_id)])`.** Every citation names the chunk it quotes (the `id=` in the context header). `enforce_citations` **fails closed**: an answer ships only if every citation passes `verify_citations(..., require_chunk_id=True)`: the named chunk was retrieved, its source and page match, and it contains the quote (at least 12 characters, normalised). A real sentence attributed to the wrong chunk fails.
4. **Stratified test set (72 questions):** 54 answerable in 6 strata (product pages 10, policies 10, support FAQs 10, release notes 6, PDFs 14, guides 4) and 18 to decline (8 *unanswerable*: on-topic, not in the docs; 10 *out of scope*: off-topic requests and an instruction). Report recall@5 over the answerable questions, correctness (`answer_contains`), a per-stratum table, input tokens per question and an estimated $ per 1,000 questions, for every variant, with 95% intervals and a paired comparison (Step 6). No test question appears in the lessons' golden set.
5. **Don't-know policy:** no verifiable evidence, or a question outside Orbita's products → `NOT_FOUND`. All 18 unanswerable and out-of-scope questions must get it (a decline is graded as the correct answer), and real questions must still get answers.

| TODO | Where | What |
|---|---|---|
| 1 | Step 1 | `index_corpus`: a persisted index that never duplicates and never keeps stale chunks |
| 2 | Step 2 | `enforce_citations`: your citation policy (fail closed) |
| 3 | Step 3 | `two_step`: variant A, one retrieval + one structured call + the policy |
| 4 | Step 5 | `score`: the metrics of 06.09 (a reference scorer re-computes them) |
| 5 | Step 4 | `agentic`: variant B, the 06.07 agent with the same policy |

## Acceptance criteria (5 checks in Step 6)

The checks score your runs with `mastery.rag.score_answers`, an independent reference scorer, so they can't be passed by a `score()` that reports the wrong numbers, or by a system that declines everything.

- **Recall@5 ≥ 0.8** for both variants.
- **Real answers:** LIVE: correct on **≥ 60%** of the answerable questions that ran and **≤ 30%** "don't know" on them (OFFLINE, with the dull scripted reader: 45% / 35%), and **a decline on every** unanswerable and out-of-scope question that ran, both variants.
- **Zero fabricated citations** in final answers (a wrong or missing chunk id counts), and every real answer is cited.
- **Your `score()` agrees** with the reference scorer (TODO 4).
- **Comparison table written** with both variants. Then write your recommendation in the Findings cell: quality (with its interval, and whether the paired comparison found a real difference), cost (input tokens, $ per 1,000 questions), latency, predictability, and how RAG compares with the long-context baseline.
- **Restart & Run All** passes with `GROQ_API_KEY` and without any key. Outputs cleared; `data/outputs/` and `data/vectorstores/` never committed.

## Modes

- **LIVE** (`GROQ_API_KEY` set): `openai/gpt-oss-20b` (`reasoning_effort="low"`) for both variants on a **stratified sample of 24 questions** (`LIVE_QUESTIONS = 24`, 3 per stratum): roughly 100–180k tokens on the free tier. `LIVE_QUESTIONS = None` runs all 72 (about 3×; it may not fit in one day's free-tier quota).
- **OFFLINE DEMO** (no key): scripted extractive readers quote the best retrieved sentence (never invent text). Reference results with bge-small: recall@5 **1.00**, correct **27/54** for both variants, declined **18/18**, **0** fabricated citations. The scripted reader gets 0/10 on product pages (it can't map "cost" to "Price:"): the per-stratum table shows it, the average hides it.
- **Embeddings:** local `BAAI/bge-small-en-v1.5` via fastembed (`pip install -e ".[dev,embeddings]"`, ~67 MB download once). Without it the notebook falls back to `HashingEmbeddings` with a ⚠️: still 5/5 checks here, but weaker ranking (vector R@1 0.78 vs 0.91 in Step 7), and there the overlap re-ranker *helps* (0.91), unlike with bge-small.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Index and lifecycle | Persisted Chroma, no duplicates, no stale chunks after an edit (the scratch check) | Also handles a deleted file and reports added / updated / deleted per run |
| Citations | Fail-closed policy; zero fabricated citations in final answers | Checks that each sentence of an answer is supported, not only that each quote exists |
| Abstention | Declines all 18 unanswerable and out-of-scope questions, ≤ 30% false don't-know (LIVE) | Writes 4 near-miss questions of your own (in-domain, not answered by the corpus) and handles them |
| Evaluation | Both variants scored, per stratum too; your `score()` matches the reference | Intervals and the paired verdict quoted in Findings, plus a per-question analysis of every ❌ (retrieval or reading?) |
| Comparison and recommendation | Filled table and 3–5 sentences, including the long-context baseline | A decision-log entry with cost per 1,000 questions and latency, saying when you would switch |
| Hygiene | Restart & Run All in both modes; outputs cleared; no stores committed | Stretch ablation run and interpreted for the embeddings you used |

## Stretch goals

- **`RUN_STRETCH = True` (default):** hybrid (BM25 + vector, RRF) and cross-encoder re-ranking ablation, retrieval metrics only (no tokens; the re-ranker is a ~80 MB download, else the offline `OverlapReranker`). Our result on the test set: recall@5 1.00 for all four, R@1 0.94 for hybrid vs 0.90 for the others (two questions); re-ranking did not help. Report what you measure.
- **pgvector via Docker** (text instructions in Step 7): `pgvector/pgvector:pg17` + `langchain-postgres`, then rerun Steps 3–6.

## Stack

Free: Groq (gpt-oss-20b), fastembed local embeddings and re-ranker, Chroma. Paid alternatives: hosted embeddings (OpenAI `text-embedding-3-small`, Lesson 06.04), Cohere Rerank (06.08), Pinecone or another managed vector DB.
