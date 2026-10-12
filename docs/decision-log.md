# Model & Provider Decision Log

> Every non-trivial choice of model, provider, vector store, or hosting option gets an entry. Future you (and your students) will want to know **why**.

## Template

```text
### D-NNN · <short title> · YYYY-MM-DD
- Context:    <task, constraints (cost, latency, privacy, rate limits)>
- Options:    <A, B, C with one line each>
- Decision:   <chosen option>
- Evidence:   <benchmarks from your notebooks, links to official docs/pricing pages, trace links>
- Trade-offs: <what you give up>
- Revisit:    <date or trigger, e.g. "if Groq deprecates model X">
```

---

## Decisions

> The entries below are **examples** that show the format and explain the course defaults. Add your own decisions below them.

### D-001 · Default chat/agent models for the course · 2026-10-11
- Context: Free-first learning on Groq, with tool calling and structured output required from Module 02.
- Options: (A) `openai/gpt-oss-20b` production, fastest/cheapest; (B) `openai/gpt-oss-120b` production, stronger reasoning; (C) `qwen/qwen3.8-27b` preview, multimodal.
- Decision: A as the "fast" default, B as the "reasoning" default, C only for vision lessons.
- Evidence: https://console.groq.com/docs/models (production vs preview), https://console.groq.com/docs/deprecations.
- Trade-offs: Preview models can be retired at short notice. Open-weight models may trail paid frontier models on hard tool-use tasks.
- Revisit: at every research checkpoint, or when Groq announces a deprecation.

### D-002 · Paid quality benchmark · 2026-10-11
- Context: Need a stronger paid model to check whether free Groq models are "good enough", and to act as an LLM-as-judge. Budget: a few dollars for the whole course.
- Options: (A) OpenAI `gpt-6-luna` ($0.10 in / $0.50 out per 1M tokens) with `gpt-6.1-sol` ($2 / $10) as the ceiling; (B) Gemini `gemini-3.8-flash` ($0.75 / $3.75 until 2026-12-31) or `gemini-3.5-flash-lite` ($0.30 / $2.50), with a free tier; (C) Anthropic.
- Decision: A by default. B when you want a free tier and only use public or synthetic data.
- Evidence: [docs/paid-benchmark-openai-vs-gemini.md](paid-benchmark-openai-vs-gemini.md) (OpenAI and Gemini pricing and model pages).
- Trade-offs: OpenAI needs about $5 of credits. Gemini's free tier may use your prompts to improve Google products.
- Revisit: 2027-01-01 (Gemini 3.8 Flash price change) or when either provider releases a new cheap model.

### D-003 · Default web search provider · 2026-10-11
- Context: Agents in Modules 05, 07, and 08 need fresh web information.
- Options: (A) Groq built-in `browser_search` on GPT-OSS models (no extra key); (B) Tavily via `langchain-tavily` (1,000 free credits/month, works with any model).
- Decision: A by default. B when you need structured output in the same call, raw sources with domain/date filters, or a non-Groq model.
- Evidence: [docs/web-search-groq-vs-tavily.md](web-search-groq-vs-tavily.md).
- Trade-offs: Groq browser search is not compatible with structured outputs and only works on GPT-OSS models.
- Revisit: when Groq changes its built-in tools (check the Groq built-in tools page).

### D-004 · Model for deep agents (Module 10) · 2026-10-11
- Context: Deep agents make many model calls per task and spawn subagents. They need a model that handles long tool-calling loops well, and enough free quota to finish a run.
- Options: (A) Groq `openai/gpt-oss-120b` + `openai/gpt-oss-20b` (course default elsewhere, free tier 8K tokens/min and 200K tokens/day, not in the official Deep Agents eval matrix); (B) Gemini `gemini-3.6-flash` (stable, on the official Deep Agents suggested list, free tier with no billing account); (C) OpenAI `gpt-6-luna` (paid).
- Decision: B by default for Module 10, A as a documented option, C as the paid benchmark.
- Evidence: https://docs.langchain.com/oss/python/deepagents/models (suggested models), https://ai.google.dev/gemini-api/docs/pricing (free tier), https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash (stable ID), https://console.groq.com/docs/rate-limits.
- Trade-offs: Gemini's free tier may use prompts for product improvement and human reviewers may read them, so only public or synthetic data. Free-tier limits are not published as fixed numbers (check AI Studio). Web search stays a tool (Groq or Tavily) because Google Search grounding is paid only.
- Revisit: when `gemini-3.6-flash` gets a shutdown date, when the Deep Agents suggested list changes, or on 2027-01-01 (price change).

