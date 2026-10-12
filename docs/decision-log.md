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

<!-- Add your decisions below this line -->
