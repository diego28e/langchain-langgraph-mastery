# Module 03 — Memory & Context Engineering

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 03](../../COURSE_OUTLINE.md#module-03--memory--context-engineering)

**Goals:** Give agents short-term memory (threads and checkpointers), manage long conversations (trim, delete, summarize), add long-term memory (stores), and treat context as something you engineer on purpose.

**Estimated time:** 1.5 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 03.01 | Memory concepts: short-term vs long-term | `03-01-memory-concepts.ipynb` | 📝 Planned |
| 03.02 | Short-term memory with checkpointers and threads | `03-02-short-term-memory.ipynb` | 📝 Planned |
| 03.03 | Long conversations: trim, delete, summarize | `03-03-managing-long-conversations.ipynb` | 📝 Planned |
| 03.04 | Long-term memory with stores | `03-04-long-term-memory.ipynb` | 📝 Planned |
| 03.05 | Context engineering | `03-05-context-engineering.ipynb` | 📝 Planned |

## Project

**Project 03 — Study Buddy with Memory**: A tutoring agent that remembers the learner across sessions.

Project files go in `project/`.

## Jupyter skill

`%autoreload` for developing `src/mastery` live.

## `src/mastery` increment

`mastery/memory.py`: checkpointer/store factory (in-memory for tests, SQLite for notebooks).

## Research checkpoint

Compare the memory row of the [feature comparison table](https://docs.langchain.com/oss/python/concepts/products) for LangChain, LangGraph, and Deep Agents. Log which you would pick for a 3-month-long user relationship, and why. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 02](../02-tools-and-agents/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 04](../04-middleware-guardrails-hitl/) →