### D-005 · Structured output strategy for Groq agents · 2026-10-12
- Context: Agents with tools must also return a validated object (Lesson 02.05, Project 02). `ChatGroq` reports `structured_output: True` in its model profile, so a bare `response_format=Schema` makes `create_agent` pick `ProviderStrategy` (JSON-schema mode).
- Options: (A) bare schema (auto); (B) `ProviderStrategy` explicitly; (C) `ToolStrategy` explicitly.
- Decision: C whenever the agent has tools. B only for tool-less extraction agents, never streamed.
- Evidence: Groq structured outputs page ("Streaming and tool use are not currently supported with Structured Outputs"): https://console.groq.com/docs/structured-outputs; LangChain structured output docs (auto selection from the model profile): https://docs.langchain.com/oss/python/langchain/structured-output; the auto path reproduced against the course's local Groq stand-in. Not yet confirmed against the live API: Lesson 02.05 has a 💸 cell for that.
- Trade-offs: `ToolStrategy` forces `tool_choice="any"` and adds one tool schema to every request (more input tokens).
- Revisit: when Groq supports JSON schema together with tools, or when `ChatGroq`'s profile changes.

### D-006 · Groq `browser_search` from LangChain · 2026-10-12
- Context: D-003 makes Groq `browser_search` the default web search. In `langchain-groq` 1.1.3, `bind_tools([{"type": "browser_search"}])` (and `create_agent(tools=[...])` with that dict) raises `ValueError: Unsupported function`, because the tool converter only passes through tool types it knows.
- Options: (A) `model.bind(tools=[{"type": "browser_search"}], tool_choice="required")` (raw request parameters); (B) Tavily as a normal client-side tool; (C) `ChatOpenAI` pointed at Groq's OpenAI-compatible URL.
- Decision: A for direct calls (Lesson 02.02), and wrapped in a small `@tool` when an agent needs it (Module 05). B stays the alternative when you need structured output, filters or non-Groq models.
- Evidence: `langchain_groq/chat_models.py` and `langchain_core/utils/function_calling.py` (installed sources, 2026-10-12); https://console.groq.com/docs/tool-use/built-in-tools/browser-search. No matching GitHub issue found on 2026-10-12.
- Trade-offs: `.bind()` bypasses LangChain's tool conversion, so the agent can't mix it with local tools in one call.
- Revisit: when a `langchain-groq` release supports built-in tools in `bind_tools`.

### D-007 · Persistence and local embeddings for Module 03 · 2026-10-12
- Context: Module 03 needs memory that survives kernel restarts on a Windows laptop, and the project's stretch asks for semantic memory search with free, local embeddings.
- Options: persistence (A) SQLite (`langgraph-checkpoint-sqlite`: `SqliteSaver` + `SqliteStore`), (B) Postgres in Docker; embeddings (C) `fastembed` (ONNX Runtime, no PyTorch), (D) `langchain-huggingface` + `sentence-transformers` (PyTorch), (E) Ollama embeddings.
- Decision: A for Modules 03 and 08 (one file per kind of memory under git-ignored `data/outputs/memory/`; Postgres in Module 13). C for Module 03 as an optional `[embeddings]` extra, wrapped by `mastery.memory.local_embeddings()` with `BAAI/bge-small-en-v1.5` (384 dims), cached in `~/.cache/fastembed`. Offline cells and tests use `HashingEmbeddings` (deterministic, no download).
- Evidence: PyPI 2026-10-12: langgraph-checkpoint-sqlite 3.1.1 (requires aiosqlite, sqlite-vec), fastembed 0.9.0 (onnxruntime, no torch). `langchain-huggingface[full]` 1.2.3 pins `sentence-transformers<6` while 6.1.0 is current, and pulls PyTorch (hundreds of MB). Measured on the box: fastembed model load + 3 embeddings ≈ 2 s on CPU; `SqliteStore` vector search via sqlite-vec works.
- Trade-offs: fastembed is not the embedding stack of Module 06 (sentence-transformers / Ollama, compared there). SQLite is single-process; `SqliteSaver` turns on WAL (`-wal`/`-shm` files); Windows locks open files (`close()` first).
- Revisit: in Module 06 (pick one local embedding stack for the course), or when `langchain-huggingface` supports sentence-transformers 6.

