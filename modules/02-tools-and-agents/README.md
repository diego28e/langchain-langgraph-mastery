# Module 02 — Tools & Your First Agents

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 02](../../COURSE_OUTLINE.md#module-02--tools--your-first-agents)
> Docs verified: **2026-10-12**

**Goals:** Define good tools, understand the tool-calling loop by writing it yourself, and build agents with `create_agent`, which replaces `create_react_agent` in v1. Give tools runtime context safely, return structured answers, stream progress, and debug runs in LangSmith Studio.

**Estimated time:** 1.5 weeks (about 12–15 hours of lessons plus 4–6 hours for the project).

## Before you start this module

Run this **once**, in **Git Bash**, from the **repo root**, with the **`lc-mastery`** environment active (the prompt starts with `(lc-mastery)`).

```bash
cd ~/path/to/langchain-langgraph-mastery   # your clone; quote the path if it has spaces
conda activate lc-mastery
git pull                                   # get this module's files
python -m pip install -e ".[dev]"          # re-run after every pull: new modules add packages
python -m pytest -q                        # expect: "... passed" and no failures (offline, no keys)
langgraph --version                         # expect: LangGraph CLI, version 0.4.33 (or newer)
```

| | |
|---|---|
| 🔑 Keys | `GROQ_API_KEY` (optional, 💸 cells skip without it). `LANGSMITH_API_KEY` (optional, free) for Studio in Lesson 02.07. |
| 💰 Cost | $0 on the Groq and LangSmith free tiers. |
| 📦 Optional extras | None: `langgraph-cli[inmem]` (Studio) is already in `[dev]`. |
| ✅ Ready when | `pytest` shows no failures and `langgraph --version` prints a version. |

If `pip install` or `pytest` fails, see the [setup guide's troubleshooting](../00-foundations/00-02-create-course-env.md#troubleshooting) (SSL certificate errors on Anaconda: Step 4b).

## How to work through this module

1. **Do [Before you start this module](#before-you-start-this-module) first** (once per pull). Module 02 adds `mastery.tools`, `mastery.agents` and `mastery.testing`. The `[dev]` extra now also installs `langgraph-cli[inmem]` (new `studio` extra) for Lesson 02.07
2. **Start Jupyter from the repo root** and pick the **Python (lc-mastery)** kernel in every notebook. Lesson 02.01 explains why that matters and how to fix "module not found".
3. **Go in order.** 02.02 writes the loop by hand; 02.03 replaces it with `create_agent`; 02.04–02.06 add context, structured output and streaming; 02.07 opens the same kind of agent in Studio. The project uses all of it.
4. **Read the cell markers.** 🧪 = offline (scripted model, free) · 🌐 = network, no tokens · 💸 = calls a model (free-tier quota). Every concept is shown first with `mastery.testing.ScriptedChatModel`, so you see the mechanics of the loop exactly, then live.
5. **No key? Still works.** Every 💸 cell checks `HAVE_GROQ_KEY` and prints `⏭️ Skipped`, so **Restart & Run All** always completes. The project has a full OFFLINE DEMO mode.
6. **Before you commit:** *Kernel → Restart Kernel and Run All Cells…*, *Edit → Clear Outputs of All Cells*, save, then `python -m pytest -q`.

## Lessons

| Lesson | Title | Notebook | Time | Keys |
|---|---|---|---|---|
| 02.01 | Tools: definition, schemas, and docstrings that work | [`02-01-defining-tools.ipynb`](02-01-defining-tools.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 02.02 | Tool calling without an agent | [`02-02-tool-calling-loop.ipynb`](02-02-tool-calling-loop.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 02.03 | `create_agent`: the agent harness | [`02-03-create-agent.ipynb`](02-03-create-agent.ipynb) | 120–150 min | `GROQ_API_KEY`, `LANGSMITH_API_KEY` (optional) |
| 02.04 | Tool runtime: state, context, store, stream writer | [`02-04-tool-runtime-and-context.ipynb`](02-04-tool-runtime-and-context.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 02.05 | Structured agent output | [`02-05-agent-structured-output.ipynb`](02-05-agent-structured-output.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 02.06 | Streaming agents | [`02-06-streaming-agents.ipynb`](02-06-streaming-agents.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 02.07 | Debugging agents in LangSmith Studio (first look) | [`02-07-studio-first-look.ipynb`](02-07-studio-first-look.ipynb) + [`studio/`](studio/) | 60–90 min | `GROQ_API_KEY`, LangSmith login |

**What each lesson gives you**

- **02.01:** the **Jupyter kernel skill** (below); what the model actually receives from `@tool` (`convert_to_openai_tool`); names, descriptions and `parse_docstring=True`; Pydantic argument schemas with enums and bounds, and validation errors before your code runs; the reserved names `config` and `runtime`; return values and `content_and_artifact`; vague vs specific descriptions (a live tool-picking test); a tour of `mastery.tools` and why the calculator never uses `eval`.
- **02.02:** `bind_tools` and what it sends; reading `tool_calls`, `invalid_tool_calls` and `finish_reason`; `tool_choice` (auto, required/any, by name) as `ChatGroq` translates it; GPT-OSS on Groq makes **one tool call per turn**; message-ordering rules for `ToolMessage`; the loop written by hand with a stop condition and a step limit; turning bad tool calls into error messages; Groq's server-side `browser_search` (`bind_tools` rejects it, `.bind()` sends it); the `ChatOpenAI` fallback pointed at Groq's OpenAI-compatible URL.
- **02.03:** `create_agent(model, tools, system_prompt=...)`; the `model` ⇄ `tools` graph and its stop condition; why the default recursion limit doesn't protect you (we measured 5,000 model calls before it stopped) and how to set `recursion_limit` and `ModelCallLimitMiddleware`; `state_schema` (`AgentState`), `@dynamic_prompt`, model routing with `@wrap_model_call`; a `create_react_agent` → `create_agent` migration table.
- **02.04:** `ToolRuntime` (context, state, store, stream writer, ids) invisible to the model; typed `context_schema` + `invoke(context=...)`; state updates with `Command`; `InMemoryStore`; which tool failures crash a run by default; `ToolErrorMiddleware` with sanitized messages, `ToolRetryMiddleware`, `wrap_tool_call` permission rules, `ToolCallLimitMiddleware`; seven tool security rules.
- **02.05:** `response_format` and `structured_response`; `ToolStrategy` vs `ProviderStrategy` and what a bare schema picks (`ProviderStrategy` on Groq, which **fails with tools**: use `ToolStrategy`); `handle_errors` for validation errors and multiple answers; answer-or-refusal unions.
- **02.06:** `stream_mode` `updates` / `messages` / `custom` and `version="v2"` parts; token filtering by node; tool-call chunks; `mastery.agents.format_stream_part`; the new `stream_events(version="v3")` API (marked experimental); `astream` with top-level `async for`.
- **02.07:** what `langgraph dev` and Studio are; `langgraph.json`; starting the server from Git Bash; a guided tour (graph, steps, state, forks, hot reload); calling the same server with `langgraph_sdk`; Windows troubleshooting.

## Project

**[Project 02 — Personal Finance Helper Agent](project/README.md)**: an agent over a synthetic expense log (July–September 2026, COP) with four deterministic tools plus the calculator, a validated `FinanceAnswer` (`ToolStrategy`), streamed tool calls, traces in `m02-finance-agent`, and a 10-question evaluation with a "no arithmetic by the LLM" check and a refusal test.

| File | Use |
|---|---|
| [`project/README.md`](project/README.md) | Spec, the 10 questions with expected answers, acceptance criteria, modes, stretch goals |
| [`project/02-project-personal-finance-agent.ipynb`](project/02-project-personal-finance-agent.ipynb) | **Starter** with six `# TODO`s (runs from day one, also offline) |
| [`project/solutions/02-project-personal-finance-agent-solution.ipynb`](project/solutions/02-project-personal-finance-agent-solution.ipynb) | **Reference solution** (open after trying) |

Data: [`data/samples/expenses/`](../../data/samples/expenses/) (`expenses-2026.csv`, 128 rows, and illustrative static `fx-rates.json`). Lessons 02.01 and 02.07 also use it.

## Jupyter skill in this module

**Kernels, one environment per course, `ipykernel` registration** (Lesson 02.01, Part 1):

| Skill | Where |
|---|---|
| A notebook runs in a **kernel**; the kernel is a Python from one environment. Check it with `sys.executable` / `sys.prefix` | 02.01 |
| One environment per course (`lc-mastery`), registered once with `python -m ipykernel install --user --name lc-mastery --display-name "Python (lc-mastery)"` | 02.01 (recap of 00.02 Step 6) |
| Listing kernelspecs (`jupyter kernelspec list`, `KernelSpecManager`) and removing stale ones | 02.01 |
| Fixing `ModuleNotFoundError`: install with `%pip` / `python -m pip` into **the kernel's** env, or switch kernel; never "pip from somewhere else" | 02.01, 02.07 (CLI in the same env) |
| Top-level `async for` in a cell vs `asyncio.run` in scripts | 02.06 |

## `src/mastery` increment

| File | What it does | Tests |
|---|---|---|
| [`src/mastery/tools/calculator.py`](../../src/mastery/tools/calculator.py) | `safe_eval` (AST allow-list, no `eval`, length/exponent/magnitude limits) and the `calculator` tool | [`tests/unit/test_tools.py`](../../tests/unit/test_tools.py) |
| [`src/mastery/tools/dates.py`](../../src/mastery/tools/dates.py) | `get_today`, `days_between`, `add_days` tools; `parse_date`, `parse_month`, `month_bounds`; `set_today` for reproducible tests | [`tests/unit/test_tools.py`](../../tests/unit/test_tools.py) |
| [`src/mastery/tools/csv_lookup.py`](../../src/mastery/tools/csv_lookup.py) | `CsvTable` and `make_csv_lookup_tool(table, ...)`: a lookup tool bound to ONE file, column enum, capped results, rows as artifact | [`tests/unit/test_tools.py`](../../tests/unit/test_tools.py) |
| [`src/mastery/agents/loop.py`](../../src/mastery/agents/loop.py) (imported as `mastery.agents`) | `execute_tool_calls`, `run_tool_loop` (the 02.02 loop, tested), `format_transcript`, `agent_stats`, `format_stream_part` | [`tests/unit/test_agents.py`](../../tests/unit/test_agents.py) |
| [`src/mastery/testing.py`](../../src/mastery/testing.py) | `ScriptedChatModel`: an offline chat model that supports `bind_tools` and streams tool calls (LangChain's fakes don't) | [`tests/unit/test_agents.py`](../../tests/unit/test_agents.py) |

## Research checkpoint

Read the "Migrate to `create_agent`" section of the [v1 migration guide](https://docs.langchain.com/oss/python/migrate/langchain-v1) and list 3 things that changed from `create_react_agent`. Every lesson also ends with its own short research task. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

✅ **Built** (2026-10-12). Every notebook passes Restart & Run All without keys (💸 cells skip) and against a local Groq stand-in (maintainer QA); the Studio app was started with `langgraph dev` and called through `langgraph_sdk` against the same stand-in. Live calls are verified by the learner at each checkpoint.

---

← [Module 01](../01-models-messages-prompts/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 03](../03-memory-and-context/) →
