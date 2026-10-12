# Module 01 — Models, Messages & Prompts

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 01](../../COURSE_OUTLINE.md#module-01--models-messages--prompts)

**Goals:** Master the model layer that everything else stands on: chat model interfaces, messages and content blocks, multimodal input, structured output, streaming and batching, token and cost awareness. Understand Runnables and LCEL well enough to read older code and the internals.

**Estimated time:** 1.5–2 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 01.01 | Chat models and `init_chat_model` | `01-01-chat-models.ipynb` | 📝 Planned |
| 01.02 | Messages and standard content blocks | `01-02-messages-and-content-blocks.ipynb` | 📝 Planned |
| 01.03 | Prompting fundamentals for open-weight models | `01-03-prompting-fundamentals.ipynb` | 📝 Planned |
| 01.04 | Structured output you can trust | `01-04-structured-output.ipynb` | 📝 Planned |
| 01.05 | Streaming, batching, and async basics | `01-05-streaming-and-batching.ipynb` | 📝 Planned |
| 01.06 | Tokens, cost, and rate limits | `01-06-tokens-cost-rate-limits.ipynb` | 📝 Planned |
| 01.07 | Under the hood: Runnables and LCEL (legacy-aware) | `01-07-runnables-and-lcel.ipynb` | 📝 Planned |
| 01.08 | First look at LangSmith tracing | `01-08-first-traces.ipynb` | 📝 Planned |

## Project

**Project 01 — Multi-Model Comparison Lab**: A reusable notebook that runs one task across several models and returns validated, structured verdicts.

Project files go in `project/`.

## Jupyter skill

Magics (`%pip`, `%env`, `%%time`) and rich display.

## `src/mastery` increment

`mastery/models.py`: `get_model(role="fast"|"reasoning"|"vision", provider="groq")` reads model IDs from config, never hard-coded across notebooks.

## Research checkpoint

Find which providers currently support standard `content_blocks` natively and whether `langchain-groq` is now one of them. Log it. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 00](../00-foundations/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 02](../02-tools-and-agents/) →
