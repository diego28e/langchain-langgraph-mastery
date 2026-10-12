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
| `unit/test_notebook_structure.py` | Module 01+ lessons have every template section; title states the docs-verified date; every live model call is guarded by a `HAVE_*_KEY`/`LIVE` flag or marked 🧪 | Notebooks read as JSON |

## Maintainer QA (not part of `pytest`)

Notebooks are executed with **nbclient** twice before release, in memory (outputs never written back):

```bash
cd _maintainer/tools/qa
python run_notebooks.py ../../../modules/01-models-messages-prompts/*.ipynb                 # no keys: 💸 cells must skip
python run_notebooks.py --mock ../../../modules/01-models-messages-prompts/*.ipynb          # live code paths vs a local stand-in
```

`--mock` starts [`mock_groq.py`](../_maintainer/tools/qa/mock_groq.py), a local HTTP server that imitates the Groq API (chat, streaming with reasoning, `json_schema`/tool calls, 401, 429 + `retry-after`, decommissioned models, images, rate-limit headers, job-posting answers with deliberate mistakes) and accepts LangSmith uploads, then points `GROQ_BASE_URL`/`LANGSMITH_ENDPOINT` at it. It proves the code paths run; it says nothing about real model quality.