### D-008 · Per-call response format with tools on Groq · 2026-10-12
- Context: Lesson 03.05 changes the response format per call (`@wrap_model_call` + `request.override(response_format=...)`), the pattern shown in the context-engineering docs.
- Options: (A) override with a bare Pydantic class (docs example); (B) override with an undeclared `ToolStrategy(...)`; (C) declare `ToolStrategy(Schema)` in `create_agent(response_format=...)` and override to `None` (or select it) per call.
- Decision: C.
- Evidence: measured with langchain 1.4.4 against the local Groq stand-in: A falls back to provider JSON-schema mode, which Groq rejects together with tools (400, see D-005); B raises `ValueError: ToolStrategy specifies tool '...' which wasn't declared in the original response format when creating the agent`; C works both ways.
- Trade-offs: every format you may select must be declared up front (a `Union[...]` for several).
- Revisit: when Groq supports JSON schema with tools, or when `create_agent` accepts new formats at call time.

### D-009 · No new dependencies for Module 04 · 2026-10-12
- Context: Module 04 needs PII handling, guardrails, human-in-the-loop and trace redaction.
- Options: (A) only what ships with `langchain` 1.4.4 / `langsmith` 0.14.7 plus small helpers in `mastery.middleware`; (B) add Presidio (PII) or guardrail frameworks.
- Decision: A. `PIIMiddleware`, `HumanInTheLoopMiddleware`, limits, retry and fallback are prebuilt; redaction, injection signals, audit, budget and role filter are ~400 lines in `src/mastery/middleware/` with 27 offline tests.
- Evidence: all 15 prebuilt middleware imported and exercised on 2026-10-12 (langchain 1.4.4); `create_anonymizer` checked end to end against the mock's recorded LangSmith upload bodies (card and addresses absent after anonymizing, present without).
- Trade-offs: regex PII detection is simple and locale-blind (a 10-digit number is redacted as a phone; accepted).
- Revisit: if a later module needs production-grade PII detection.

### D-010 · Layered defences and guard-classifier parsing · 2026-10-12
- Context: Groq's safety models are Preview, and Groq's docs don't state Prompt Guard's exact reply format.
- Decision: never rely on one layer (least-privilege tools, allow-lists, fencing, scanner, classifier, HITL, audit). `parse_guard_score` accepts a probability or a BENIGN/MALICIOUS-style label; anything else → `None`, treated as an attack (fail closed). `parse_verdict` for the safeguard model fails closed too.
- Evidence: model pages on console.groq.com (2026-10-12): both models Preview; Prompt Guard 512-token context. Live formats **not verified** (no key on the build machine): the 04.05 cell prints the raw first reply so learners see it.
- Revisit: after the first live run (log the raw format in `docs/research-log.md`), or when either model leaves Preview.

### D-011 · Where Module 04 writes, and fake sending · 2026-10-12
- Decision: every "send" writes a file under git-ignored `data/outputs/m04/` (`04-05-outbox/`, `04-06-outbox/`, `outbox/`, `project04-audit.jsonl`, `04-06-hitl.sqlite`). No SMTP or email API anywhere in the module.
- Trade-offs: no deliverability or provider-side concerns are taught here.

### D-012 · Validate HITL decisions before resuming · 2026-10-12
- Context: measured with langgraph 1.2.14: after a resume fails (wrong number of decisions), resending correct decisions on the same thread, by interrupt id, or from the paused checkpoint config still raised the same `ValueError`.
- Decision: lessons and the project validate decisions (`check_decisions`) before `Command(resume=...)`, and tell learners to restart on a new `thread_id` if a thread is stuck.
- Revisit: re-test on each langgraph upgrade; remove the warning when fixed.

