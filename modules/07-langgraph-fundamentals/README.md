# Module 07 — LangGraph Fundamentals

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 07](../../COURSE_OUTLINE.md#module-07--langgraph-fundamentals)

**Goals:** Think in graphs. Build deterministic + agentic workflows with the Graph API. Know the canonical workflow patterns. Use the Functional API when it fits. Debug in Studio.

**Estimated time:** 2 weeks (about 14–17 hours of lessons plus 6–8 hours for the project).

## Before you start this module

Run this **once**, in **Git Bash**, from the **repo root**, with the **`lc-mastery`** environment active (the prompt starts with `(lc-mastery)`).

```bash
cd ~/path/to/langchain-langgraph-mastery   # your clone; quote the path if it has spaces
conda activate lc-mastery
git pull                                   # get this module's files
python -m pip install -e ".[dev,embeddings]"   # re-run after every pull (Module 07 adds no packages; it keeps langgraph-api >= 0.16, see D-023)
python -m pip check                        # expect: No broken requirements found.  (not clean? Module 06 README, "Saw ERROR: pip's dependency resolver...")
python -m pytest -q                        # expect: "... passed" and no failures (offline, no keys)
python -c "import langgraph, importlib.metadata as m; print('langgraph', m.version('langgraph'), '| langgraph-api', m.version('langgraph-api'))"   # expect: langgraph 1.2.x | langgraph-api 0.16.x
langgraph --version                        # expect: LangGraph CLI, version 0.4.x
```

| | |
|---|---|
| 🔑 Keys | `GROQ_API_KEY` (optional: without it 💸 cells print `⏭️ Skipped` and scripted models stand in). `LANGSMITH_API_KEY` (optional: Studio and traces for cost/latency). **No new keys** |
| 💰 Cost | $0. Graph mechanics run offline. LIVE cells use `gpt-oss-20b` on the Groq free tier: a few thousand tokens each; one Project 07 run ≈ 6–12k tokens |
| 💾 Disk | Nothing new. 07.07 writes a small SQLite file to `data/outputs/m07/` (git-ignored) |
| 🌐 Network | Graph images are drawn by mermaid.ink (public, no key). Offline or blocked? `show_graph` falls back to Mermaid text (JupyterLab renders it). Studio is a web page at smith.langchain.com that talks to **your** local server |
| ✅ Ready when | `pip check` is clean, `pytest` passes, `langgraph-api 0.16.x` and the CLI version print |

If `pip install` or `pytest` fails, see the [setup guide's troubleshooting](../00-foundations/00-02-create-course-env.md#troubleshooting).

## How to work through this module

1. **Do [Before you start this module](#before-you-start-this-module) first** (once per pull). Module 07 adds `mastery.graphs` and the app folder [`apps/m07_content_pipeline/`](../../apps/m07_content_pipeline/README.md).
2. **Start Jupyter from the repo root** (`jupyter lab` in Git Bash) and pick the **Python (lc-mastery)** kernel in every notebook.
3. **Go in order.** 07.01 designs before coding; 07.02–07.03 are the Graph API; 07.04 the canonical patterns (you'll reuse them in Project 07); 07.05 the Functional API; 07.06 runs a graph as an app in Studio; 07.07 rebuilds Module 06's RAG agent as a custom graph and adds a SQL agent.
4. **Read the cell markers.** 🧪 = offline (scripted models, free) · 🌐 = network, no tokens (graph PNGs) · 💸 = calls a model. **Restart & Run All** always completes without a key.
5. **Windows notes.** `langgraph dev` runs in **its own Git Bash window** (it keeps running; stop it with **Ctrl + C**). If port 2024 is taken: `langgraph dev --port 2025` and change `baseUrl` in the Studio link. Studio in Safari/Brave may block `http://127.0.0.1`: use Chrome/Edge or `langgraph dev --tunnel`. SQLite files are opened read-only and closed after every query, so deleting `data/outputs/m07/` works while the kernel runs.
6. **Before you commit:** *Kernel → Restart Kernel and Run All Cells…*, *Edit → Clear Outputs of All Cells*, save, then `python -m pytest -q`.

## Lessons

| Lesson | Title | Notebook | Time | Keys |
|---|---|---|---|---|
| 07.01 | Thinking in LangGraph | [`07-01-thinking-in-langgraph.ipynb`](07-01-thinking-in-langgraph.ipynb) | 60–90 min | `GROQ_API_KEY` (optional) |
| 07.02 | Graph API: state, nodes, edges, reducers | [`07-02-graph-api-basics.ipynb`](07-02-graph-api-basics.ipynb) | 120–150 min | none |
| 07.03 | Control flow: `Command`, `Send`, cycles, recursion limits | [`07-03-control-flow.ipynb`](07-03-control-flow.ipynb) | 120–150 min | none |
| 07.04 | Workflow patterns | [`07-04-workflow-patterns.ipynb`](07-04-workflow-patterns.ipynb) | 150–180 min | `GROQ_API_KEY` (optional) |
| 07.05 | Functional API | [`07-05-functional-api.ipynb`](07-05-functional-api.ipynb) | 90–120 min | none |
| 07.06 | Application structure, local server, and Studio | [`07-06-app-structure-and-studio.ipynb`](07-06-app-structure-and-studio.ipynb) | 90–120 min | none (Studio needs a free LangSmith login; `LANGSMITH_API_KEY` optional for traces) |
| 07.07 | Custom agentic RAG and SQL agents in LangGraph | [`07-07-custom-rag-and-sql-graphs.ipynb`](07-07-custom-rag-and-sql-graphs.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |

**What each lesson gives you**

- **07.01:** the five design steps from the docs (steps → what each step needs → state → nodes → wiring) on a support-ticket triage; a Mermaid design cell before code; when `create_agent` is enough and when to drop to LangGraph.
- **07.02:** `StateGraph` with `TypedDict` and Pydantic state, reducers (`operator.add`, `add_messages`, custom ones from `mastery.graphs`), `MessagesState`, normal and conditional edges, `START`/`END`, compile, invoke, `get_graph()` drawings; a state-update trace you can read.
- **07.03:** `Command(update=..., goto=...)`, map-reduce with `Send`, a bounded cycle, `recursion_limit` and `GraphRecursionError`, `RemainingSteps` for a graceful stop.
- **07.04:** prompt chaining (with a gate), parallelization, routing, orchestrator-worker, evaluator-optimizer, and an agent loop by hand with `ToolNode`; when each one fits.
- **07.05:** `@entrypoint` and `@task`, futures, checkpointed results with `InMemorySaver`, `previous` and `entrypoint.final`; determinism, idempotency, JSON-serializable inputs and outputs; Graph vs Functional, decided per case.
- **07.06:** `langgraph.json`, dependencies and `.env`; `langgraph dev`; Studio (graph view, runs, state, time-travel preview); calling the local server from Python with `langgraph-sdk`.
- **07.07:** Module 06's agentic RAG as a custom graph (retrieve → **grade documents** → rewrite question → answer), and a SQL agent graph (list tables → schema → generate → **check query** → run, read-only).

## Project

**[Project 07 — Content Pipeline Graph](project/README.md)**: a graph that turns a topic into a reviewed blog-post draft: `plan_outline` → parallel `research_section` (`Send`) → `write_draft` → `critique` → `revise` loop (max 3) → `finalize`. Typed state with reducers, structured outline and critique, the graph drawn in the notebook, the same app under `langgraph dev`/Studio, cost and latency per run.

| File | Use |
|---|---|
| [`project/README.md`](project/README.md) | Spec, acceptance criteria, modes, stretch goals |
| [`project/07-project-content-pipeline.ipynb`](project/07-project-content-pipeline.ipynb) | **Starter** with four `# TODO`s (runs from day one, also offline) |
| [`project/solutions/07-project-content-pipeline-solution.ipynb`](project/solutions/07-project-content-pipeline-solution.ipynb) | **Reference solution** (open after trying) |
| [`apps/m07_content_pipeline/`](../../apps/m07_content_pipeline/README.md) | The same graph as a LangGraph app for `langgraph dev` and Studio |

## Jupyter skill in this module

**Inline graph visualization + Mermaid documentation cells**:

| Skill | Where |
|---|---|
| Draw a compiled graph inline: `show_graph(graph)` (PNG via mermaid.ink, Mermaid text fallback); `graph.get_graph().draw_mermaid()` / `draw_ascii()` | 07.02, every lesson after |
| Write the design **first** as a ```` ```mermaid ```` block in a Markdown cell (JupyterLab 4.1+ and GitHub render it), then compare with the drawn graph | 07.01, 07.04 |
| `get_graph(xray=True)` to see inside subgraphs and agents | 07.07 |
| Save the diagram next to the code (`draw_mermaid_png(output_file_path=...)`) for docs | 07.06 |

## `src/mastery` increment

| File | What it does | Tests |
|---|---|---|
| [`src/mastery/graphs/state.py`](../../src/mastery/graphs/state.py) | Reducers `merge_dicts`, `append_unique`, `keep_last(n)`; Project 07 schemas `Outline`, `SectionPlan`, `Critique`, `SectionNote`, `ContentState`; `memory_checkpointer()` (allows these types in checkpoints, D-028) | [`tests/unit/test_graphs.py`](../../tests/unit/test_graphs.py) |
| [`src/mastery/graphs/nodes.py`](../../src/mastery/graphs/nodes.py) | `timed` (per-node latency into `run_log`), `run_summary`, `loop_router` (score threshold + hard iteration cap), `stream_updates`, `show_graph`, `mermaid_markdown` | same |
| [`src/mastery/graphs/content.py`](../../src/mastery/graphs/content.py) | The Project 07 reference pipeline `build_content_graph`, prompts, `corpus_researcher` (offline, Module 06 corpus), `web_researcher` (Module 05 `web_search`), `offline_models` | same |
| [`src/mastery/graphs/sql.py`](../../src/mastery/graphs/sql.py) | Read-only SQLite helpers for 07.07: `sqlite_from_csv`, `list_tables`, `table_schema`, `check_sql`, `run_readonly_query` (read-only connection + authorizer) | same |
| [`src/mastery/graphs/server.py`](../../src/mastery/graphs/server.py) | `DevServer`: start `langgraph dev --no-reload` on a free port from a notebook, wait for `/ok`, stop it (07.06, Project 07) | same |
| [`src/mastery/doctor.py`](../../src/mastery/doctor.py) | `check_dependencies()`: a focused `pip check` for the course stack (D-023) | [`tests/unit/test_doctor.py`](../../tests/unit/test_doctor.py) |

## Production notes

> ⚠️ **Production note: every loop needs a counter, not only a model's opinion.**
> Evaluator-optimizer loops stop on "good enough" **or** after N iterations (`loop_router`), and the graph has a `recursion_limit`. Log which one fired.

> ⚠️ **Production note: `langgraph dev` is a development server.**
> In-memory, single process, no auth. Production uses a persistent Agent Server (LangSmith Deployment) or your own FastAPI service with a durable checkpointer (Modules 08 and 13).

> ⚠️ **Production note: model-written SQL is untrusted code.**
> Read-only credentials at the database, an allow-list of tables, statement checks, row limits and timeouts. A "check query" prompt is a second opinion, not a security control.

Each lesson has its own production notes; they are collected in [`docs/production-notes.md`](../../docs/production-notes.md).

## Research checkpoint

Read [Choosing between Graph and Functional APIs](https://docs.langchain.com/oss/python/langgraph/choosing-apis) and write **your own** rule of thumb (two or three sentences, with one example from this module of each) in [`docs/research-log.md`](../../docs/research-log.md). 07.05 ends with a template.

## Status

✅ Built (docs verified 2026-10-12).

---

← [Module 06](../06-rag/README.md) · [Course outline](../../COURSE_OUTLINE.md) · [Module 08](../08-langgraph-production-features/) →
