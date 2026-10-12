# Tests

| Folder | What | Network / keys | When it runs |
|---|---|---|---|
| `tests/unit/` | Tests for `src/mastery` using fake chat models and in-memory persistence | None | Every commit (locally) and in CI |
| `tests/integration/` | Real model/API calls. Assert on structure, not exact text | Needs `.env` keys | Manually: `python -m pytest -m integration` |

Introduced in Module 12 (see [Unit testing](https://docs.langchain.com/oss/python/langchain/test/unit-testing) and [Integration testing](https://docs.langchain.com/oss/python/langchain/test/integration-testing)). Unit tests may appear earlier, as soon as code moves into `src/mastery`.

## Running the tests (Git Bash, course env active, repo root)

```bash
python -m pytest            # unit tests only (the default, see [tool.pytest.ini_options] in pyproject.toml)
python -m pytest -v         # one line per test
python -m pytest -m integration   # live Groq calls; needs GROQ_API_KEY in .env
```

Module 00 adds: `unit/test_config.py`, `unit/test_groq_catalog.py` (HTTP faked with `httpx.MockTransport`), `unit/test_notebook_hygiene.py` (every notebook under `modules/` is valid and has no saved outputs), and `integration/test_groq_live.py`.

Module 01 adds (all offline):

| File | Tests | How it stays offline |
|---|---|---|
| `conftest.py` | `isolated_env` fixture: removes every course variable (`GROQ_API_KEY`, `MASTERY_*`, `LANGSMITH_*`, ...) for one test | `monkeypatch` |
| `unit/test_models.py` | `get_model` roles/providers, key checks, `PreviewModelWarning`, missing-package hint, `explain_model_error` for SDK-style and `langchain_core` errors (401, 404, 429 + `retry-after`, 498, 5xx, timeouts) | Models are constructed, never invoked; fake exception classes |
| `unit/test_doctor.py` | Bad `SSL_CERT_FILE` gives `CertificateSettingError` with the fix, from `get_model` and `load_settings` | `monkeypatch` sets a non-existent path; offline. `conftest.py` also prints an SSL warning in the pytest header |
| `unit/test_pricing.py` | Price lookup (`provider:model` and bare IDs), `estimate_cost`, `cost_report` | Pure functions |
| `unit/test_display.py` | `message_summary`, HTML rendering, escaping of model output | `AIMessage` objects built by hand |
| `unit/test_tools.py` | `safe_eval` allow-list and limits, `calculator` errors as `ToolMessage`s, date tools (fixed "today"), `CsvTable` (BOM, row cap) and `make_csv_lookup_tool` (column enum, artifact, caps) | Pure functions and a temporary CSV |
| `unit/test_agents.py` | `ScriptedChatModel` (script, callables, streaming tool calls, `repeat_last`), `execute_tool_calls` error paths, `run_tool_loop` limits, transcript/stream formatting, `create_agent` end to end | `ScriptedChatModel`: no network |
| `unit/test_notebook_structure.py` | Module 01+ lessons have every template section; title states the docs-verified date; every live model call is guarded by a `HAVE_*_KEY`/`LIVE` flag or marked 🧪 | Notebooks read as JSON |

Module 03 adds (all offline):

| File | Tests | How it stays offline |
|---|---|---|
| `unit/test_memory.py` | `thread_config`, `memory_dir`; in-memory checkpointer keeps threads apart; **SQLite checkpointer read back from a new Python process**; `make_store` (memory and SQLite) put/get/prefix search and semantic search with an index; SQLite store reopened; TTL arg rules; `safe_label` / `learner_namespace` reject unsafe ids; `HashingEmbeddings` stable and normalised; `count_tokens`; a `create_agent` tool writing to `runtime.store` with users kept apart | `tmp_path` SQLite files, `ScriptedChatModel`, `HashingEmbeddings` (no model download) |

Module 04 adds (all offline):

| File | Tests | How it stays offline |
|---|---|---|
| `unit/test_middleware.py` | Redaction (email, card, IP, phone, API keys; nested objects); injection signals and `fence_untrusted` (fake end markers neutralised); `parse_guard_score` (numbers, labels, garbage → `None`); `TokenBudgetMiddleware` ends a run / raises / counts per thread; `RoleToolFilterMiddleware` hides tools, blocks forbidden calls, fails closed for unknown roles; `AuditLogMiddleware` writes redacted JSONL for model and tool calls and errors | `ScriptedChatModel` agents, `tmp_path` files |

Module 05 adds (all offline; MCP servers run in-memory or on `127.0.0.1`):

| File | Tests | How it stays offline |
|---|---|---|
| `unit/test_mcp.py` | Notes server: tools and annotations, save/search/delete round trip, limits and errors, `lesson_info`, resource and prompt, `tokens_from_env`; **over HTTP** (`serve_http`): bearer tokens, tools hidden without scope, per-user notes; docs stand-in format and every benchmark page in the snapshot; URL extraction (incl. JSON-escaped newlines) and `check_sources`; `urls_from_messages` (tool results, Groq `executed_tools`, skipping the `ToolStrategy` echo); poisoned descriptions and fingerprints; `approval_policy` with the allow-list; async agents over MCP tools with Module 04 middleware (sync `invoke` raises); `web_search` backend switch, Groq sources via `ScriptedChatModel`, Tavily via a fake engine | FastMCP in-memory servers, a local HTTP child process on a free port, `ScriptedChatModel`, saved docs snapshot |

## Maintainer QA (not part of `pytest`)

Notebooks are executed with **nbclient** twice before release, in memory (outputs never written back):

```bash
cd _maintainer/tools/qa
python run_notebooks.py ../../../modules/01-models-messages-prompts/*.ipynb                 # no keys: 💸 cells must skip
python run_notebooks.py --mock ../../../modules/01-models-messages-prompts/*.ipynb          # live code paths vs a local stand-in
python run_notebooks.py --mock ../../../modules/02-tools-and-agents/*.ipynb ../../../modules/02-tools-and-agents/project/*.ipynb ../../../modules/02-tools-and-agents/project/solutions/*.ipynb
python run_notebooks.py --mock ../../../modules/03-memory-and-context/*.ipynb ../../../modules/03-memory-and-context/project/*.ipynb ../../../modules/03-memory-and-context/project/solutions/*.ipynb
python run_notebooks.py --mock ../../../modules/04-middleware-guardrails-hitl/*.ipynb ../../../modules/04-middleware-guardrails-hitl/project/*.ipynb ../../../modules/04-middleware-guardrails-hitl/project/solutions/*.ipynb
python run_notebooks.py --mock ../../../modules/05-mcp-and-external-tools/*.ipynb ../../../modules/05-mcp-and-external-tools/project/*.ipynb ../../../modules/05-mcp-and-external-tools/project/solutions/*.ipynb
```

Module 03 notebooks write SQLite files under `data/outputs/memory/`, Module 04 writes outboxes, audit logs and a SQLite file under `data/outputs/m04/`, Module 05 writes notes, an IDE config example and an audit log under `data/outputs/m05/` (all git-ignored); delete those folders after QA runs. The mock also answers the two Groq safety models (Prompt Guard: a score; safeguard: a JSON verdict) and records LangSmith upload bodies (`LANGSMITH_BODIES`) so redaction can be checked.

`--mock` starts [`mock_groq.py`](../_maintainer/tools/qa/mock_groq.py), a local HTTP server that imitates the Groq API (chat, streaming with reasoning, `json_schema`/tool calls, 401, 429 + `retry-after`, decommissioned models, images, rate-limit headers, job-posting answers with deliberate mistakes; since Module 02 an **agent mode** that picks a tool from the question, fills arguments, makes one call per turn and answers `ToolStrategy` schemas from tool results; a 400 for `json_schema` + tools, as Groq documents; built-in `browser_search` with `executed_tools` incl. `search_results` URLs; since Module 05 a **Tavily** stand-in at `/tavily/search`, enabled with `TAVILY_BASE_URL` and a mock `tvly-` key) and accepts LangSmith uploads, then points `GROQ_BASE_URL`/`LANGSMITH_ENDPOINT` at it. It proves the code paths run; it says nothing about real model quality.
