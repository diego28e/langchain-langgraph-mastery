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
