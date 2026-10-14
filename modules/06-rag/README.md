# Module 06 — Documents, Embeddings & RAG

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 06](../../COURSE_OUTLINE.md#module-06--documents-embeddings--rag)

**Goals:** Build retrieval systems that are grounded, cited, and measurable: loading and parsing documents, chunking, embeddings, vector stores, 2-step RAG vs agentic RAG vs hybrid RAG, re-ranking, and basic RAG evaluation.

**Estimated time:** 2–2.5 weeks (about 16–20 hours of lessons plus 6–8 hours for the project).

## Before you start this module

Run this **once**, in **Git Bash**, from the **repo root**, with the **`lc-mastery`** environment active (the prompt starts with `(lc-mastery)`).

```bash
cd ~/path/to/langchain-langgraph-mastery   # your clone; quote the path if it has spaces
conda activate lc-mastery
git pull                                   # get this module's files
python -m pip install -e ".[dev,embeddings]"   # re-run after every pull: Module 06 adds the [rag] extra (splitters, Chroma, pypdf, bs4); [embeddings] = fastembed for real local embeddings
python -m pip check                        # expect: No broken requirements found. (if not: see the note below the table)
python -c "import importlib.metadata as m; print('langgraph-api', m.version('langgraph-api'))"   # expect: 0.16.x or newer
python -m pytest -q                        # expect: "... passed" and no failures (offline, no keys, no downloads)
python -c "import mastery.rag, chromadb, pypdf; print('rag ok', chromadb.__version__)"   # expect: rag ok 1.5.x
python -c "from mastery.memory import local_embeddings; print('embeddings ok', local_embeddings().dims)"   # 🌐 first run downloads ~67 MB; expect: embeddings ok 384
```

| | |
|---|---|
| 🔑 Keys | `GROQ_API_KEY` (optional: without it 💸 cells print `⏭️ Skipped` and an offline extractive reader stands in). **No new keys.** Optional paid comparisons (`OPENAI_API_KEY` embeddings, `COHERE_API_KEY` re-ranking) are clearly marked and skipped without a key |
| 💰 Cost | $0. Embeddings and re-ranking run **locally on your CPU** (fastembed, ONNX, no PyTorch). Chroma runs in-process. Groq free tier: a RAG answer is ~1.5–4k input tokens (the retrieved chunks), so keep `k` small |
| 💾 Disk | ~67 MB embedding model + ~80 MB re-ranker (cached in `~/.cache/fastembed`), a few MB of Chroma files in `data/vectorstores/` (git-ignored) |
| 🌐 Network | Only the first model download (Hugging Face). Offline, corporate proxy, or `[embeddings]` not installed? 🌐 cells print ⚠️ and fall back to the offline `HashingEmbeddings`; everything still runs |
| ✅ Ready when | `pip check` is clean, `pytest` shows no failures, `rag ok` and `embeddings ok 384` print |

**Saw `ERROR: pip's dependency resolver does not currently take into account...`?** If you installed Module 06 before 2026-10-12 evening, pip may have **downgraded** `langgraph-api` (0.16 → 0.10) to fit Chroma's OpenTelemetry packages and left orphans behind. The course now pins `langgraph-api>=0.16.0`. Fix once:

```bash
git pull && python -m pip install -e ".[dev,embeddings]"   # restores langgraph-api 0.16.x, opentelemetry 1.42.x
python -m pip check                                         # lists leftovers, e.g. opentelemetry-exporter-otlp-common / -http-transport / -prometheus
python -m pip show opentelemetry-exporter-otlp-common | grep Required-by   # empty = nothing needs it
python -m pip uninstall -y opentelemetry-exporter-otlp-common opentelemetry-exporter-http-transport   # only the ones pip check named AND nothing requires
python -m pip check                                         # expect: No broken requirements found.
```

Never uninstall a package whose `Required-by:` is not empty (`opentelemetry-exporter-prometheus` is **required** by langgraph-api 0.16; it only looks orphaned while 0.10 is installed). How to read the warning: [setup guide · Dependency warnings](../00-foundations/00-02-create-course-env.md#dependency-warnings-after-an-install).

If `pip install`, `pytest` or the model download fails, see the [setup guide's troubleshooting](../00-foundations/00-02-create-course-env.md#troubleshooting). SSL certificate errors on Anaconda (also for `huggingface.co`): Step 4b. `DLL load failed` from `onnxruntime` on Windows: install the [Microsoft Visual C++ Redistributable (x64)](https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist) and restart Git Bash.

## How to work through this module

1. **Do [Before you start this module](#before-you-start-this-module) first** (once per pull). Module 06 adds `mastery.rag` and the course corpus in `data/samples/rag/` (fictional "Orbita Labs" Nimbus weather stations: 24 Markdown files, 8 PDFs, a 20-question golden set).
2. **Start Jupyter from the repo root** (`jupyter lab` in Git Bash) and pick the **Python (lc-mastery)** kernel in every notebook.
3. **Go in order.** 06.01 is the map; 06.02–06.05 build the index step by step (load → split → embed → store); 06.06–06.08 answer questions with it; 06.09 measures. The project combines all of it.
4. **Read the cell markers.** 🧪 = offline (free) · 🌐 = downloads a model once (no key, no tokens) · 💸 = calls a model. No key? Every 💸 cell prints `⏭️ Skipped`, so **Restart & Run All** always completes.
5. **Windows notes.** Chroma keeps its files open while the kernel runs: to delete an index, use `reset_chroma(store)` or restart the kernel first (`PermissionError: [WinError 32]` otherwise). Keep the repo in a short path (e.g. `C:\dev\...`) to avoid 260-character path errors in model caches. Files are read as UTF-8 with CRLF handled.
6. **Before you commit:** *Kernel → Restart Kernel and Run All Cells…*, *Edit → Clear Outputs of All Cells*, save, then `python -m pytest -q`. `data/vectorstores/` and `data/cache/` are git-ignored: never commit indexes or embedding caches.

## Lessons

| Lesson | Title | Notebook | Time | Keys |
|---|---|---|---|---|
| 06.01 | Retrieval concepts and RAG architectures | [`06-01-retrieval-concepts.ipynb`](06-01-retrieval-concepts.ipynb) | 60–90 min | `GROQ_API_KEY` (optional) |
| 06.02 | Loading and parsing documents (PDF, HTML, Markdown) | [`06-02-document-loaders.ipynb`](06-02-document-loaders.ipynb) | 90–120 min | none |
| 06.03 | Chunking strategies | [`06-03-chunking.ipynb`](06-03-chunking.ipynb) | 90–120 min | none |
| 06.04 | Embeddings: local vs hosted | [`06-04-embeddings.ipynb`](06-04-embeddings.ipynb) | 120–150 min | none (`OPENAI_API_KEY` optional) |
| 06.05 | Vector stores: in-memory → Chroma → production options | [`06-05-vector-stores.ipynb`](06-05-vector-stores.ipynb) | 120–150 min | none |
| 06.06 | 2-step RAG with citations | [`06-06-two-step-rag.ipynb`](06-06-two-step-rag.ipynb) | 150–180 min | `GROQ_API_KEY` (optional) |
| 06.07 | Agentic RAG with `create_agent` | [`06-07-agentic-rag.ipynb`](06-07-agentic-rag.ipynb) | 150–180 min | `GROQ_API_KEY` (optional) |
| 06.08 | Hybrid search, query rewriting, and re-ranking | [`06-08-hybrid-and-reranking.ipynb`](06-08-hybrid-and-reranking.ipynb) | 120–150 min | `GROQ_API_KEY`, `COHERE_API_KEY` (both optional) |
| 06.09 | Measuring RAG quality (preview of Module 10) | [`06-09-rag-evaluation-preview.ipynb`](06-09-rag-evaluation-preview.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |

**What each lesson gives you**

- **06.01:** why models need retrieval; indexing (load → split → embed → store) vs retrieval + generation; 2-step, agentic and hybrid RAG side by side on one question; the current LangChain RAG entry points (the old `langchain/rag` URL now redirects).
- **06.02:** PDF pages with pypdf (1-based `page`), HTML without nav/script noise (BeautifulSoup), Markdown with titles; repo-relative POSIX `source`; scanned PDFs and encodings; Docling and Unstructured (when, and why not here).
- **06.03:** recursive, Markdown-header and token splitting; size/overlap tuning measured on the golden set; metadata and stable `chunk_id`s; `start_index`.
- **06.04:** what an embedding is; offline `HashingEmbeddings` vs local `bge-small` (fastembed) vs paid models, measured on a labelled paraphrase set; Ollama and sentence-transformers as alternatives; **caching embeddings**.
- **06.05:** `InMemoryVectorStore`, then **Chroma persisted to `data/vectorstores/`** (upserts by id, cosine distance, reopen without re-embedding, metadata filters); pgvector, Qdrant, Pinecone surveyed.
- **06.06:** retrieve → prompt → `with_structured_output(CitedAnswer)`; quotes verified in code; the "not in the sources" reply; retrieval in the LangSmith trace (`run_type="retriever"`); prompt injection inside documents.
- **06.07:** retrieval as a tool (`content_and_artifact`), an agent that decides when and what to search, routing across two knowledge bases; cost and latency vs 2-step.
- **06.08:** BM25 + vectors fused with reciprocal-rank fusion, explicit query rewriting (multi-query), cross-encoder re-ranking (local; Cohere optional); measured gains.
- **06.09:** golden set, hit rate, recall@k, MRR; groundedness with an LLM judge; a small report you can rerun after every change.

## Project

**[Project 06 — Cited Knowledge Assistant](project/README.md)**: Q&A over the 32-document Nimbus corpus (Markdown + PDF) with trustworthy citations, in two variants (2-step and agentic) on the same Chroma index and the same 20 questions. Every quote is verified in code. Acceptance: recall@5 ≥ 0.8, zero fabricated citations, "don't know" on the 4 out-of-corpus questions, a comparison table and a recommendation.

| File | Use |
|---|---|
| [`project/README.md`](project/README.md) | Spec, acceptance criteria, modes, stretch goals |
| [`project/06-project-cited-knowledge-assistant.ipynb`](project/06-project-cited-knowledge-assistant.ipynb) | **Starter** with four `# TODO`s (runs from day one, also offline) |
| [`project/solutions/06-project-cited-knowledge-assistant-solution.ipynb`](project/solutions/06-project-cited-knowledge-assistant-solution.ipynb) | **Reference solution** (open after trying) |

## Jupyter skill in this module

**Data hygiene: caching embeddings and persisting stores outside git** (06.04, 06.05; used in every later notebook):

| Skill | Where |
|---|---|
| Know where a notebook writes: `data/vectorstores/`, `data/cache/`, `~/.cache/fastembed`, and check with `git check-ignore -v <path>` | 06.05 |
| `CachedEmbeddings`: re-running a cell re-embeds nothing; cache keyed by model + text | 06.04 |
| Time a cell with `%%time` / `%time` (first vs cached run) | 06.04 |
| Persist an index once, reopen it in later notebooks without re-embedding (same model!) | 06.05 |
| Free file locks before deleting an index on Windows (`reset_chroma`, or restart the kernel) | 06.05 |
| Never commit indexes, caches or private documents; keep sample data small and fictional | 06.02, 06.05 |

## `src/mastery` increment

| File | What it does | Tests |
|---|---|---|
| [`src/mastery/rag/loaders.py`](../../src/mastery/rag/loaders.py) | `load_markdown`, `load_pdf` (1-based `page`), `load_html` (noise removed), `load_corpus` (repo-/corpus-relative POSIX `source`) | [`tests/unit/test_rag.py`](../../tests/unit/test_rag.py) |
| [`src/mastery/rag/splitters.py`](../../src/mastery/rag/splitters.py) | `split_documents(preset="recursive"\|"markdown"\|"tokens")` with stable `chunk_id`; `chunk_stats` | same |
| [`src/mastery/rag/index.py`](../../src/mastery/rag/index.py) | `CachedEmbeddings` (SQLite), `default_embeddings` (fastembed → Hashing fallback), `build_index` (memory/Chroma, upsert by id), `open_chroma`, `reset_chroma`, `vectorstore_dir`, `folder_size` | same |
| [`src/mastery/rag/retrieve.py`](../../src/mastery/rag/retrieve.py) | `retrieve` (comparable scores, filters), `BM25`, `rrf`, `hybrid_search`, `cross_encoder_reranker`, `OverlapReranker`, `make_retriever_tool` | same |
| [`src/mastery/rag/citations.py`](../../src/mastery/rag/citations.py) | `Citation`, `CitedAnswer`, `format_context`/`parse_context`, `verify_citations`, `format_citations`, `is_dont_know`, `extractive_answer`/`extractive_reader` (offline baseline) | same |
| [`src/mastery/rag/eval.py`](../../src/mastery/rag/eval.py) | `recall_at_k`, `mrr`, `evaluate_retrieval` (hit rate, recall, MRR per question) | same |

## Production notes

> ⚠️ **Production note: retrieved documents are untrusted input.**
> A chunk can contain "ignore your instructions". Fence context as data, verify every citation in code, and never let retrieved text trigger tools with side effects without a human (Lesson 04.05).

> ⚠️ **Production note: an index is a build artifact.**
> Version it with the embedding model name and the splitter settings, rebuild it from the source documents, and never mix vectors from two models in one collection. Re-index on a schedule when the documents change.

Each lesson has its own production notes; they are collected in [`docs/production-notes.md`](../../docs/production-notes.md).

## Research checkpoint

The `/oss/python/langchain/rag` URL now redirects to a **Deep Agents** RAG page. As of 2026-10-12 the current entry points are: [Retrieval](https://docs.langchain.com/oss/python/deepagents/retrieval) (concepts and architectures), [Semantic search / knowledge base](https://docs.langchain.com/oss/python/langchain/knowledge-base) (load → split → embed → store), [Agentic RAG with LangGraph](https://docs.langchain.com/oss/python/langgraph/agentic-rag), and [RAG with Deep Agents](https://docs.langchain.com/oss/python/deepagents/rag). Check whether that is still true and log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

✅ Built (docs verified 2026-10-12).

---

← [Module 05](../05-mcp-and-external-tools/README.md) · [Course outline](../../COURSE_OUTLINE.md) · [Module 07](../07-langgraph-fundamentals/) →
