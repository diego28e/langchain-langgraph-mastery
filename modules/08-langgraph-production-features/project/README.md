# Project 08 — Research-and-Write Agent with Human Approval

> **Module 08 · LangGraph Production Features** · ⏱️ 6–8 hours · Docs verified 2026-10-12 · the last project of Part 1

**Goal:** a durable, interruptible research assistant. It asks when a request is vague, plans, researches your docs and the web in a subgraph, drafts an answer, and **waits for your approval** before it finalizes. It survives a crash, retries a flaky web search (and falls back to docs-only when the web is down), streams its progress, and you can fork it from the plan to try a different one.

| File | What it is |
|---|---|
| [`08-project-research-agent.ipynb`](08-project-research-agent.ipynb) | **Starter.** Runs top to bottom from the start. Four `# TODO` blocks are yours to complete |
| [`solutions/08-project-research-agent-solution.ipynb`](solutions/08-project-research-agent-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried, or when you are stuck on one TODO |
| [`apps/m08_research_agent/`](../../../apps/m08_research_agent/README.md) | The **app**: `agent.py` + `langgraph.json`, served by `langgraph dev`; answer the interrupts in Studio |
| [`src/mastery/graphs/research.py`](../../../src/mastery/graphs/research.py) | The reference graph (`build_research_graph`), prompts, offline models, docs/web search backends and the crash-demo CLI. The app and the tests use it |
| [`src/mastery/graphs/hitl.py`](../../../src/mastery/graphs/hitl.py) | `approval_node` (approve / edit / reject + validation loop + give-up), `run_until_pause`, `resume`, `drive` |

Docs search uses **Project 06's Chroma index** when it exists in `data/vectorstores/` (`USE_PROJECT06_INDEX = True`), else BM25 over the same Module 06 corpus (offline, free). Outputs go to the git-ignored `data/outputs/m08/` (the SQLite checkpoint file `project08.sqlite` and `project08-report.json`).

## Requirements

1. **Graph:** `clarify_question` (**interrupt** if the request is ambiguous) → `plan` (structured output, stored as a plain dict) → **research subgraph** (`search_docs` → `search_web`, its own state schema) → `draft` → **approval interrupt** (approve / edit / reject with feedback) → `finalize`, or back to `draft` (max 3 rejections, then it finalizes as `gave_up`).
2. **SQLite checkpointer** (`AsyncSqliteSaver`: the graph has async nodes). A run survives a restart (close and reopen the database) and a crash (a child process killed mid-run, resumed in the notebook).
3. **Time travel:** fork the thread right after `plan` with a different plan; label the branch with `metadata` and `tags`.
4. **Streaming:** node updates (parent + subgraph) and the draft's tokens in a live-updating notebook display. **Per-node retry and timeout** on the web search, with an `error_handler` fallback.

| TODO | Where | What |
|---|---|---|
| 1 | Step 2 | `clarify_question`: pause with a clarifying question when the request is ambiguous, in a way that survives the resume (the node re-runs from the top) |
| 2 | Step 2 | `web_node_options`: bound the web search's time, retry only transient failures (one retry layer), and fall back to a docs-only answer when it stays down |
| 3 | Step 2 | `make_approval`: approve finalizes, reject loops back to the writer with the feedback, and the loop gives up after a few rejections |
| 4 | Step 5 | `fork_from_plan`: rewind to just after planning, change the plan, and run a labelled branch you can find in the trace |

Each TODO has a 💡 hint cell under it (collapsed); the solution notebook has the full code.

## Acceptance criteria (9 checks in Step 7 offline; 8 in LIVE)

- **Survives a restart:** a thread of **your** graph paused at `approval` finalizes after the database is closed and reopened. (Step 4b also kills the reference graph in a child process mid-search and resumes it from SQLite: a runtime demo, reported but not graded.)
- **Approval is required before finalization:** the run pauses at `approval` and nothing is final before it; each rejection sends it back to `draft` with that rejection's feedback (the writer runs once more per rejection, and the revision shows up in the final text); giving up only happens after the rejection limit; a vague request triggers a clarifying question first, and the clarify step is **resume-safe** (the model's verdict is computed once and replayed on resume, so the human's answer can't be dropped).
- **The fork is a different, traceable branch:** different plan, different sources, different final answer, and checkpoints labelled `branch=fork-1` with `forked_from=<checkpoint id>`. With LangSmith tracing on, filter by tag `fork` or `metadata.branch`.
- **Fault tolerance:** a transient web failure is retried invisibly (`retry_on=mastery.models.is_transient`, the LIVE web model has `max_retries=0` so retries live in one layer); 400/401 errors are not retried; a dead or hanging web search ends in `Web search unavailable (...)` and a docs-only answer instead of a failed run.
- **Traces:** the notebook sets `LANGSMITH_PROJECT=m08-project-research-agent` unless you set your own.
- **Restart & Run All** passes with `GROQ_API_KEY` and without any key. Outputs cleared; `data/outputs/` never committed.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Durability | A paused thread of your graph finalizes after the database is reopened | Explains which nodes re-ran after the child-process kill and why that is safe |
| Human approval | Nothing is final before approval; each rejection loops back with its feedback | Approval records who approved which draft (draft hash, reviewer, time) |
| Time travel | The fork is a different, labelled branch | Compares the fork and the original in LangSmith, linked from your findings |
| Fault tolerance | Transient failures retried once in one layer; 400/401 not retried | A failure case of your own (e.g. a timeout) with the expected behaviour asserted |
| Hygiene | Restart & Run All with and without a key; traces in your project; outputs cleared | Writing-preferences stretch with two users and a check that they don't mix |

