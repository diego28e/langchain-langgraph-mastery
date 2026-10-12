# Module 05 — MCP & External Tools

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 05](../../COURSE_OUTLINE.md#module-05--mcp--external-tools)

**Goals:** Connect agents to the outside world safely: web search (Groq's built-in browser search by default, Tavily for comparison) and the Model Context Protocol (MCP), using the **built-in `langchain.mcp` namespace** (beta, `langchain[mcp]>=1.4.0`), which replaces the standalone `langchain-mcp-adapters` package.

**Estimated time:** 1–1.5 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 05.01 | Web search: Groq built-in browser search (default) and Tavily | `05-01-web-search-tools.ipynb` | 📝 Planned |
| 05.02 | MCP fundamentals | `05-02-mcp-fundamentals.ipynb` | 📝 Planned |
| 05.03 | Consuming MCP servers with `MCPAdapter` | `05-03-mcp-adapter.ipynb` | 📝 Planned |
| 05.04 | Building your own MCP server with FastMCP | `05-04-build-an-mcp-server.ipynb` | 📝 Planned |
| 05.05 | MCP auth and security | `05-05-mcp-auth-and-security.ipynb` | 📝 Planned |

## Production notes

> ⚠️ **Production note: web search results are untrusted input.**
> Treat every result as data, never as instructions (Lesson 04.05). In production: restrict domains where possible, log which URLs fed each answer, set timeouts and search limits, and keep a fallback search provider. Groq's built-in tools are not available on regional/sovereign endpoints, so check this before promising data residency.

## Project

**Project 05 — Docs-Aware Research Agent over MCP**: An agent that answers LangChain/LangGraph questions by searching the official docs over MCP and the web, with citations.

Project files go in `project/`.

## Jupyter skill

Async in notebooks (top-level `await`).

## `src/mastery` increment

`mastery/mcp.py` (adapter helpers) and `mastery/mcp_servers/`.

## Research checkpoint

Check whether `langchain.mcp` is still beta (look for `LangChainBetaWarning` on the [MCP page](https://docs.langchain.com/oss/python/langchain/mcp/index)) and which MCP features are still "not yet wrapped" on the migration page. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 04](../04-middleware-guardrails-hitl/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 06](../06-rag/) →