### D-013 · Async-only MCP tools; async middleware · 2026-10-12
- Context: `langchain.mcp` (langchain 1.4.4, beta) builds async-only tools: sync `invoke` raises `NotImplementedError: StructuredTool does not support sync invocation.` Middleware that defines only sync `wrap_model_call` / `wrap_tool_call` raises `NotImplementedError` under `ainvoke`.
- Decision: every MCP notebook uses top-level `await` and `agent.ainvoke`. `AuditLogMiddleware` and `RoleToolFilterMiddleware` gained `awrap_*` hooks (shared logic, same tests). The beta API is used directly in notebooks; reusable helpers in `mastery/mcp.py` don't import `langchain.mcp`, so a breaking beta change stays in notebook code.
- Evidence: measured on the box 2026-10-12 (langchain 1.4.4, fastmcp 4.1.0, mcp 2.3.0); `tests/unit/test_mcp.py`.
- Revisit: when `langchain.mcp` leaves beta or adds sync tools.

### D-014 · An offline stand-in for the docs MCP server · 2026-10-12
- Context: `https://docs.langchain.com/mcp` is free and keyless, but notebooks and tests must run offline and give stable results.
- Decision: `mastery.mcp_servers.docs_standin` serves `search_docs_by_lang_chain` over `data/samples/mcp/docs-snapshot.json` (86 Python sections captured 2026-10-12) in the real server's `Title/Link/Page/Content` format. 🌐 cells try the real server and fall back with a ⚠️; Project 05 OFFLINE uses the stand-in, LIVE the real server.
- Trade-offs: the snapshot ages; its ranking is word overlap, not the real search. The offline project reader scores 8/10 honestly (2 misses kept on purpose).
- Revisit: refresh the snapshot (`_maintainer/tools/m05/data.py`) when docs URLs change; re-check the benchmark's `expected_page`s.

### D-015 · Annotations are claims: allow-lists and fail-closed policies · 2026-10-12
- Decision: `approval_policy` pauses every tool not marked read-only (no hint → pause). For servers we don't control, pass `trusted_read_only=[...]`: only reviewed names skip approval. `tool_fingerprint` pins reviewed definitions; `poisoned_descriptions` is a tripwire, not a wall. The project gives the agent only allowed tool names (no `submit_feedback`, no `delete_note`).
- Evidence: MCP spec (tool annotations are hints from the server); 05.05 demo of a server that marks `wipe_disk` read-only.

### D-016 · Web search: `.bind`, a `web_search` tool, and an unverified `executed_tools` parse · 2026-10-12
- Context: `bind_tools` can't convert Groq's `browser_search` (D-006), browser search can't be combined with structured output, and a `.bind`-ed model can't also call local tools.
- Decision: `mastery.web_search.make_web_search_tool()` runs the search as its own call inside a normal tool (fenced findings + `Sources:` list + URLs in the artifact), so agents mix it with MCP and local tools and the final answer is structured (two-step pattern). `MASTERY_WEB_SEARCH=tavily` switches backend. `groq_search_sources` reads `executed_tools[].search_results.results[].url`, `browser_results[].url` and URLs in `output`.
- Evidence: field names from Groq's API schema (groq SDK types), 2026-10-12. **Not verified live** (no key on the build machine): 05.01 prints the live `executed_tools` types so learners can check.
- Revisit: after the first live run (log the real shape in `docs/research-log.md`).

### D-017 · `fastmcp` and `langchain-tavily` as an `[mcp]` extra in `[dev]` · 2026-10-12
- Decision: new extra `mcp = ["langchain[mcp]>=1.4.4,<2", "langchain-tavily>=0.2.18,<1"]` (PyPI 2026-10-12: langchain 1.4.4 pulls fastmcp 4.1.0 + mcp 2.3.0; langchain-tavily 0.2.18), included in `[dev]`, so `pip install -e ".[dev]"` (the usual step) installs it and `pytest` covers MCP offline. `requirements.txt` already listed both.
- Trade-offs: a slightly bigger dev install (fastmcp brings uvicorn/starlette/httpx, mostly already present).

