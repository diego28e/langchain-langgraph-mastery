# Module 02 — Tools & Your First Agents

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 02](../../COURSE_OUTLINE.md#module-02--tools--your-first-agents)

**Goals:** Define good tools, understand the tool-calling loop, and build agents with `create_agent`, which replaces `create_react_agent` in v1.

**Estimated time:** 1.5 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 02.01 | Tools: definition, schemas, and docstrings that work | `02-01-defining-tools.ipynb` | 📝 Planned |
| 02.02 | Tool calling without an agent | `02-02-tool-calling-loop.ipynb` | 📝 Planned |
| 02.03 | `create_agent`: the agent harness | `02-03-create-agent.ipynb` | 📝 Planned |
| 02.04 | Tool runtime: state, context, store, stream writer | `02-04-tool-runtime-and-context.ipynb` | 📝 Planned |
| 02.05 | Structured agent output | `02-05-agent-structured-output.ipynb` | 📝 Planned |
| 02.06 | Streaming agents | `02-06-streaming-agents.ipynb` | 📝 Planned |
| 02.07 | Debugging agents in LangSmith Studio (first look) | `02-07-studio-first-look.ipynb` | 📝 Planned |

## Project

**Project 02 — Personal Finance Helper Agent**: An agent that answers questions about your own (sample) expense CSV with safe, deterministic tools.

Project files go in `project/`.

## Jupyter skill

Kernels, one env per course, `ipykernel` registration.

## `src/mastery` increment

`mastery/tools/` with reusable, tested tools (calculator, date utilities, CSV lookup).

## Research checkpoint

Read the "Migrate to `create_agent`" section of the [v1 migration guide](https://docs.langchain.com/oss/python/migrate/langchain-v1) and list 3 things that changed from `create_react_agent`. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 01](../01-models-messages-prompts/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 03](../03-memory-and-context/) →
