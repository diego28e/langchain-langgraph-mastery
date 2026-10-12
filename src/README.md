# `src/mastery`: the course's reusable package

This package grows module by module. Whenever code is needed in a second notebook, it moves here (with a unit test in `tests/unit/`). By the end of the course, it is a small, production-style toolkit you understand line by line.

> No code yet. The package is created in Module 00 (Lesson 00.04, `config.py`).

## Planned layout

| Module | Path | Purpose |
|---|---|---|
| 00 | `mastery/config.py` | Load `.env`, validate required keys, friendly errors |
| 01 | `mastery/models.py` | `get_model(role, provider)`: model IDs from config, never hard-coded. Includes the paid benchmark (OpenAI by default, Gemini optional) |
| 02 | `mastery/tools/` | Reusable, tested tools |
| 03 | `mastery/memory.py` | Checkpointer and store factories |
| 04 | `mastery/middleware/` | Token budget guard, audit logger, role-based tool filter |
| 05 | `mastery/mcp.py`, `mastery/mcp_servers/`, `mastery/tools/web_search.py` | MCP helpers, the course's FastMCP server, and a web search switch (Groq browser search by default, Tavily optional) |
| 06 | `mastery/rag/` | Loaders, splitter presets, indexing, retrieval, citations |
| 07–08 | `mastery/graphs/` | State schemas, node utilities, HITL helpers |
| 09 | `mastery/agents/` | Specialist agent factories |
| 10 | `mastery/deep/` | `build_deep_agent()` with course defaults (explicit model, `CompositeBackend` layout, deny rules for secrets, limits), `sandboxes/docker.py` (`DockerSandbox`), course `skills/`, trajectory and file-state evaluators |
| 11 | `mastery/voice/` | `transcribe()`, `speak()` (≤ 200-char chunking), `VoicePipeline` |
| 12 | `mastery/evals/` | Shared evaluators and dataset builders |
| 13 | `mastery/service/` | FastAPI app factory, `pydantic-settings` config, API-key auth, SSE helpers (self-hosted with Docker) |

Notebooks import it after an editable install (`pip install -e .`, set up when `pyproject.toml` is added in Module 00) and use `%autoreload 2` (Module 03) while developing.
