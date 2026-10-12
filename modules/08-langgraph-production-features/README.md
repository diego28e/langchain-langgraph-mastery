# Module 08 — LangGraph Production Features

> **Part 1 — Core (Modules 00–08)** · the last module of Part 1 · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 08](../../COURSE_OUTLINE.md#module-08--langgraph-production-features)

**Goals:** Master what makes LangGraph a runtime: persistence, durable execution, interrupts, time travel, subgraphs, streaming, fault tolerance, and long-term stores.

**Estimated time:** 2 weeks (about 13–16 hours of lessons plus 6–8 hours for the project).

## Before you start this module

Run this **once**, in **Git Bash**, from the **repo root**, with the **`lc-mastery`** environment active (the prompt starts with `(lc-mastery)`).

```bash
cd ~/path/to/langchain-langgraph-mastery   # your clone; quote the path if it has spaces
conda activate lc-mastery
git pull                                   # get this module's files
python -m pip install -e ".[dev,embeddings]"   # re-run after every pull (Module 08 adds no packages: aiosqlite comes with langgraph-checkpoint-sqlite)
python -m pip check                        # expect: No broken requirements found.  (not clean? Module 06 README, "Saw ERROR: pip's dependency resolver...")
python -m pytest -q                        # expect: "... passed" and no failures (offline, no keys)
python -c "import importlib.metadata as m; print('langgraph', m.version('langgraph'), '| checkpoint-sqlite', m.version('langgraph-checkpoint-sqlite'), '| aiosqlite', m.version('aiosqlite'))"   # expect: langgraph 1.2.x | checkpoint-sqlite 3.1.x | aiosqlite 0.2x
python -m mastery.graphs.research --help   # expect: usage: ... --db DB --thread THREAD --question QUESTION ...
```

| | |
|---|---|
| 🔑 Keys | `GROQ_API_KEY` (optional: without it 💸 cells print `⏭️ Skipped` and scripted models stand in). `LANGSMITH_API_KEY` (optional: traces of forks in 08.04 and Project 08). **No new keys** |
| 💰 Cost | $0. Every mechanism is shown offline. LIVE cells use `gpt-oss-20b` on the Groq free tier (a few thousand tokens each); one Project 08 run ≈ 5–15k tokens incl. Groq browser search |
| 💾 Disk | A few small SQLite files in `data/outputs/m08/` (git-ignored, < 5 MB; 08.01 grows one to ~2 MB on purpose) |
| 🖥️ Processes | 08.01, 08.02 and Project 08 start a **child Python process** and kill it on purpose (a simulated crash). It ends by itself; nothing keeps running |
| ✅ Ready when | `pip check` is clean, `pytest` passes, the three versions print and the research CLI shows its help |

If `pip install` or `pytest` fails, see the [setup guide's troubleshooting](../00-foundations/00-02-create-course-env.md#troubleshooting).

## How to work through this module

1. **Do [Before you start this module](#before-you-start-this-module) first** (once per pull). Module 08 adds `mastery.graphs.hitl`, `persistence`, `stores`, `research` and the app folder [`apps/m08_research_agent/`](../../apps/m08_research_agent/README.md).
2. **Start Jupyter from the repo root** (`jupyter lab` in Git Bash) and pick the **Python (lc-mastery)** kernel in every notebook.
3. **Go in order.** 08.01–08.02 are about not losing work (checkpoints, durability, retries, timeouts); 08.03–08.04 put a human in the loop and travel in time; 08.05–08.06 compose and observe graphs; 08.07 adds memory across threads. Every lesson uses pieces of Project 08's research agent, so the project feels familiar.
4. **Read the cell markers.** 🧪 = offline (scripted models, free) · 🌐 = network, no tokens (LangSmith API in 08.04) · 💸 = calls a model. **Restart & Run All** always completes without a key.
5. **Async cells.** Graphs with timeouts are `async`; in a notebook cell you write `await graph.ainvoke(...)` directly (Jupyter runs an event loop). In a `.py` script wrap it in `asyncio.run(main())`.
6. **Windows notes.** Close SQLite connections before deleting their files (`close(saver)` / `await saver.conn.close()`), or Windows reports `PermissionError: [WinError 32]`. The crash demos use `Popen.kill()`, which works on Windows (TerminateProcess). If a child process ever survives a kernel crash, end it in Task Manager (`python.exe`).
7. **Before you commit:** *Kernel → Restart Kernel and Run All Cells…*, *Edit → Clear Outputs of All Cells*, save, then `python -m pytest -q`.

## Lessons

| Lesson | Title | Notebook | Time | Keys |
|---|---|---|---|---|
| 08.01 | Persistence: checkpointers, threads, and durability | [`08-01-persistence.ipynb`](08-01-persistence.ipynb) | 120–150 min | none |
| 08.02 | Durable execution and fault tolerance | [`08-02-durable-execution-and-fault-tolerance.ipynb`](08-02-durable-execution-and-fault-tolerance.ipynb) | 120–150 min | none |
| 08.03 | Interrupts and human-in-the-loop (graph level) | [`08-03-interrupts.ipynb`](08-03-interrupts.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 08.04 | Time travel: replay and fork | [`08-04-time-travel.ipynb`](08-04-time-travel.ipynb) | 90–120 min | `GROQ_API_KEY`, `LANGSMITH_API_KEY` (both optional) |
| 08.05 | Subgraphs | [`08-05-subgraphs.ipynb`](08-05-subgraphs.ipynb) | 90–120 min | none |
| 08.06 | Streaming in depth | [`08-06-streaming.ipynb`](08-06-streaming.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 08.07 | Long-term memory store inside graphs | [`08-07-stores-in-graphs.ipynb`](08-07-stores-in-graphs.ipynb) | 90–120 min | none |

**What each lesson gives you**

- **08.01:** `StateSnapshot` anatomy (`values`, `next`, `tasks`, `metadata`, parent ids); SQLite threads that survive a restart; the three `durability` modes **measured** by killing a run; deleting and trimming threads; serialization rules (plain dicts in state, allow-lists for your classes).
- **08.02:** `RetryPolicy` (and what `default_retry_on` does and doesn't retry), fallback on the last attempt, timeouts for async nodes, `error_handler` with `Command(goto=...)`, `set_node_defaults`, resuming a killed run, idempotency, draining with `RunControl`.
- **08.03:** `interrupt()` / `Command(resume=...)`, why the node re-runs, approve / edit / reject with a validation loop and a give-up limit (`mastery.graphs.hitl`), interrupts inside tools, parallel interrupts by id, static breakpoints, a live-updating status cell.
- **08.04:** pick checkpoints by `next`, replay vs fork (`update_state(..., as_node=...)`), the thread as a tree, branch labels in `metadata`/`tags`, finding forks in LangSmith.
- **08.05:** subgraph as a node vs called from a node, the shared-reducer duplication trap, `stream(subgraphs=True)`, `get_state(subgraphs=True)`, interrupts inside a subgraph with one checkpointer.
- **08.06:** all seven stream modes counted, the v2 event format, combined modes, token filtering by node, `get_stream_writer()` progress, a live-updating display, the experimental `stream_events(version="v3")`.
- **08.07:** `runtime.store` + `runtime.context` in nodes, namespaces per user/org, filter and semantic search, Project 08's preferences, a contract test for InMemory and SQLite stores.

## Project

**[Project 08 — Research-and-Write Agent with Human Approval](project/README.md)**: `clarify_question` (interrupt if vague) → `plan` → research subgraph (docs over Project 06's index + web search with retry, timeout and fallback) → `draft` → approval interrupt (approve / edit / reject) → `finalize`. SQLite checkpoints that survive a restart and a crash, a fork from the plan, streamed progress and tokens.

| File | Use |
|---|---|
| [`project/README.md`](project/README.md) | Spec, acceptance criteria, modes, stretch goals |
| [`project/08-project-research-agent.ipynb`](project/08-project-research-agent.ipynb) | **Starter** with four `# TODO`s (runs from day one, also offline) |
| [`project/solutions/08-project-research-agent-solution.ipynb`](project/solutions/08-project-research-agent-solution.ipynb) | **Reference solution** (open after trying) |
| [`apps/m08_research_agent/`](../../apps/m08_research_agent/README.md) | The same graph as a LangGraph app: answer its interrupts in Studio |

## Jupyter skill in this module

**Live-updating displays for streams and interrupt/resume cells**:

| Skill | Where |
|---|---|
| `handle = display(Markdown(...), display_id=True)` then `handle.update(...)`: one output area that changes in place (status lines, a growing answer with a `▌` cursor) | 08.03, 08.06, Project 08 |
| **Parameter cells** for the human (`DECISIONS = [...]`, `CLARIFICATION = "..."`): change the value, re-run the next cell, see the other branch; scripted defaults keep Restart & Run All green | 08.03, Project 08 |
| Top-level `await` in cells for async graphs (`await graph.ainvoke(...)`, `async for ... in graph.astream(...)`) | 08.02 onwards |
| Child processes from a cell (`subprocess.Popen`) to simulate a crash, then resume in the kernel | 08.01, 08.02, Project 08 |

## `src/mastery` increment

| File | What it does | Tests |
|---|---|---|
| [`src/mastery/graphs/hitl.py`](../../src/mastery/graphs/hitl.py) | `approval_node` (approve / edit / reject, validation loop, give-up after N rejections, returns `Command`), `Decision`/`parse_decision`, `run_until_pause`, `resume`, `drive` (+ async versions), `scripted_reviewer`, `pending_interrupts` | [`tests/unit/test_graphs_m08.py`](../../tests/unit/test_graphs_m08.py) |
| [`src/mastery/graphs/persistence.py`](../../src/mastery/graphs/persistence.py) | `sqlite_checkpointer`, `async_sqlite_checkpointer` (with the course allow-list), `checkpoint_rows`/`acheckpoint_rows`, `count_checkpoints`, `trim_thread`, `file_size` | same |
| [`src/mastery/graphs/stores.py`](../../src/mastery/graphs/stores.py) | `check_store_contract(store, semantic=...)`: 10–11 behaviours graph code relies on | same |
| [`src/mastery/graphs/research.py`](../../src/mastery/graphs/research.py) | The Project 08 reference graph `build_research_graph`, `Plan`/`Clarity`, prompts, `corpus_docs_search`/`retriever_docs_search`, `offline_web_search` (fails/hangs on purpose), `web_tool_search`, `offline_models`, the crash CLI (`python -m mastery.graphs.research`) and `run_and_kill` | same |
| [`src/mastery/graphs/nodes.py`](../../src/mastery/graphs/nodes.py) | `timed` now also wraps `async def` nodes (needed for timeouts) | same + [`test_graphs.py`](../../tests/unit/test_graphs.py) |

## Production notes

> ⚠️ **Production note: pick durability per graph, from evidence.**
> `"sync"` never loses a completed step; `"async"` (the default) can lose the last steps in a crash; `"exit"` loses the whole run (08.01 measured all three). Slow, costly or human-gated steps deserve `"sync"`.

> ⚠️ **Production note: durable is not exactly-once.**
> A node interrupted mid-way re-runs from its start, and so does a node with `interrupt()` on resume. Side effects need idempotency keys or must come after the checkpoint that records the decision.

> ⚠️ **Production note: humans are part of the system.**
> Paused threads can wait for days: store them durably, validate every resume value, record who approved what, and expire abandoned approvals.

Each lesson has its own production notes; they are collected in [`docs/production-notes.md`](../../docs/production-notes.md).

## Research checkpoint

Read [Backward compatibility](https://docs.langchain.com/oss/python/langgraph/backward-compatibility) and log in [`docs/research-log.md`](../../docs/research-log.md) **what happens to in-flight runs** (threads paused at an interrupt, or crashed mid-run) **when you change a graph**: adding a node, removing or renaming one, adding or removing state keys, changing a reducer. Test one case yourself: pause a Project 08 thread at `approval`, add a node between `approval` and `finalize`, rebuild the graph on the same SQLite file and resume. 08.07 ends with this prompt too.

## Part 1 complete

This module ends **Part 1 — Core (Modules 00–08)**. You can now:

- set up a reproducible environment and use models, messages, prompts and structured output (Modules 00–01);
- build tool-calling agents with `create_agent`, memory, middleware, guardrails and human approval (Modules 02–04);
- connect MCP servers and web search, and build and evaluate RAG systems (Modules 05–06);
- design LangGraph workflows (Module 07) and make them **production-grade**: persistent, durable, interruptible, forkable, composable, streamed and with long-term memory (Module 08).

**Before you move on:** Projects 01–08 pass their acceptance checks, `python -m pytest -q` is green, and your [`docs/research-log.md`](../../docs/research-log.md) and [`docs/decision-log.md`](../../docs/decision-log.md) have your own entries.

**What's next: Part 2 — Pro (Modules 09–14)** makes these systems coordinated, long-running, multimodal, measured and deployed. It starts with **[Module 09 — Multi-Agent Systems](../09-multi-agent-systems/README.md)** (subagents, handoffs, router, custom workflows; [outline](../../COURSE_OUTLINE.md#module-09--multi-agent-systems)), which builds directly on this module's subgraphs, interrupts and stores. Part 2 modules are 📝 planned; when one ships, start with its README's **Before you start this module** block.

## Status

✅ Built (docs verified 2026-10-12).

---

← [Module 07](../07-langgraph-fundamentals/README.md) · [Course outline](../../COURSE_OUTLINE.md) · [Module 09](../09-multi-agent-systems/README.md) →