## Modes

- **LIVE** (`GROQ_API_KEY` set): `openai/gpt-oss-20b` (`reasoning_effort="low"`) clarifies, plans and writes; the web is Groq's built-in browser search (`mastery.web_search`). One run ≈ 5–15k tokens; the notebook makes ~4 runs: free on the free tier, under $0.02 at paid prices. Step 6 (retry/timeout) always uses the offline web stand-ins, so it costs nothing extra.
- **OFFLINE DEMO** (no key): `offline_models()` scripts the three roles (a request under 4 words is "ambiguous"; the writer makes one bullet per finding, two after "shorter" feedback, one paragraph for a "paragraph" preference). `offline_web_search()` returns no results but can fail (`failures=N`) or hang (`delay=S`) on purpose. Reference result: 9/9 checks. The untouched starter passes 0/9, with ❌ pointing at the TODOs.

## Run it in Studio (once, by hand)

In a second Git Bash window, with `(lc-mastery)` active:

```bash
cd apps/m08_research_agent
langgraph dev          # Safari or Brave: langgraph dev --tunnel
```

Start a run with `{"question": "Battery?"}`: Studio shows the clarify interrupt; answer with plain text. At the approval interrupt answer `{"action": "reject", "feedback": "make it shorter"}`, then `{"action": "approve"}`. Then open the thread, pick the checkpoint after `plan`, edit `plan`, and fork: that's Step 5 in the UI.

## Stretch goals

- **Writing preferences in a long-term store** (Step 8, `RUN_STRETCH = True`): `draft` reads `("preferences", user_id)` from `runtime.store`; the same question gives a paragraph for one user and bullets for another. Make it persistent with `make_store("sqlite", ...)`; in `langgraph dev` pass `context={"user_id": "ana"}` with the run.
- **Agent Chat UI:** [Agent Chat UI](https://docs.langchain.com/oss/python/langchain/ui) renders chat graphs (a `messages` key) and their interrupts. Write a thin `MessagesState` wrapper graph that calls this agent (Way 2, Lesson 08.05) and returns the final answer as an AI message; add it to `langgraph.json` as a second graph id and connect the UI to `http://127.0.0.1:2024`.
- **Stronger writer (paid):** keep `gpt-oss-20b` for clarify/plan and draft with a bigger model (`get_model("reasoning")` or OpenAI as a benchmark). Fork the same thread after `plan` with both writers and compare.

## Stack

Free: Groq (gpt-oss-20b + built-in browser search), Chroma (Project 06) or BM25, SQLite (`langgraph-checkpoint-sqlite` + `aiosqlite`), `langgraph dev` + Studio (free LangSmith account). Paid alternatives: a stronger drafting model; Postgres (`PostgresSaver`) or LangSmith Deployment for multi-worker persistence.
