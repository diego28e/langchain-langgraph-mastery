# Module 09 — Multi-Agent Systems

> **Part 2 — Pro (Modules 09–14)** · the first module of Part 2 · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 09](../../COURSE_OUTLINE.md#module-09--multi-agent-systems)

**Goals:** Know the current multi-agent patterns (subagents, handoffs, skills, router, custom workflow), what each one costs in model calls, tokens, and control, and how to pick one from requirements. Build the same system two ways and measure the difference. This module uses plain `create_agent` and LangGraph; Module 10 then shows what a full agent harness (Deep Agents) adds on top.

**Estimated time:** 1.5 weeks (about 9–11 hours of lessons plus 6–8 hours for the project).

## Welcome to Part 2 — Pro

Part 1 taught you to build agents, RAG systems and production-grade LangGraph workflows. **Part 2 makes them coordinated, long-running, multimodal, measured and deployed**: multi-agent systems (this module), Deep Agents (10), voice (11), testing and evaluation (12), a self-hosted production service (13) and, optionally, local models and fine-tuning (14). See the [Part 2 overview](../../COURSE_OUTLINE.md#part-2--pro-modules-0914).

What changes in Part 2:

- **Measure before you add.** Every module compares designs with numbers (model calls, tokens, latency, pass rate), not opinions. This module starts with a **single-agent baseline** and only then adds agents.
- **Systems, not cells.** Lessons reuse one domain across the module (here: the Orbita Cloud support desk) and the course package (`mastery.agents`) grows with tested building blocks.
- **Fewer hand-holding steps.** You know the notebook routine (Step 0, markers, Restart & Run All); lessons now spend that space on design decisions and pitfalls.

**Prerequisites (from Part 1)** — you should be comfortable with:

| You need | Where you learned it |
|---|---|
| `create_agent`, tools, `ToolRuntime`, streaming agents | Module 02 |
| Middleware (`@wrap_model_call`, `request.override`), `HumanInTheLoopMiddleware` | Module 04 |
| `mastery.rag` (load → split → BM25 / Chroma → retrieve) | Module 06 |
| `StateGraph`, reducers, `Command`, `Send` | Module 07 |
| Checkpointers, `interrupt()` / `Command(resume=...)`, subgraphs, `mastery.graphs.hitl.drive` | Module 08 |

**Before you move on from Part 1:** Projects 01–08 pass their acceptance checks and `python -m pytest -q` is green (see the [Module 08 wrap-up](../08-langgraph-production-features/README.md#part-1-complete)).

## Before you start this module

Run this **once**, in **Git Bash**, from the **repo root**, with the **`lc-mastery`** environment active (the prompt starts with `(lc-mastery)`).

```bash
cd ~/path/to/langchain-langgraph-mastery   # your clone; quote the path if it has spaces
conda activate lc-mastery
git pull                                   # get this module's files
rm -f src/mastery/agents.py                # Module 09 turns it into the package src/mastery/agents/ (see below)
python -m pip install -e ".[dev,embeddings]"   # re-run after every pull (Module 09 adds jupytext via the new [notebooks] extra, included in [dev])
python -m pip check                        # expect: No broken requirements found.  (not clean? Module 06 README, "Saw ERROR: pip's dependency resolver...")
python -m pytest -q                        # expect: "... passed" and no failures (offline, no keys)
python -c "import importlib.metadata as m; print('langchain', m.version('langchain'), '| langgraph', m.version('langgraph'), '| jupytext', m.version('jupytext'))"   # expect: langchain 1.4.x | langgraph 1.2.x | jupytext 1.19.x
python -c "import mastery.agents as a; print(a.__file__)"   # expect: ...src/mastery/agents/__init__.py
```

> **Why `rm -f src/mastery/agents.py`?** Until Module 08, `mastery.agents` was one file. It is now a package (`src/mastery/agents/`, with the old helpers in `loop.py` and re-exported, so `from mastery.agents import run_tool_loop` still works). If your pull still shows the old file, Python imports the package anyway (a package directory wins over a module of the same name), but delete the stale file so nobody edits the wrong one. If you pulled with Git, it is already gone and the command does nothing.

| | |
|---|---|
| 🔑 Keys | `GROQ_API_KEY` (optional: without it 💸 cells print `⏭️ Skipped` and an offline, rule-based support model stands in). **No new keys** |
| 💰 Cost | $0. Every pattern runs and is measured offline. LIVE cells use `gpt-oss-20b` on the Groq free tier: a few thousand tokens per cell; Project 09 LIVE ≈ 3–6k tokens per conversation per pattern (`LIVE_LIMIT` caps how many run) |
| 💾 Disk | Small: an ADR and JSON reports in `data/outputs/m09/` (git-ignored, < 1 MB); Project 09 LIVE builds a small Chroma index in `data/vectorstores/` (< 5 MB) |
| ⏱️ Free-tier note | Multi-agent patterns make **many** small calls. On the free tier you may hit the requests-per-minute limit; `get_model` retries `429`s, so a LIVE run is slower, not broken |
| ✅ Ready when | `pip check` is clean, `pytest` passes, the versions print and `mastery.agents` resolves to the package |

If `pip install` or `pytest` fails, see the [setup guide's troubleshooting](../00-foundations/00-02-create-course-env.md#troubleshooting).

## How to work through this module

1. **Do [Before you start this module](#before-you-start-this-module) first** (once per pull). Module 09 adds the package [`src/mastery/agents/`](../../src/mastery/agents/__init__.py) (`specialists`, `metrics`, `support`) and the support-desk data in [`data/samples/support-desk/`](../../data/samples/support-desk/).
2. **Start Jupyter from the repo root** (`jupyter lab` in Git Bash) and pick the **Python (lc-mastery)** kernel in every notebook.
3. **Go in order.** 09.01 measures a single-agent baseline and the patterns side by side; 09.02–09.04 build each pattern on the **same** support desk (subagents, handoffs, skills and router); 09.05 builds a custom workflow and writes the ADR. The project then compares handoffs vs subagents on 15 conversations.
4. **Read the cell markers.** 🧪 = offline (scripted or rule-based models, free) · 💸 = calls a model. **Restart & Run All** always completes without a key.
5. **Numbers are measured.** Offline counts (model calls) are exact and repeatable; offline tokens are estimates (4 characters ≈ 1 token, tool schemas included). LIVE numbers vary run to run; record them in your findings.
6. **Windows notes.** Nothing in this module starts servers or child processes. Jupytext commands run through `sys.executable -m jupytext`, so they use the kernel's environment even if `jupytext` isn't on your Git Bash `PATH`. Jupytext writes LF line endings; with `core.autocrlf=true` Git may warn `LF will be replaced by CRLF` for paired `.py` files, which is harmless.
7. **Before you commit:** *Kernel → Restart Kernel and Run All Cells…*, *Edit → Clear Outputs of All Cells*, save, then `python -m pytest -q`.

## Lessons

| Lesson | Title | Notebook | Time | Keys |
|---|---|---|---|---|
| 09.01 | Why (and when not) to go multi-agent | [`09-01-multi-agent-overview.ipynb`](09-01-multi-agent-overview.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 09.02 | Subagents (supervisor-style orchestration) | [`09-02-subagents.ipynb`](09-02-subagents.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 09.03 | Handoffs | [`09-03-handoffs.ipynb`](09-03-handoffs.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 09.04 | Skills and routers | [`09-04-skills-and-router.ipynb`](09-04-skills-and-router.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 09.05 | Custom workflows and choosing an architecture | [`09-05-custom-workflow-and-architecture.ipynb`](09-05-custom-workflow-and-architecture.ipynb) | 120–150 min | none |

**What each lesson gives you**

- **09.01:** the five patterns and the docs' model-call table, then the **same table measured** on the Orbita Cloud desk (one-shot, repeat request, multi-domain) including a single-agent baseline; a "do I need multi-agent?" checklist; runtime vs framework vs harness; the Jupyter skill (long-notebook layout, Jupytext pairing).
- **09.02:** specialists as tools, written by hand (the docs pattern) and with `subagent_tool`; isolated vs forked context (the "what's your customer ID?" bug and its fix); one `task` dispatch tool with an enum; an `interrupt()` inside a subagent pausing the outer agent; per-agent counts with `UsageMeter`; migrating from `langgraph-supervisor`.
- **09.03:** handoffs in one agent (middleware swaps prompt and tools by `current_step`) and as agent subgraphs (`Command(graph=Command.PARENT)`, `active_agent`); why the next turn skips triage; `carry="last"` vs `"turn"` (a measured ping-pong that hits the recursion limit); HITL refunds inside a handoff.
- **09.04:** skills (`load_skill`, progressive disclosure; prompt tokens measured with and without) and a router (classify → `Send` fan-out in parallel → join); stateless routing and where the customer ID comes from; keyword vs LLM classifier.
- **09.05:** Pattern C, a custom refund workflow (deterministic parse/validate/approve/issue + one agent node); embedding it in a router; all patterns on the 15-conversation test set in one table; an ADR template written to `data/outputs/m09/`; what a harness (Module 10) would add.

## Project

**[Project 09 — Multi-Agent Support Desk](project/README.md)**: Orbita Cloud (a fictional SaaS) gets a support desk built twice: **Pattern A** (handoffs: triage → billing / technical / account) and **Pattern B** (subagents: one coordinator calling the same specialists as tools). Shared FAQ search with `mastery.rag`, a billing-manager approval before any refund over $50, a 15-conversation test set, a measured comparison and an ADR with your recommendation.

| File | Use |
|---|---|
| [`project/README.md`](project/README.md) | Spec, test set, acceptance criteria, modes, stretch goals |
| [`project/09-project-support-desk.ipynb`](project/09-project-support-desk.ipynb) | **Starter** with four `# TODO`s (runs from day one, also offline) |
| [`project/solutions/09-project-support-desk-solution.ipynb`](project/solutions/09-project-support-desk-solution.ipynb) | **Reference solution** (open after trying) |
| [`data/samples/support-desk/`](../../data/samples/support-desk/) | FAQ (3 Markdown files), customers/invoices/service status, `conversations.jsonl` (the 15-conversation test set) |

## Jupyter skill in this module

**Organizing long notebooks + Jupytext pairing**:

| Skill | Where |
|---|---|
| A long notebook as **Parts** (`## Part N · ...` headings): the Table of Contents panel (*View → Table of Contents*) becomes a clickable outline; collapse a Part by clicking the blue bar left of its heading | every lesson; 09.01 explains it |
| One **comparison cell** at the end of a Part that prints a table, instead of scattered prints | 09.01, 09.05, Project 09 |
| **Jupytext pairing**: `jupytext --set-formats ipynb,py:percent nb.ipynb` keeps a `.py` twin (`# %%` cells) you can diff, grep and review; `jupytext --sync nb.ipynb` updates whichever is older | 09.01 Part 5 (on a copy in `data/outputs/m09/`) |
| Running a CLI from the kernel's environment: `subprocess.run([sys.executable, "-m", "jupytext", ...])` | 09.01 |

## `src/mastery` increment

| File | What it does | Tests |
|---|---|---|
| [`src/mastery/agents/__init__.py`](../../src/mastery/agents/__init__.py) | `mastery.agents` is now a **package**; re-exports the Module 02 helpers and the new building blocks | [`tests/unit/test_agents_m09.py`](../../tests/unit/test_agents_m09.py) + [`test_agents.py`](../../tests/unit/test_agents.py) (unchanged) |
| [`src/mastery/agents/loop.py`](../../src/mastery/agents/loop.py) | The old `mastery/agents.py` (Module 02: `run_tool_loop`, `execute_tool_calls`, `format_transcript`, ...), moved unchanged | [`test_agents.py`](../../tests/unit/test_agents.py) |
| [`src/mastery/agents/specialists.py`](../../src/mastery/agents/specialists.py) | `Specialist` (recipe → `create_agent`), `subagent_tool` (`context="query"/"history"`, `output="last"/"all"`), `task_tool` (enum dispatch), `handoff_tool` (`carry="last"/"turn"`) + `handoff_graph`, `step_tool` + `step_middleware` (single-agent handoffs), `HandoffState`, `StepState` | `test_agents_m09.py` |
| [`src/mastery/agents/metrics.py`](../../src/mastery/agents/metrics.py) | `UsageMeter`: a callback that counts model calls and tokens, in total and per agent (`lc_agent_name`), and times a `with` block | same |
| [`src/mastery/agents/support.py`](../../src/mastery/agents/support.py) | The Orbita Cloud desk: `SupportDesk` backend, `make_support_tools` (refunds over `REFUND_THRESHOLD` call `interrupt()`), `faq_search` (BM25 or Chroma), `make_specialists`, `build_single_agent_baseline` / `build_single_agent_desk` / `build_handoffs_desk` / `build_subagents_desk` / `build_router_desk`, `offline_model`, `load_conversations`, `run_conversation`, `score`, `evaluate` | same |

## Production notes

> ⚠️ **Production note: every agent is a bill.**
> A pattern's cost is model calls × tokens per call. Measured on this desk, subagents made **71** model calls for the 15 conversations, handoffs **53**, a single agent and a keyword router **36** each (09.01, 09.05). Add an agent when an eval says the simpler design fails, not because the diagram looks nicer.

> ⚠️ **Production note: one checkpointer, at the top.**
> Subagents and agent subgraphs should inherit the parent's checkpointer. Give the outermost graph the checkpointer and a `thread_id`; then an `interrupt()` three levels down still pauses and resumes the whole system (09.02, 09.03).

> ⚠️ **Production note: context is a design decision.**
> Decide per specialist what it sees (only a task, or the history) and what it returns (a final answer, or a transcript). Most multi-agent bugs in this module were context bugs: a missing customer ID, a lost tool result, a ping-pong between agents.

Each lesson has its own production notes; they are collected in [`docs/production-notes.md`](../../docs/production-notes.md).

## Research checkpoint

Re-read the [Multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent/index) overview and log in [`docs/research-log.md`](../../docs/research-log.md): **did the list of recommended patterns change** (on 2026-10-12: subagents, handoffs, skills, router, custom workflow), **did the model-call / token table change**, and **is `langgraph-supervisor` still "no longer actively maintained"** ([migration guide](https://docs.langchain.com/oss/python/migrate/langgraph-supervisor))? 09.05 ends with this prompt too.

## Status

✅ Built (docs verified 2026-10-12).

---

← [Module 08](../08-langgraph-production-features/README.md) · [Course outline](../../COURSE_OUTLINE.md) · [Module 10](../10-deep-agents/README.md) →