### D-018 · A `[rag]` extra in `[dev]`; no `langchain-community` · 2026-10-12
- Decision: `rag = [langchain-text-splitters>=1.1.3, langchain-chroma>=1.1.0, pypdf>=6.20.1, beautifulsoup4>=4.15.0]`, included in `[dev]`. Loaders are ~100 lines in `mastery/rag/loaders.py` on pypdf and bs4 directly, instead of `langchain-community` loaders.
- Evidence: PyPI 2026-10-12 (chromadb 1.5.9 comes with langchain-chroma); the docs' Cohere reranker page states `langchain-community` is no longer maintained.
- Trade-offs: fewer loader formats; Docling (`langchain-docling`) and Unstructured (`langchain-unstructured`) are shown as options in 06.02, not installed.

### D-019 · Local embeddings optional, with a Hashing fallback · 2026-10-12
- Decision: `[embeddings]` (fastembed) stays **out** of `[dev]`; Module 06 asks for `pip install -e ".[dev,embeddings]"`. `default_embeddings()` uses `BAAI/bge-small-en-v1.5` (384 dims, ~67 MB once) and falls back to `HashingEmbeddings(1024)` with a ⚠️ when fastembed or the download is unavailable. Tests always use Hashing (no download in CI).
- Evidence: measured on the golden set: R@1 0.72 (Hashing) vs 0.91 (bge); paraphrases MRR 0.61 vs 0.88.
- Trade-offs: a learner who skips the extra sees worse retrieval, explained in the ⚠️ and in 06.04.

### D-020 · Chroma: cosine, one collection per embedding model, ids = `chunk_id`, 1-based pages · 2026-10-12
- Decision: `build_index(kind="chroma")` sets `hnsw.space = cosine`, disables telemetry, names folders/collections after the model (`nimbus-bge-small-en-v1-5`, `project06-...`) so vectors from two models never mix, and uses `chunk_id = source#p<page>-c<n>` as id (re-indexing upserts). `retrieve` reports `1 − distance` as `score`. Pages are 1-based everywhere (what a reader sees in a PDF viewer).
- Evidence: Chroma default space is l2; collection names need ≥3 characters; `None` metadata values are rejected (measured, chromadb 1.5.9).

