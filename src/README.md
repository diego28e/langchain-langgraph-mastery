# `src/mastery`: the course's reusable package

This package grows module by module. Whenever code is needed in a second notebook, it moves here (with a unit test in `tests/unit/`). By the end of the course, it is a small, production-style toolkit you understand line by line.

> **Status:** Modules 00–05 code is in place (`config.py`, `doctor.py`, `groq_catalog.py`, `models.py`, `pricing.py`, `display.py`, `tools/`, `agents/`, `testing.py`, `memory.py`, `middleware/`, `mcp.py`, `mcp_servers/`, `web_search.py`), with unit tests in [`tests/unit/`](../tests/unit/).

## Install once (Git Bash, course env active, repo root)

```bash
conda activate lc-mastery
python -m pip install -e ".[dev]"      # quotes keep bash from treating [dev] as a pattern
                                       # [dev] includes [llm] (LangChain packages) from Module 01 on
python -c 'import mastery; print(mastery.__version__)'   # expect: 0.1.0
python -m pytest                       # expect: all passed, no network or keys needed
```

Step-by-step with troubleshooting: [Lesson 00.02 guide](../modules/00-foundations/00-02-create-course-env.md).

## Planned layout

| Module | Path | Purpose |
|---|---|---|
| 00 | `mastery/config.py` | Load `.env`, validate required keys, friendly errors, course settings (model IDs) |
| 00 | `mastery/doctor.py` | `check_ssl_env()` / `require_valid_ssl_env()`: a missing `SSL_CERT_FILE`/`SSL_CERT_DIR` raises `CertificateSettingError` with the fix (called by `load_settings` and `get_model`; Lesson 00.02, Step 4b) |
| 00 | `mastery/groq_catalog.py` | List live Groq models via the Models API; friendly HTTP errors |
| 01 | `mastery/models.py` | `get_model(role, provider)`: model IDs from config, never hard-coded; `provider="benchmark"` for the paid benchmark (OpenAI by default, Gemini optional). `PreviewModelWarning`, `explain_model_error()` (one classifier for SDK and `langchain_core` exceptions), `describe_model()` |
| 01 | `mastery/pricing.py` | Dated price table and `estimate_cost()` / `cost_report()` from `usage_metadata` |
| 01 | `mastery/display.py` | Safe (HTML-escaped) message cards for Jupyter: `show_message()`, testable `render_message_html()` |
| 02 | `mastery/tools/` | Reusable, tested tools: `calculator` (AST allow-list, no `eval`), date tools (`get_today`, `days_between`, `add_days`), `make_csv_lookup_tool` for one CSV file |
| 02 | `mastery/agents/loop.py` (was `agents.py` until Module 09; still imported as `mastery.agents`) | `execute_tool_calls` / `run_tool_loop` (the hand-written loop, tested), `format_transcript`, `agent_stats`, `format_stream_part` (v2 stream parts) |
| 02 | `mastery/testing.py` | `ScriptedChatModel`: offline chat model with `bind_tools` and tool-call streaming, for 🧪 cells and unit tests |
| 03 | `mastery/memory.py` | `make_checkpointer` / `make_store` (in-memory for tests, SQLite in git-ignored `data/outputs/memory/` for notebooks; optional embedding index and TTL), `close`, `thread_config`, `learner_namespace` / `safe_label` (namespace validation), `count_tokens`, offline `HashingEmbeddings`, optional `local_embeddings()` (fastembed, `[embeddings]` extra) |
| 04 | `mastery/middleware/` | `TokenBudgetMiddleware` (run/thread token budget, ends or raises), `AuditLogMiddleware` + `read_audit_log` (redacted JSONL events), `RoleToolFilterMiddleware` + `role_from_context` (hides **and** blocks tools per role, fails closed), `redact_text` / `redact_obj` / `PII_PATTERNS`, `injection_signals` / `INJECTION_PATTERNS`, `fence_untrusted`, `parse_guard_score` (Prompt Guard output, fail closed). Since Module 05, `AuditLogMiddleware` and `RoleToolFilterMiddleware` also have async hooks (MCP agents run with `ainvoke`) |
| 05 | `mastery/mcp.py` | MCP helpers (`langchain.mcp` stays in notebooks; this module doesn't import it): annotations (`is_read_only`, `is_destructive`, `tool_info`), `approval_policy` (HITL `interrupt_on` from annotations + an allow-list, fails closed), citations (`extract_urls`, `urls_from_messages`, `check_sources`), security (`tool_fingerprint`, `poisoned_descriptions`), `serve_http` / `free_port` (a local HTTP MCP server for notebooks and tests) |
| 05 | `mastery/mcp_servers/` | `notes_server.py` (FastMCP: notes tools, resource, prompt, optional bearer tokens + scopes, CLI `python -m mastery.mcp_servers.notes_server`), `docs_standin.py` (offline stand-in for the docs MCP server) |
| 05 | `mastery/web_search.py` | `web_search` tool switch (`MASTERY_WEB_SEARCH`: Groq browser search by default via `.bind`, Tavily optional), `browser_search_model`, `groq_search_sources`, `make_tavily`, `tavily_sources` |
| 06 | `mastery/rag/` | `loaders.py` (`load_markdown`, `load_pdf` with 1-based pages via pypdf, `load_html` via BeautifulSoup without nav/scripts, `load_corpus`), `splitters.py` (`split_documents` presets `recursive` / `markdown` / `tokens`, stable `chunk_id`, `chunk_stats`), `index.py` (`default_embeddings` fastembed → Hashing fallback, `CachedEmbeddings` SQLite cache, `build_index` memory/Chroma cosine with upserts, `open_chroma`, `reset_chroma`), `retrieve.py` (`retrieve` with scores, pure-Python `BM25`, `rrf`, `hybrid_search`, `OverlapReranker`, `cross_encoder_reranker`, `make_retriever_tool` with document artifacts), `citations.py` (`Citation`, `CitedAnswer`, `format_context` / `parse_context`, `verify_citations`, `NOT_FOUND`, offline `extractive_reader` / `extractive_agent_reader`), `eval.py` (`recall_at_k`, `mrr`, `evaluate_retrieval`) |
| 07 | `mastery/graphs/` | `state.py` (reducers `merge_dicts`, `append_unique`, `keep_last`; `Outline`/`Critique`/`SectionPlan`; `ContentState`; `memory_checkpointer` that allows these models in checkpoints), `nodes.py` (`timed` per-node latency into `run_log`, `loop_router` with a hard stop, `stream_updates`, `run_summary`, `mermaid_markdown`, `show_graph` PNG → Mermaid fallback), `content.py` (Project 07 reference graph `build_content_graph`, prompts, `offline_models`, `corpus_researcher`, `web_researcher`, `TEST_TOPICS`), `sql.py` (read-only SQLite helpers: `sqlite_from_csv`, `list_tables`, `table_schema`, `check_sql`, `run_readonly_query`), `server.py` (`DevServer`: start/stop `langgraph dev` from a notebook). `doctor.check_dependencies` checks the installed stack's requirements |
| 08 | `mastery/graphs/` | `hitl.py` (`approval_node`: approve / edit / reject with a validation loop and a give-up limit, returns `Command`; `parse_decision`; `run_until_pause` / `resume` / `drive` and async versions; `scripted_reviewer`), `persistence.py` (`sqlite_checkpointer`, `async_sqlite_checkpointer` with the course allow-list, `checkpoint_rows`, `count_checkpoints`, `trim_thread`, `file_size`), `stores.py` (`check_store_contract`), `research.py` (Project 08 reference graph `build_research_graph` with clarify/approval interrupts, a research subgraph with retry + timeout + error handler, store preferences; `corpus_docs_search`, `retriever_docs_search`, `offline_web_search`, `web_tool_search`, `offline_models`, the crash CLI and `run_and_kill`). `nodes.timed` also wraps `async def` nodes |
| 09 | `mastery/agents/` | `metrics.py` (`UsageMeter`: model calls and tokens per agent via `lc_agent_name`), `specialists.py` (`Specialist`, `subagent_tool` with `context` query/history and `output` last/all, `task_tool`, `handoff_tool` + `handoff_graph` (`Command.PARENT`, `carry="turn"`), `step_tool` + `step_middleware` for one-agent handoffs), `support.py` (Project 09 desk: `SupportDesk`, `make_support_tools` with the refund interrupt, `faq_search`, prompts, `make_specialists`, reference builders for single agent / handoffs / subagents / router / skills / custom refund workflow, `OfflineSupportModel`, `run_conversation`, `score`, `evaluate`) |
| 10 | `mastery/deep/` | `build_deep_agent()` with course defaults (explicit model, `CompositeBackend` layout, deny rules for secrets, limits), `sandboxes/docker.py` (`DockerSandbox`), course `skills/`, trajectory and file-state evaluators |
| 11 | `mastery/voice/` | `transcribe()`, `speak()` (≤ 200-char chunking), `VoicePipeline` |
| 12 | `mastery/evals/` | Shared evaluators and dataset builders |
| 13 | `mastery/service/` | FastAPI app factory, `pydantic-settings` config, API-key auth, SSE helpers (self-hosted with Docker) |

Notebooks import it after the editable install above (packaging is defined in [`pyproject.toml`](../pyproject.toml)). If it isn't installed, each notebook's setup cell falls back to `src/` and tells you how to fix it. While editing `src/mastery`, restart the kernel to pick up changes, or use `%autoreload 2` (Module 03).

## Optional dependencies (extras)

| Extra | Installs | Why separate |
|---|---|---|
| (none) | `python-dotenv`, `httpx` | Enough for Module 00 (`config`, `groq_catalog`) |
| `[llm]` | `langchain`, `langchain-core`, `langchain-groq` | `models`, `pricing`, `display` import LangChain **lazily**, so `import mastery` works without it |
| `[studio]` | `langgraph-cli[inmem]` | `langgraph dev` for LangSmith Studio (Lesson 02.07); pulls the local Agent Server (Python ≥ 3.11) |
| `[dev]` | `pytest`, `nbformat`, `nbconvert` + `[llm]` + `[studio]` | Every unit test runs, offline; notebook tooling; `langgraph dev` |

Other providers are installed only when you use them: `python -m pip install "langchain-openai>=1.7.0,<2"` (paid benchmark) or `"langchain-google-genai>=4.4.1,<5"`. `get_model()` tells you the exact command if one is missing.

## Example (Module 01)

```python
from mastery.models import get_model, explain_model_error
from mastery.pricing import estimate_cost

llm = get_model("fast", temperature=0, max_tokens=300)        # groq:<MASTERY_MODEL_FAST>
try:
    reply = llm.invoke("Say hi in five words.")
    print(reply.text, estimate_cost(reply.usage_metadata, "groq:openai/gpt-oss-20b"))
except Exception as error:
    info = explain_model_error(error)          # kind, retryable, status_code, retry_after, hint
    print(info.kind, info.hint)
```
