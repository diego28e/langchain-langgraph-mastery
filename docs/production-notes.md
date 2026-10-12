# Production Notes: Course Shortcuts and What to Do Instead

> A course has to take shortcuts: free tiers, preview models, local files, one-line setups. Every shortcut in this repo carries a **⚠️ Production note** right where it is used (rule in [CONVENTIONS.md](../CONVENTIONS.md#9-production-notes-every-shortcut-has-one)). This page collects them in one place.
> **Verified on October 11, 2026.**

## Why preview models are not for production

Groq separates **production** models from **preview** models ([Supported models](https://console.groq.com/docs/models), [Deprecations](https://console.groq.com/docs/deprecations)):

- **Production models** "meet or exceed" Groq's standards for speed, quality, and reliability. When one is deprecated, you get a clear migration path and a recommended replacement.
- **Preview models** are "intended for evaluation purposes only and should not be used in production environments". They "may be discontinued at short notice with limited advance warning".

This happens often. In 2026 alone Groq retired `qwen/qwen3-32b`, `qwen/qwen3.6-27b`, `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`, and `groq/compound(-mini)`. Requests to a retired ID **return errors**.

### What to use instead (the general checklist)

1. **Prefer production / GA (generally available) models** for anything users depend on. Check the status column on the provider's model page.
2. **Read the SLA and terms.** Free tiers and preview models usually have no uptime guarantee. If you need one, it comes with a paid or enterprise plan. Know your rate limits ([Groq rate limits](https://console.groq.com/docs/rate-limits)).
3. **Know the deprecation policy** and subscribe to the provider's deprecation notices. Groq announces by email and updates its deprecations page.
4. **Pin model IDs in config, not in code** (`.env` → `mastery/models.py`). Log when and where you verified each ID. Upgrade on purpose after running your eval suite (Module 12), never by surprise.
5. **Have a tested fallback**: a second model or provider wired in with model-fallback middleware (Lesson 04.02), and a test that proves the fallback works.
6. **Monitor**: alert on error rates, `404`/`model_not_found` errors, latency, and cost (Lessons 12.02 and 12.06). Run a canary request against each model ID daily.
7. **Design model-agnostic code**, as Groq's own deprecation guide recommends: keep provider details behind one function.

## Index of shortcuts used in the course

| Where | Shortcut | Production note (short) |
|---|---|---|
| Default model stack, 11.01 | `qwen/qwen3.8-27b` (vision) is a **preview** model | Use a production vision model with an SLA (for example a paid OpenAI/Gemini model) and keep a text-only fallback path |
| 04.04–04.05 | `openai/gpt-oss-safeguard-20b` and `meta-llama/llama-prompt-guard-2-*` are **preview** classifiers | Never rely on one classifier. Layer rules + classifier + human review. Fail closed when the classifier is unavailable |
| 11.03, Project 11 | Orpheus TTS `canopylabs/orpheus-v1-english` is **preview**, 200 characters per request, WAV only | Use a GA TTS model with an SLA, keep a "text only" fallback, cache generated audio, and monitor per-character cost |
| 00.06, paid benchmark, Module 10 | Free tiers (Groq, Gemini, LangSmith) for everything | No SLA, low rate limits, and different data-use terms (Gemini free tier may use your data). Use paid tiers for user data. See [paid benchmark](paid-benchmark-openai-vs-gemini.md) |
| 05.01 | Web search results go straight into the prompt | Treat results as untrusted input. Restrict domains, log sources, keep a fallback search provider. See [web search](web-search-groq-vs-tavily.md) |
| 00.04 | `.env` files for secrets | Use a secret manager (cloud provider, Docker/Kubernetes secrets) and rotate keys |
| 00.02 | Hand-built conda env (`lc-mastery`) and a laptop as the runtime | Reproducible, locked environments (lock file or container image) built by CI; the laptop is never the deployment target (Module 13) |
| 00.03 | Notebooks as the place where code runs | Move reusable code into a tested package (`src/mastery`) and run services, not notebooks, in production |
| 00.04 | `getpass()` to type a key into a session | Interactive only. Services read keys from a secret manager or injected environment variables |
| 00.05 | Scraping docs pages and hand-curated deprecation lists | Use official APIs (Models API, PyPI JSON) and subscribe to provider deprecation/changelog feeds; automate checks in CI |
| 00.06 | Hand-copied price table | Track real spend from provider usage dashboards/billing APIs and per-request token usage (Lesson 13.02) |
| 00.07 | One model, no fallback; errors only reported | Pinned model ID in config, tested fallback model (Lesson 04.02), retries with backoff respecting `retry-after` (Lessons 01.06, 13.02), alerting on 4xx/5xx rates |
| 00.07 | Checking model availability by opening a notebook | Scheduled job or CI check that compares configured IDs with the live Models API (`tests/integration/test_groq_live.py` is a first version) |
| Project 00 | Three prompts, one run per model, as a "comparison"; offline sample JSON | Versioned evaluation datasets, repeated runs, automatic evaluators (Module 12); availability decisions only from the live API |
| 01.01 | Trusting integration defaults (`ChatGroq`: temperature 0.7, `max_retries=2`, no timeout) | Set `timeout`, `max_retries`, `temperature` explicitly in one config module; log them as trace metadata; re-check defaults on every integration upgrade |
| 01.01, 01.02 | `get_model("vision")` returns a **preview** model (`PreviewModelWarning`) | GA model with an SLA for user-facing features, a tested fallback (Lesson 04.02), watch the deprecations page |
| 01.02 | Base64 images inline in requests | Resize first, prefer provider file storage/URLs for repeated images, validate MIME type and size, process only images users consented to |
| 01.02 | Whole conversations saved to JSON files | Store only what you need, encrypt at rest, set retention, redact PII before logging, record model + prompt version per `AIMessage` |
| 01.03 | User text pasted into prompts with only delimiters | Length limits, escape delimiter tags in user text, allow-list the output, log suspicious inputs, guardrails (Module 04) |
| 01.03, Project 01 | Prompts and models judged on 10–12 examples, one run, one annotator | Labelled datasets that reflect real traffic, repeated runs, experiments tracked in LangSmith (Module 12), accuracy reported with uncertainty |
| 01.03 | Prompts as Python constants in notebooks | Versioned, reviewed prompt artifacts (Git or LangSmith prompt hub); log the prompt version in trace metadata |
| 01.04 | Schema-valid output treated as "done" | Measure field-level accuracy, monitor parse-failure rate per model/prompt version, route invalid results to a human or fallback |
| 01.04 | Reading a private constant (`_STRICT_STRUCTURED_OUTPUT_MODELS`) to learn behavior | Never import private names in application code; re-test the behavior on upgrades |
| 01.05 | Streaming to a notebook with `display(..., display_id=True)` | Stream to clients over SSE/WebSockets (Module 13), stop generating on disconnect, sanitize Markdown before rendering HTML |
| 01.05 | `asyncio.gather` / `batch` with only a concurrency cap | Bound concurrency **and** rate, per-request timeouts, cancel remaining tasks when the caller gives up |
| 01.06, Project 01 | `InMemoryRateLimiter` (per process, requests only) | Shared limiter (e.g. Redis) across workers, limit tokens as well as requests, adapt to `x-ratelimit-*` headers, queue instead of failing |
| 01.06, Project 01 | Costs estimated from `mastery.pricing` (hand-maintained, list prices) | Reconcile with provider billing, track cost per feature/customer via trace metadata (LangSmith cost tracking), budget alerts |
| 01.07 | Silent `with_fallbacks` | Emit a metric/tag when a fallback fires, alert on its rate, test the fallback path, validate the backup's output too |
| 01.07 | Anonymous lambdas inside LCEL pipelines | Named, documented, unit-tested functions; `.with_config(run_name=...)` so traces are readable |
| 01.08 | Tracing full prompts/outputs to LangSmith (free plan, 180-day retention) | Mask or hide PII (`LANGSMITH_HIDE_INPUTS`/anonymizers), one project per environment, sample high-volume traffic, flush tracers on shutdown |
| Project 01 | OFFLINE DEMO mode: stand-in "models" built from the answer key | Demo numbers are never evidence. Decisions come from live runs on a representative dataset |
| 02.01, 02.04 | Tools over a local CSV and in-memory data, no authentication | Tools call services with per-user, least-privilege credentials; identity and tenant come from `runtime.context` set by the server, never from model arguments; permission checks in the tool or a `wrap_tool_call` middleware, with a test that asks for another user's data |
| 02.01 | `calculator` evaluates model-written expressions (AST allow-list) | Never `eval`/`exec`/shell model output. Keep allow-lists, size limits and timeouts; prefer purpose-built tools (`sum_by_category`) over a general evaluator |
| 02.02 | `ChatGroq` only | Keep a tested OpenAI-compatible fallback (`ChatOpenAI(base_url="https://api.groq.com/openai/v1")`) with a CI smoke test, for when `langchain-groq` lags the Groq API or its SDK pin (`groq<1`) blocks an upgrade. It loses Groq-specific parsing (reasoning, `executed_tools`) |
| 02.02 | Groq built-in `browser_search` sent with `.bind(tools=[...])` because `bind_tools` rejects it | Queries go to Groq and its search partner; no filtering of pages before the model reads them; not on regional endpoints. Log queries, treat answers as untrusted, keep a client-side search tool (Tavily, Module 05) as fallback |
| 02.03 | Framework default recursion limit (1000 in the docs; 9,999 measured with langgraph 1.2.14) | `recursion_limit` on every call plus `ModelCallLimitMiddleware`/`ToolCallLimitMiddleware`; alert on steps per run |
| 02.04 | Unexpected tool exceptions propagate (default); `str(exc)` as error text in demos | `ToolErrorMiddleware` with an allow-list of exception types and fixed, sanitized messages; full exception logged server-side with a request id |
| 02.05 | `ToolStrategy` chosen by hand because auto picks `ProviderStrategy` on Groq (JSON schema + tools unsupported) | Always explicit strategies; re-test after upgrades (model profiles change); monitor validation-retry rate; version answer schemas |
| 02.06 | `stream_events(version="v3")` is **experimental** in langgraph 1.2.14 | Production streaming on `stream(..., version="v2")` until v3 is stable; allow-list which nodes/events reach clients |
| 02.07, Project 02 | `langgraph dev` + Studio with tracing on, on sample data | Development only. Real user data: `LANGSMITH_TRACING=false` or redaction (Module 04); deployments use a persistent Agent Server or the Module 13 service |
| Project 02 | Static, illustrative FX rates; synthetic expenses; OFFLINE DEMO stand-in models | Dated rates from a trusted source with the `as_of` shown to users; real evaluation on representative data; demo scores are never evidence |
| 03, 08 | `InMemorySaver` / SQLite checkpointers | Use a durable database (Postgres checkpointer) with backups |
| 03.01, 03.02 | Thread ids like `"ana-s1"` chosen in code; conversations kept forever | Server-generated thread ids (`uuid4`) stored with their owner and checked on every request; retention (`prune`, `delete_thread`), `EncryptedSerializer` at rest |
| 03.02, Project 03 | SQLite checkpointer and store files in `data/outputs/memory/` (one process) | Postgres checkpointer/store (Module 13) or LangSmith Deployment persistence; backups; one database per environment |
| 03.03 | `count_tokens_approximately` (≈4 chars/token) as the token budget | Reconcile with provider `usage_metadata`, keep a margin below input **and** tokens-per-minute limits, cap tool output size |
| 03.03, Project 03 | Summaries written by a small model and trusted as memory | Keep identity, permissions and key facts out of summaries (context/store); log summaries for audit; evaluate summary quality (Module 12) |
| 03.04, Project 03 | Model-written memories (`remember_fact`) re-injected into prompts | Length caps, typed `kind`, never store instructions, mark memories as data, user-visible "what you remember" + delete, TTLs, write audit log |
| 03.04 | `HashingEmbeddings` (word overlap) in demos; one local fastembed model | A real embedding model chosen by evaluation; record model + dims with the store and re-embed on change; pgvector in production |
| 03.05 | Tools hidden from the model with `wrap_model_call` | Hiding is not authorization: enforce permissions in the tool or `wrap_tool_call` too |
| 04.02 | Prebuilt retry/fallback/limit middleware with demo thresholds | Tune limits from real traffic; alert when fallbacks or limits fire; fallback to a different provider, not only a smaller model |
| 04.03 | `AuditLogMiddleware` writing local JSONL; `TokenBudgetMiddleware` estimating tokens | Ship audit events to an append-only store with retention and access control; reconcile budgets with provider `usage_metadata` and billing |
| 04.03 | Role taken from `runtime.context` set in the notebook | Roles come from your auth system, never from the model or the user's text |
| 04.04 | Regex PII detectors (`PIIMiddleware`, `redact_text`) | Dedicated PII detection (e.g. Presidio or a provider service) tuned per locale; test on real-shaped data; redact before logging **and** before tracing |
| 04.04–04.05 | Groq **Preview** safety models (`gpt-oss-safeguard-20b`, `llama-prompt-guard-2-86m`) | Never the only defence; fail closed; pin, monitor and keep a fallback classifier (see the lesson notes) |
| 04.05 | Regex injection scanner measured on 20 rows | Layered defences, a much larger labelled set, red-teaming, and monitoring of `injection_blocked` rates |
| 04.06, Project 04 | `InMemorySaver`/SQLite for pending approvals; a code `review()` policy as the "human" | Durable checkpointer shared by workers; a real review UI showing exact arguments; reviewer identity, timeouts that reject, and an audit trail |
| Project 04 | Outbox = files in `data/outputs/m04/outbox/` | Real sending through a provider API behind the same approval gate, with rate limits and an allow-list |
| 06 | `InMemoryVectorStore`, local Chroma folder | Use a managed or server-mode vector store with backups and access control |
| 07.06 | `langgraph dev` in-memory server | Not a production server. Self-host with FastAPI + Docker (Module 13) or use LangSmith Deployment |
| 13 | Single-container Docker Compose on your laptop | Add a reverse proxy with TLS, health checks, resource limits, log shipping, and a deployment pipeline |
| Module 10 (all lessons) | `deepagents` is **pre-1.0** (0.7.x) with frequent releases and deprecations; some features are **beta** (forked subagents, interpreters/dynamic subagents, `RubricMiddleware`) | Pin the exact version in a lock file, upgrade on a branch behind trajectory evals, fail CI on `deepagents` deprecation warnings, keep beta features behind your own interface |
| Module 10 model stack (default) | **Gemini free tier** (`google_genai:gemini-3.6-flash`) for every deep agent and subagent. Unpaid quota: Google may use prompts and responses to improve its products and **human reviewers may read them**; free-tier limits are per project and per model, shown only in AI Studio, and "not guaranteed" | Paid tier (paid usage is not used to improve Google products); public/synthetic data only while learning; pin the exact stable ID (`gemini-3.6-flash`, no `-latest` aliases), watch the [deprecations page](https://ai.google.dev/gemini-api/docs/deprecations) (Google calls it its "previous generation" Flash); budget for the price doubling on 2027-01-01 ($0.75/$3.75 → $1.50/$7.50 per 1M); retry on `429 RESOURCE_EXHAUSTED`; per-run call/token limits; a tested fallback model ([terms](https://ai.google.dev/gemini-api/terms), [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [pricing](https://ai.google.dev/gemini-api/docs/pricing)) |
| Module 10 model stack (Groq option) | Groq free tier (8K tokens/min, 200K tokens/day on `gpt-oss-*`), and models that are not in the official Deep Agents eval matrix | Paid tier with headroom, a model that passes the official suite **and** your evals, per-run call/token limits, retries, and a tested fallback |
| 10.04, Lab 10A | `FilesystemBackend` / `LocalShellBackend` on your own disk | Development only. In services use `StateBackend`/`StoreBackend` and sandboxes, least-privilege permissions, audit logs |
| 10.07 | Writable memory in a local `InMemoryStore` | Per-user scopes, read-only shared/org memory, reviewed or consolidated writes, durable store (Postgres) |
| 10.09, Lab 10B | Local `DockerSandbox` (shares the host kernel, network on by default) | Managed sandbox or hardened microVMs with egress control, limits, TTLs; never secrets inside a sandbox |
| 10.11 | Managed Deep Agents (public beta) and Deep Agents Code (not supported on Windows) | Optional references only; self-host with Module 13 or use GA LangSmith Deployment |
| 00.02, Step 4b | `SSL_CERT_FILE` pinned to conda's public CA bundle with `conda env config vars` | Corporate proxies that inspect TLS need the company's root CA: build one bundle (public + corporate CA), point `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` at it in the deployment config (or pass `http_client=httpx.Client(verify=...)`), never disable verification (`verify=False`), and fail fast at startup if the file is missing (as `mastery.doctor` does) |
| Everywhere | Model IDs verified once on a date | Re-verify on a schedule and before each release |

New shortcut in a lesson? Add a callout in the lesson **and** a row here.
