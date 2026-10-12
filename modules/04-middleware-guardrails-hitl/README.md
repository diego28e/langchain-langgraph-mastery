# Module 04 — Middleware, Guardrails & Human-in-the-Loop

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 04](../../COURSE_OUTLINE.md#module-04--middleware-guardrails--human-in-the-loop)

**Goals:** Use middleware, the defining feature of `create_agent`, to add reliability, safety, and human oversight without rewriting the agent loop. Understand prompt injection and tool security.

**Estimated time:** 1.5–2 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 04.01 | Middleware mental model and hooks | `04-01-middleware-overview.ipynb` | 📝 Planned |
| 04.02 | Prebuilt middleware tour | `04-02-prebuilt-middleware.ipynb` | 📝 Planned |
| 04.03 | Writing custom middleware | `04-03-custom-middleware.ipynb` | 📝 Planned |
| 04.04 | Guardrails: PII, content policy, output validation | `04-04-guardrails.ipynb` | 📝 Planned |
| 04.05 | Prompt injection and tool security | `04-05-prompt-injection-and-tool-security.ipynb` | 📝 Planned |
| 04.06 | Human-in-the-loop for agents | `04-06-human-in-the-loop.ipynb` | 📝 Planned |

## Production notes

> ⚠️ **Production note: the safety classifiers in 04.04–04.05 are Groq preview models.**
> `openai/gpt-oss-safeguard-20b` and `meta-llama/llama-prompt-guard-2-*` can be retired at short notice. In production: never let one classifier be your only defence. Layer deterministic rules, a classifier, least-privilege tools, and human approval. Decide what happens when the classifier is down (usually: fail closed for risky actions). Pin the model ID, monitor its error rate, and keep a fallback classifier.

## Project

**Project 04 — Safe Email-Triage Agent**: An agent that reads a (fake) inbox, drafts replies, and only "sends" after human approval.

Project files go in `project/`.

## Jupyter skill

Debugging (`%debug`, `%pdb`, reproducible failing cells).

## `src/mastery` increment

`mastery/middleware/`: token-budget guard, audit logger, role-based tool filter.

## Research checkpoint

List the current prebuilt middleware on the [Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) page and log one that did not exist when this course was written. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 03](../03-memory-and-context/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 05](../05-mcp-and-external-tools/) →
