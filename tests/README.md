# Tests

| Folder | What | Network / keys | When it runs |
|---|---|---|---|
| `tests/unit/` | Tests for `src/mastery` using fake chat models and in-memory persistence | None | Every commit (locally) and in CI |
| `tests/integration/` | Real model/API calls. Assert on structure, not exact text | Needs `.env` keys | Manually: `pytest -m integration` |

Introduced in Module 12 (see [Unit testing](https://docs.langchain.com/oss/python/langchain/test/unit-testing) and [Integration testing](https://docs.langchain.com/oss/python/langchain/test/integration-testing)). Unit tests may appear earlier, as soon as code moves into `src/mastery`.
