# Project 05 — Docs-Aware Research Agent over MCP

> **Module 05 · MCP & External Tools** · ⏱️ 5–7 hours · Docs verified 2026-10-12

**Goal:** an agent that answers LangChain/LangGraph questions by searching the official docs over MCP (and the web when the docs have nothing), returns a structured answer whose `sources` are **verified against tool results**, and saves notes to your own FastMCP server only after a human approves.

| File | What it is |
|---|---|
| [`05-project-docs-research-agent.ipynb`](05-project-docs-research-agent.ipynb) | **Starter.** Runs top to bottom from the start. Four `# TODO` blocks are yours to complete |
| [`solutions/05-project-docs-research-agent-solution.ipynb`](solutions/05-project-docs-research-agent-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried, or when you are stuck on one TODO |

Data: [`data/samples/mcp/benchmark.jsonl`](../../../data/samples/mcp/benchmark.jsonl) (10 questions about this course's topics, each with the docs page that answers it) and [`docs-snapshot.json`](../../../data/samples/mcp/docs-snapshot.json) (86 docs sections captured 2026-10-12 for the offline stand-in). Notes and the audit log go to the git-ignored `data/outputs/m05/`.

## Requirements

1. **Tools from two MCP sources:** the LangChain docs server `https://docs.langchain.com/mcp` (`search_docs_by_lang_chain`, `query_docs_filesystem_docs_by_lang_chain`) and the course notes server `mastery.mcp_servers.notes_server` (`save_note`, `search_notes`, `list_notes`). Least privilege: `submit_feedback` and `delete_note` are not given to the agent. The docs server is third-party: its allowed tools are **pinned** (`tool_fingerprint` + `poisoned_descriptions`, reviewed value in `data/samples/mcp/reviewed-fingerprints.json`; LIVE, recorded on first connect in `data/outputs/m05/`) and refused on any change.
2. **Web search** for anything outside the docs: `web_search` from `mastery.web_search`. Default: Groq built-in browser search (the search is its own step inside the tool, so the final answer can still be structured: the two-step pattern of 05.01). `MASTERY_WEB_SEARCH=tavily` in `.env` switches to Tavily (needs `TAVILY_API_KEY`).
3. **Structured answer:** `Answer(answer: str, sources: list[str])` via `ToolStrategy`. `validate_sources` keeps only URLs that appeared in a tool result and reports the rest as **invented**.
4. **HITL before `save_note`:** `HumanInTheLoopMiddleware` with a policy from `approval_policy(...)` and an allow-list of reviewed read-only tools (annotations alone are not trusted).
5. **Egress gate:** private notes + untrusted docs/web text + an outbound `web_search` query is the "lethal trifecta". Once a thread has read a note, `web_search` is blocked and the block is logged.
6. **Limits that end in an answer:** tool-call limits use `exit_behavior="continue"` (the model gets an error and must still `Answer`; the global limit counts the `Answer` call, hence 9), with `ModelCallLimitMiddleware` as a backstop. A run that ends without an `Answer` is scored as a failure, never a crash.

| TODO | Where | What |
|---|---|---|
| 1 | Step 1 | `load_tools`: two `MCPAdapter`s, allowed names only, `pin_check` on the docs tools, plus `web_search` |
| 2 | Step 3 | `validate_sources`: `urls_from_messages(..., skip_tools={"Answer"})` + `check_sources` |
| 3 | Step 2 | `approval_policy_for`: HITL on `save_note`; reviewed reads and `web_search` run freely |
| 4 | Step 5 | `score`: does a cited source match the expected docs page? |

## Acceptance criteria (12 checks in Step 5 offline; 10 in LIVE)

- **≥8/10** benchmark answers cite the docs page that contains the answer (the `expected_page` itself or one of its sub-pages; anchors count, look-alike pages such as `...-guide` don't). **Spot-check** two or three cited pages by hand in LIVE mode.
- **0 invented URLs** reach an answer, and every answer has at least one source. The check compares your `validate_sources` with an independent check of the model's raw sources, and offline an "inventive" model must have its fake URL removed while the real source is kept (2 checks).
- **Rug pull:** a docs tool with a changed description is refused, and `load_tools` refuses a docs server whose fingerprint no longer matches the reviewed one (2 checks).
- **Egress:** a scripted model that reads a note and then calls `web_search` with it is blocked, and `egress_blocked` is in the audit log.
- **Limits:** a model that never stops searching ends as a scored failure (`no answer (limit)`), not an exception.
- `save_note` (loaded, TODO 1): a reject saves nothing; an approve saves exactly one note; every `save_note` that ran was approved first (audit log).
- **Restart & Run All** passes with `GROQ_API_KEY` and without any key. Outputs cleared; `data/outputs/` never committed.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Tools and trust | Two MCP sources loaded by allowed name; rug-pull and fingerprint checks pass | A tool contract snapshot of your own (names + descriptions) checked on every run |
| Sources | 0 invented URLs; every answer has a source; ≥ 8/10 cite the expected page | Two or three cited pages spot-checked by hand, with notes in your findings |
| Safety | HITL on `save_note`; egress blocked after a note is read | A second egress case of your own (e.g. a note text inside a docs query) that is caught |
| Limits | A model that never stops ends as a scored failure, not an exception | Measures how often LIVE runs hit a limit, and adjusts one limit with evidence |
| Hygiene | Restart & Run All with and without a key; outputs cleared | Groq vs Tavily comparison (if you have a key) with timings and source quality |

## Modes

- **LIVE** (`GROQ_API_KEY` set): `openai/gpt-oss-20b` (`reasoning_effort="low"`) with the real docs server (falls back to the stand-in if unreachable). About 60–120k tokens for the full benchmark, free tier. The free tier allows about 8K tokens/minute and 200K/day, so expect throttling and only 1–3 full runs per day; a 429 or other error is recorded as a failed row. Results vary run to run: read the transcript as well as the ✅.
- **OFFLINE DEMO** (no key): a scripted "reader" searches the **docs stand-in** with the question's keywords and cites the result it judges best. It is honest, not tuned per question: it gets **8/10** (q05 and q08 pick a neighbouring page). An "inventive" variant adds a fake URL so you can see `validate_sources` remove it. With all TODOs done: **12/12**; the untouched starter shows 4/12 with ❌ pointing at the TODOs.
- **Tavily** (`MASTERY_WEB_SEARCH=tavily` + `TAVILY_API_KEY`, optional): only changes `web_search`; 1 credit per search.

## Stretch goal (`RUN_STRETCH = True`)

Expose the agent itself as an MCP tool: a FastMCP server with `ask_docs(question) -> {answer, sources}` (read-only to callers: its reviewer rejects `save_note`), tested through `MCPAdapter`. Serve it with `run(transport="http", host="127.0.0.1", port=8771)` from a `.py` file; later from your FastAPI service (Module 12) or the [Agent Server MCP endpoint](https://docs.langchain.com/langsmith/server-mcp) (optional Lesson 12.08).

## Stack

Free: Groq (gpt-oss-20b + built-in browser search), the LangChain docs MCP server, FastMCP. Freemium alternative: Tavily (1,000 free credits/month).