### D-021 · Own BM25; re-ranking optional, not the default · 2026-10-12
- Decision: a ~40-line pure-Python `BM25` (no `rank_bm25` dependency; the docs' `retrievers/bm25` page is gone) plus `rrf`. The fastembed cross-encoder (`Xenova/ms-marco-MiniLM-L-6-v2`) and Cohere `rerank-v4.0-fast` are taught and measured, but not on by default.
- Evidence: 06.08 ablation: hybrid raised paraphrase R@1 0.8 → 0.9; re-ranking gave no gain (hybrid+rerank 0.8). Project 06 golden set: identical totals.
- Revisit: with a harder or real query set.

### D-022 · Offline readers that quote instead of a model; explicit multi-query · 2026-10-12
- Decision: offline notebooks and tests answer with `extractive_answer` (IDF-weighted term coverage over retrieved sentences; abstains when too many question terms are unseen). It only copies text, so it never fabricates; it gets 12/16 on the golden set honestly and its limits are shown (06.09). Multi-query is written as an explicit `SearchQueries` structured call, not `MultiQueryRetriever` (community).
- Trade-offs: offline correctness is not model quality; LIVE results are the real measure.

### D-023 · A floor on `langgraph-api` so Chroma can't downgrade the Agent Server · 2026-10-12
- Context: after Module 06, `pip install -e ".[dev,embeddings]"` downgraded langgraph-api 0.16.0 → 0.10.3 and langgraph-runtime-inmem 0.36.0 → 0.30.3, upgraded OpenTelemetry to 1.45.1, and warned `opentelemetry-exporter-prometheus 0.63b1 requires opentelemetry-sdk~=1.42.1`.
- Root cause (reproduced on Python 3.13, fresh and upgrade installs): chromadb 1.5.9 (via langchain-chroma) requires `opentelemetry-exporter-otlp-proto-grpc>=1.2.0` with no upper bound; pip takes the newest (1.45.1, needs `opentelemetry-sdk~=1.45.1`). langgraph-api 0.16.0 requires `opentelemetry-exporter-prometheus>=0.63b1,<0.64`, which needs `opentelemetry-sdk~=1.42.1`. pip resolves the conflict by backtracking the package with no floor, langgraph-api, to 0.10.3 (no prometheus exporter, grpcio 1.80). On upgrades the old prometheus exporter stays behind as an orphan.
- Decision: `[studio]` (in `[dev]`) adds `langgraph-api>=0.16.0,<1`; requirements.txt too. pip then keeps langgraph-api 0.16.0 and picks otlp-proto-grpc 1.42.1. `mastery.doctor.check_dependencies()` (a focused `pip check` + the floor) runs in pytest. Rejected: pinning chromadb/opentelemetry (brittle, every langgraph-api release moves its OpenTelemetry pin) and moving Chroma out of `[dev]` (RAG tests need it offline).
- Evidence: fresh install → langgraph-api 0.16.0, runtime-inmem 0.36.0, grpcio 1.81.1, otel-sdk 1.42.1, chromadb 1.5.9, `pip check` clean; upgrade from the broken state → same, plus two orphans (`opentelemetry-exporter-otlp-common`, `opentelemetry-exporter-http-transport` 0.66b1, nothing requires them) removed by hand; `langgraph dev` serves the Module 02 graph.
- Revisit: when langgraph-api moves to a newer OpenTelemetry (raise the floor with it) or chromadb bounds its exporter.

### D-024 · `mastery.graphs`: one reference pipeline shared by app, tests and solution · 2026-10-12
- Decision: Project 07's graph lives in `mastery/graphs/content.py` (`build_content_graph`). `apps/m07_content_pipeline/pipeline.py` serves it, `tests/unit/test_graphs.py` tests it, and the project notebook rebuilds it node by node (the learner writes `fan_out`, `revise`, the router) and checks node names and scores against the served app. Reusable pieces (`timed`, `loop_router`, reducers, `show_graph`, `DevServer`) sit next to it.
- Trade-offs: the solution and the app could drift; the acceptance check "same node names, same offline scores" catches it.

### D-025 · Offline content models and keyless `langgraph dev` · 2026-10-12
- Decision: `offline_models()` scripts planner, writer and critic (critic: 4 + 2 per fixed issue; writer fixes one issue per revision), so the loop visibly improves (4 → 6 → 8) without a key. The app uses them when `GROQ_API_KEY` is missing or `MASTERY_OFFLINE=1`; notebooks start the server with `MASTERY_OFFLINE=1` by default (no tokens spent by Restart & Run All). Research is BM25 sentence picking over the Module 06 corpus (copies text, never invents).
- Apps live in repo-root `apps/` (CONVENTIONS), Module 02's `studio/` folders stay where they are.

### D-026 · Default recursion limit: teach "measure it", not a number · 2026-10-12
- Context: the docs say the default `recursion_limit` is 1000; langgraph 1.2.14 uses 10007 (`DEFAULT_RECURSION_LIMIT`, overridable with `LANGGRAPH_DEFAULT_RECURSION_LIMIT`), measured on the box.
- Decision: 07.03 prints the installed value and always sets `recursion_limit` explicitly on loops; termination is a counter in state (`loop_router`), the limit is only the safety net.

### D-027 · Read-only SQL helpers instead of `SQLDatabase`/community toolkits · 2026-10-12
- Decision: 07.07 uses `mastery/graphs/sql.py` (~100 lines on `sqlite3`): one `SELECT`/`WITH` statement, `LIMIT` added, file opened with `mode=ro` **and** an authorizer that allows only reads. No `langchain-community` (unmaintained, D-018).
- Trade-offs: SQLite only; production uses a read-only DB role and timeouts (production notes).

### D-028 · Register Pydantic state types for checkpoints · 2026-10-12
- Context: langgraph 1.2.14 warns "Deserializing unregistered type mastery.graphs.state.Outline from checkpoint. This will be blocked in a future version" when Pydantic objects in state are read back from `InMemorySaver`.
- Decision: `memory_checkpointer()` builds `InMemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES))`; notebooks and tests that read history use it. The `langgraph dev` server showed no such warning in its log (verified).
- Revisit: Module 08 (SQLite/Postgres checkpointers need the same serde).
- Update (Module 08): the server claim held for runs without resumes. With an interrupt + resume, `langgraph dev` logged "Deserializing unregistered type" for Pydantic objects in state and has no allow-list setting, so Module 08 stores plain dicts in state (D-030).

### D-029 · `mastery.graphs.hitl`: one approval node, a validation loop, and scripted humans · 2026-10-12
- Context: Lesson 08.03, Project 08 and the app all need approve / edit / reject; keyless notebooks need a "human" that always answers.
- Decision: `approval_node(...)` re-asks inside the node when an answer is invalid (no `try/except` around `interrupt()`, per the docs' rules), returns `Command(goto=...)` (register with `destinations=`), and gives up after `max_rejections`. `drive`/`adrive` + `scripted_reviewer` answer pauses in tests and 🧪 cells; parameter cells (`DECISIONS`) let learners try other branches.
- Revisit: if LangGraph ships a built-in review node for graphs.

### D-030 · Plain dicts in checkpointed state · 2026-10-12
- Context: Pydantic objects in state need an allow-list on every checkpointer (`allowed_msgpack_modules`); unlisted types come back as dicts (blocked) and `langgraph dev`/LangSmith Deployment has no allow-list setting (warning in its log). A `python -m` run also stores `__main__.Plan` instead of the module path.
- Decision: validate with Pydantic in the node, store `model_dump()` in state (`ResearchState.plan: dict`). The course allow-list stays for Module 07's graphs. The CLI re-imports its own module in `__main__` so stored types never point at `__main__`.
- Revisit: when the server exposes a serializer allow-list.

### D-031 · Research subgraph: own schema, called from a node, searches in sequence · 2026-10-12
- Context: measured on langgraph 1.2.14: (1) a subgraph added as a node that shares an `operator.add` key returns the parent's items again (duplicates); (2) a node's `error_handler` does not run when the node fails in the same super-step as a parallel sibling (the exception ends the run); (3) a handler that returns a plain dict ends the run instead of following the node's edges.
- Decision: `research` is an async wrapper node that calls the subgraph with its own schema and returns only new items; `search_docs → search_web` run one after the other; handlers that must continue return `Command(goto=...)` (`search_web` is the subgraph's last node, so a dict is enough there). Lessons 08.02 and 08.05 show the measurements.
- Revisit: re-test (2) on new langgraph releases (Lesson 08.02, exercise 3).

### D-032 · Async nodes + `AsyncSqliteSaver` for anything with a timeout · 2026-10-12
- Context: node timeouts are async-only (a sync node with `timeout=` fails at compile); `SqliteSaver` raises `NotImplementedError` from async calls; `SqliteSaver.prune` raises `NotImplementedError` (3.1.1).
- Decision: `timed` wraps async nodes; `async_sqlite_checkpointer()` for async graphs; `trim_thread()` (keep the newest checkpoint) instead of `prune` for SQLite. Default `durability` stays `"async"` in lessons; the crash CLI uses `"sync"` (08.01 measured that `"async"` lost every step after the input and `"exit"` everything).
- Revisit: when `langgraph-checkpoint-sqlite` implements `prune`.

### D-033 · Offline web stand-in that fails on purpose · 2026-10-12
- Context: retries, timeouts and fallbacks must be visible without a key or network.
- Decision: `offline_web_search(failures=N, delay=S)` returns no results but raises `ConnectionError` for the first N calls or sleeps S seconds; LIVE mode uses Groq browser search through `web_tool_search`. The v3 `stream_events` API is taught as experimental; v2 `stream` is what the helpers use.
- Revisit: Module 12 (failure injection in evals).

<!-- Add your decisions below this line -->
