# Module 05 — MCP & External Tools

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 05](../../COURSE_OUTLINE.md#module-05--mcp--external-tools)

**Goals:** Connect agents to the outside world safely: web search (Groq's built-in browser search by default, Tavily for comparison) and the Model Context Protocol (MCP), using the **built-in `langchain.mcp` namespace** (beta, `langchain[mcp]>=1.4.0`), which replaces the standalone `langchain-mcp-adapters` package.

**Estimated time:** 1–1.5 weeks (about 10–13 hours of lessons plus 5–7 hours for the project).

## Before you start this module

Run this **once**, in **Git Bash**, from the **repo root**, with the **`lc-mastery`** environment active (the prompt starts with `(lc-mastery)`).

```bash
cd ~/path/to/langchain-langgraph-mastery   # your clone; quote the path if it has spaces
conda activate lc-mastery
git pull                                   # get this module's files
python -m pip install -e ".[dev]"          # re-run after every pull: Module 05 adds fastmcp + langchain-tavily (the new [mcp] extra)
python -m pytest -q                        # expect: "... passed" and no failures (offline, no keys; starts local MCP servers on 127.0.0.1)
python -c "import mastery.mcp, mastery.web_search; from mastery.mcp_servers import notes_server; print('mcp ok')"   # expect: mcp ok
python -m mastery.mcp_servers.notes_server --help   # expect: "usage: notes_server.py [-h] [--transport {stdio,http}] ..."
```

| | |
|---|---|
| 🔑 Keys | `GROQ_API_KEY` (optional: without it 💸 cells print `⏭️ Skipped`). **New, optional: `TAVILY_API_KEY`** (free, no card: [app.tavily.com](https://app.tavily.com), 1,000 credits/month) for 05.01 Parts 6–7 and `MASTERY_WEB_SEARCH=tavily` in the project. Add it to `.env` as `TAVILY_API_KEY=tvly-...` and restart the kernel. The LangChain docs MCP server needs **no key** |
| 💰 Cost | $0. Groq free tier (browser search reads pages, so input tokens are higher than a plain chat: ~2–10k per search with `reasoning_effort="low"`). Tavily: 1 credit per basic search |
| 📦 Optional extras | [Node.js LTS](https://nodejs.org/) only if you want the **MCP Inspector** (`npx @modelcontextprotocol/inspector`, 05.02/05.04). VS Code or Cursor to connect the notes server to an IDE (05.04) |
| 🌐 Network | 🌐 cells reach `https://docs.langchain.com/mcp`. Offline or blocked? They print ⚠️ and the lesson continues with the **offline stand-in** (`mastery.mcp_servers.docs_standin`) |
| ✅ Ready when | `pytest` shows no failures, `mcp ok` prints and `--help` shows the usage line |

If `pip install` or `pytest` fails, see the [setup guide's troubleshooting](../00-foundations/00-02-create-course-env.md#troubleshooting) (SSL certificate errors on Anaconda: Step 4b; the same fix applies to `docs.langchain.com` and Tavily).

## How to work through this module

1. **Do [Before you start this module](#before-you-start-this-module) first** (once per pull). Module 05 adds `mastery.mcp` (MCP helpers), `mastery.web_search` (Groq/Tavily `web_search` tool), the FastMCP servers in `mastery/mcp_servers/`, and the benchmark + docs snapshot in `data/samples/mcp/`.
2. **Start Jupyter from the repo root** (`jupyter lab` in Git Bash) and pick the **Python (lc-mastery)** kernel in every notebook.
3. **Async from 05.02 on.** MCP is async: in notebooks you write `await ...` directly in a cell (Jupyter skill below). `asyncio.run()` fails inside Jupyter; that's expected.
4. **Go in order.** 05.01 is web search (no MCP yet); 05.02 explains MCP and looks inside a server; 05.03 consumes servers with `MCPAdapter`; 05.04 builds one; 05.05 secures it. The project combines all of it.
5. **Read the cell markers.** 🧪 = offline (scripted model or local server, free) · 🌐 = network, no tokens · 💸 = calls a model or Tavily. No key? Every 💸 cell prints `⏭️ Skipped`, so **Restart & Run All** always completes.
6. **Windows notes.** Local servers bind to `127.0.0.1` (no firewall prompt). In notebooks we use in-memory and HTTP servers; stdio servers are started from scripts or your IDE (stdio from inside Jupyter can fail on Windows). Notes are UTF-8 files under `data/outputs/m05/` (git-ignored).
7. **Before you commit:** *Kernel → Restart Kernel and Run All Cells…*, *Edit → Clear Outputs of All Cells*, save, then `python -m pytest -q`. Don't commit a personal `.mcp.json` (git-ignored).

## Lessons

| Lesson | Title | Notebook | Time | Keys |
|---|---|---|---|---|
| 05.01 | Web search: Groq built-in browser search (default) and Tavily | [`05-01-web-search-tools.ipynb`](05-01-web-search-tools.ipynb) | 150–180 min | `GROQ_API_KEY`, `TAVILY_API_KEY` (both optional) |
| 05.02 | MCP fundamentals | [`05-02-mcp-fundamentals.ipynb`](05-02-mcp-fundamentals.ipynb) | 90–120 min | none |
| 05.03 | Consuming MCP servers with MCPAdapter | [`05-03-mcp-adapter.ipynb`](05-03-mcp-adapter.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 05.04 | Building your own MCP server with FastMCP | [`05-04-build-an-mcp-server.ipynb`](05-04-build-an-mcp-server.ipynb) | 150–180 min | `GROQ_API_KEY` (optional) |
| 05.05 | MCP auth and security | [`05-05-mcp-auth-and-security.ipynb`](05-05-mcp-auth-and-security.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |

**What each lesson gives you**

- **05.01:** server-side vs client-side tools; Groq `browser_search` attached with `.bind` (not `bind_tools`, D-006), `reasoning_effort="low"`, `tool_choice`; reading sources from `executed_tools`; the **two-step pattern** (search → `with_structured_output`) with invented-URL detection; web search as a normal `web_search` tool next to your own tools; fenced, scanned results; Tavily's raw results and filters; an opt-in 5-question comparison. Why `groq/compound` tutorials fail (shut down 2026-09-21).
- **05.02:** hosts, clients, servers; tools (model), resources (app), prompts (user); top-level `await`; looking inside a server (info, capabilities, annotations); in-memory, Streamable HTTP and stdio transports; the public docs server; `LangChainBetaWarning`.
- **05.03:** `MCPAdapter` with a URL, a server object and an `mcpServers` config (prefixed names); async-only tools (`ainvoke`) and async middleware; content blocks, `artifact`, `status="error"`; an agent over the docs server with grounded citations; caching and per-call sessions.
- **05.04:** a FastMCP server from scratch (tool, resource, prompt), tool design for models, `ToolError` vs `mask_error_details`; a tour of `notes_server.py`; testing in-memory and from an agent; running over stdio/HTTP; a generated **IDE config** (`.mcp.json` for VS Code and Cursor, Windows `python.exe` path); the MCP Inspector (optional).
- **05.05:** bearer tokens and scopes (tools hidden per scope), per-user data; OAuth 2.1 explained (discovery, PKCE, audience-bound tokens, no passthrough); tool poisoning and rug pulls (scan + fingerprint); HITL on side-effecting MCP tools with an allow-list instead of trusting annotations; Groq remote MCP vs client-side MCP.

## Project

**[Project 05 — Docs-Aware Research Agent over MCP](project/README.md)**: an agent that answers LangChain/LangGraph questions from the official docs MCP server and your own FastMCP notes server, with web search for the rest (Groq by default, `MASTERY_WEB_SEARCH=tavily` to switch). Every answer is an `Answer(answer, sources)` whose URLs are checked against tool results; `save_note` waits for a human. Acceptance: ≥8/10 benchmark questions cite the right docs page, 0 invented URLs.

| File | Use |
|---|---|
| [`project/README.md`](project/README.md) | Spec, acceptance criteria, modes, stretch goal |
| [`project/05-project-docs-research-agent.ipynb`](project/05-project-docs-research-agent.ipynb) | **Starter** with four `# TODO`s (runs from day one, also offline) |
| [`project/solutions/05-project-docs-research-agent-solution.ipynb`](project/solutions/05-project-docs-research-agent-solution.ipynb) | **Reference solution** (open after trying) |

## Jupyter skill in this module

**Async in notebooks: top-level `await`** (Lesson 05.02, Part 2; used in every later notebook):

| Skill | Where |
|---|---|
| `await coro()` directly in a cell (Jupyter's loop is already running) | 05.02 |
| Why `asyncio.run()` raises `cannot be called from a running event loop` in Jupyter, and why not to "fix" it with `nest_asyncio` | 05.02 |
| `async with` for sessions (`Client`, `MCPAdapter`) in a cell | 05.02, 05.03 |
| `await agent.ainvoke(...)`: MCP tools have no sync path | 05.03 |
| The same code as a script: `async def main()` + `asyncio.run(main())` (stdio demo) | 05.02 |

## `src/mastery` increment

| File | What it does | Tests |
|---|---|---|
| [`src/mastery/mcp.py`](../../src/mastery/mcp.py) | `is_read_only`, `is_destructive`, `tool_info`, `approval_policy` (HITL from annotations + allow-list), `extract_urls`, `urls_from_messages`, `check_sources`, `tool_fingerprint`, `poisoned_descriptions`, `serve_http` (local HTTP server for notebooks/tests), `free_port` | [`tests/unit/test_mcp.py`](../../tests/unit/test_mcp.py) |
| [`src/mastery/web_search.py`](../../src/mastery/web_search.py) | `browser_search_model` (`.bind`), `groq_search_sources`, `make_tavily`, `tavily_sources`, `make_web_search_tool` (`MASTERY_WEB_SEARCH`), `web_search_backend` | same |
| [`src/mastery/mcp_servers/notes_server.py`](../../src/mastery/mcp_servers/notes_server.py) | FastMCP notes server: `save_note`, `search_notes`, `list_notes`, `delete_note`, `lesson_info`; `notes://{note_id}`; `study_plan`; optional bearer tokens + scopes; CLI (`--transport stdio\|http`) | same |
| [`src/mastery/mcp_servers/docs_standin.py`](../../src/mastery/mcp_servers/docs_standin.py) | Offline stand-in for the docs server (`search_docs_by_lang_chain` over `data/samples/mcp/docs-snapshot.json`) | same |
| [`src/mastery/middleware/audit.py`](../../src/mastery/middleware/audit.py), [`roles.py`](../../src/mastery/middleware/roles.py) | Now also async (`awrap_model_call`, `awrap_tool_call`), so they work in MCP agents | [`tests/unit/test_middleware.py`](../../tests/unit/test_middleware.py), `test_mcp.py` |

## Production notes

> ⚠️ **Production note: web search results are untrusted input.**
> Treat every result as data, never as instructions (Lesson 04.05). In production: restrict domains where possible, log which URLs fed each answer, set timeouts and search limits, and keep a fallback search provider. Groq's built-in tools are not available on regional/sovereign endpoints, so check this before promising data residency.

> ⚠️ **Production note: MCP servers are third-party code and third-party prompts.**
> Review tool descriptions before connecting, pin a fingerprint, require human approval for every tool you haven't verified as read-only, and use per-user, least-privilege credentials.

Each lesson has its own production notes; they are collected in [`docs/production-notes.md`](../../docs/production-notes.md).

## Research checkpoint

Check whether `langchain.mcp` is still beta (05.02 prints the `LangChainBetaWarning`; see the [MCP page](https://docs.langchain.com/oss/python/langchain/mcp/index)) and which MCP features are still "not yet wrapped" on the [migration page](https://docs.langchain.com/oss/python/migrate/langchain-mcp-adapters) (2026-10-12: prompts and resources). Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

✅ Built (docs verified 2026-10-12).

---

← [Module 04](../04-middleware-guardrails-hitl/README.md) · [Course outline](../../COURSE_OUTLINE.md) · [Module 06](../06-rag/README.md) →
