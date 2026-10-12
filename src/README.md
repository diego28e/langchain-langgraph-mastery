# `src/mastery`: the course's reusable package

This package grows module by module. Whenever code is needed in a second notebook, it moves here (with a unit test in `tests/unit/`). By the end of the course, it is a small, production-style toolkit you understand line by line.

> **Status:** Module 00 code is in place (`config.py`, `groq_catalog.py`), with unit tests in [`tests/unit/`](../tests/unit/).

## Install once (Git Bash, course env active, repo root)

```bash
conda activate lc-mastery
python -m pip install -e ".[dev]"      # quotes keep bash from treating [dev] as a pattern
python -c 'import mastery; print(mastery.__version__)'   # expect: 0.1.0
python -m pytest                       # expect: all passed, no network or keys needed
```

Step-by-step with troubleshooting: [Lesson 00.02 guide](../modules/00-foundations/00-02-create-course-env.md).

## Planned layout

| Module | Path | Purpose |
|---|---|---|
| 00 | `mastery/config.py` | Load `.env`, validate required keys, friendly errors, course settings (model IDs) |
| 00 | `mastery/groq_catalog.py` | List live Groq models via the Models API; friendly HTTP errors |
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

Notebooks import it after the editable install above (packaging is defined in [`pyproject.toml`](../pyproject.toml)). If it isn't installed, each notebook's setup cell falls back to `src/` and tells you how to fix it. While editing `src/mastery`, restart the kernel to pick up changes, or use `%autoreload 2` (Module 03).
