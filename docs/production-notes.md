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
| 00.06, paid benchmark | Free tiers (Groq, Gemini, LangSmith) for everything | No SLA, low rate limits, and different data-use terms (Gemini free tier may use your data). Use paid tiers for user data. See [paid benchmark](paid-benchmark-openai-vs-gemini.md) |
| 05.01 | Web search results go straight into the prompt | Treat results as untrusted input. Restrict domains, log sources, keep a fallback search provider. See [web search](web-search-groq-vs-tavily.md) |
| 00.04 | `.env` files for secrets | Use a secret manager (cloud provider, Docker/Kubernetes secrets) and rotate keys |
| 03, 08 | `InMemorySaver` / SQLite checkpointers | Use a durable database (Postgres checkpointer) with backups |
| 06 | `InMemoryVectorStore`, local Chroma folder | Use a managed or server-mode vector store with backups and access control |
| 07.06 | `langgraph dev` in-memory server | Not a production server. Self-host with FastAPI + Docker (Module 13) or use LangSmith Deployment |
| 13 | Single-container Docker Compose on your laptop | Add a reverse proxy with TLS, health checks, resource limits, log shipping, and a deployment pipeline |
| Module 10 (all lessons) | `deepagents` is **pre-1.0** (0.7.x) with frequent releases and deprecations; some features are **beta** (forked subagents, interpreters/dynamic subagents, `RubricMiddleware`) | Pin the exact version in a lock file, upgrade on a branch behind trajectory evals, fail CI on `deepagents` deprecation warnings, keep beta features behind your own interface |
| Module 10 model stack | Groq free tier (8K tokens/min, 200K tokens/day on `gpt-oss-*`) for deep agents, and a model that is not in the official Deep Agents eval matrix | Paid tier with headroom, a model that passes the official suite **and** your evals, per-run call/token limits, retries, and a tested fallback |
| 10.04, Lab 10A | `FilesystemBackend` / `LocalShellBackend` on your own disk | Development only. In services use `StateBackend`/`StoreBackend` and sandboxes, least-privilege permissions, audit logs |
| 10.07 | Writable memory in a local `InMemoryStore` | Per-user scopes, read-only shared/org memory, reviewed or consolidated writes, durable store (Postgres) |
| 10.09, Lab 10B | Local `DockerSandbox` (shares the host kernel, network on by default) | Managed sandbox or hardened microVMs with egress control, limits, TTLs; never secrets inside a sandbox |
| 10.11 | Managed Deep Agents (public beta) and Deep Agents Code (not supported on Windows) | Optional references only; self-host with Module 13 or use GA LangSmith Deployment |
| Everywhere | Model IDs verified once on a date | Re-verify on a schedule and before each release |

New shortcut in a lesson? Add a callout in the lesson **and** a row here.
