# `src/mastery`: the course's reusable package

This package grows module by module. Whenever code is needed in a second notebook, it moves here (with a unit test in `tests/unit/`). By the end of the course, it is a small, production-style toolkit you understand line by line.

> **Status:** Modules 00–05 code is in place (`config.py`, `doctor.py`, `groq_catalog.py`, `models.py`, `pricing.py`, `display.py`, `tools/`, `agents.py`, `testing.py`, `memory.py`, `middleware/`, `mcp.py`, `mcp_servers/`, `web_search.py`), with unit tests in [`tests/unit/`](../tests/unit/).

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
| 02 | `mastery/agents.py` | `execute_tool_calls` / `run_tool_loop` (the hand-written loop, tested), `format_transcript`, `agent_stats`, `format_stream_part` (v2 stream parts) |
| 02 | `mastery/testing.py` | `ScriptedChatModel`: offline chat model with `bind_tools` and tool-call streaming, for 🧪 cells and unit tests |
| 03 | `mastery/memory.py` | `make_checkpointer` / `make_store` (in-memory for tests, SQLite in git-ignored `data/outputs/memory/` for notebooks; optional embedding index and TTL), `close`, `thread_config`, `learner_namespace` / `safe_label` (namespace validation), `count_tokens`, offline `HashingEmbeddings`, optional `local_embeddings()` (fastembed, `[embeddings]` extra) |
| 04 | `mastery/middleware/` | `TokenBudgetMiddleware` (run/thread token budget, ends or raises), `AuditLogMiddleware` + `read_audit_log` (redacted JSONL events), `RoleToolFilterMiddleware` + `role_from_context` (hides **and** blocks tools per role, fails closed), `redact_text` / `redact_obj` / `PII_PATTERNS`, `injection_signals` / `INJECTION_PATTERNS`, `fence_untrusted`, `parse_guard_score` (Prompt Guard output, fail closed). Since Module 05, `AuditLogMiddleware` and `RoleToolFilterMiddleware` also have async hooks (MCP agents run with `ainvoke`) |
| 05 | `mastery/mcp.py` | MCP helpers (`langchain.mcp` stays in notebooks; this module doesn't import it): annotations (`is_read_only`, `is_destructive`, `tool_info`), `approval_policy` (HITL `interrupt_on` from annotations + an allow-list, fails closed), citations (`extract_urls`, `urls_from_messages`, `check_sources`), security (`tool_fingerprint`, `poisoned_descriptions`), `serve_http` / `free_port` (a local HTTP MCP server for notebooks and tests) |
| 05 | `mastery/mcp_servers/` | `notes_server.py` (FastMCP: notes tools, resource, prompt, optional bearer tokens + scopes, CLI `python -m mastery.mcp_servers.notes_server`), `docs_standin.py` (offline stand-in for the docs MCP server) |
| 05 | `mastery/web_search.py` | `web_search` tool switch (`MASTERY_WEB_SEARCH`: Groq browser search by default via `.bind`, Tavily optional), `browser_search_model`, `groq_search_sources`, `make_tavily`, `tavily_sources` |
| 06 | `mastery/rag/` | Loaders, splitter presets, indexing, retrieval, citations |
| 07–08 | `mastery/graphs/` | State schemas, node utilities, HITL helpers |
| 09 | `mastery/agents/` | Specialist agent factories |
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
