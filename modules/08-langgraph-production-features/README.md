# Module 08 — LangGraph Production Features

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 08](../../COURSE_OUTLINE.md#module-08--langgraph-production-features)

**Goals:** Master what makes LangGraph a runtime: persistence, durable execution, interrupts, time travel, subgraphs, streaming, fault tolerance, and long-term stores.

**Estimated time:** 2 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 08.01 | Persistence and checkpointers in depth | `08-01-persistence.ipynb` | 📝 Planned |
| 08.02 | Durable execution and fault tolerance | `08-02-durable-execution-and-fault-tolerance.ipynb` | 📝 Planned |
| 08.03 | Interrupts and human-in-the-loop (graph level) | `08-03-interrupts.ipynb` | 📝 Planned |
| 08.04 | Time travel: replay and fork | `08-04-time-travel.ipynb` | 📝 Planned |
| 08.05 | Subgraphs | `08-05-subgraphs.ipynb` | 📝 Planned |
| 08.06 | Streaming in depth | `08-06-streaming.ipynb` | 📝 Planned |
| 08.07 | Long-term memory store inside graphs | `08-07-stores-in-graphs.ipynb` | 📝 Planned |

## Project

**Project 08 — Research-and-Write Agent with Human Approval**: A durable, interruptible research assistant that plans, researches, drafts, and waits for your approval.

Project files go in `project/`.

## Jupyter skill

Live-updating displays for streams and interrupt/resume cells.

## `src/mastery` increment

`mastery/graphs/hitl.py` (reusable approval node + resume helpers).

## Research checkpoint

Read [Backward compatibility](https://docs.langchain.com/oss/python/langgraph/backward-compatibility) and log what happens to in-flight runs when you change a graph. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 07](../07-langgraph-fundamentals/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 09](../09-multi-agent-and-deep-agents/) →
