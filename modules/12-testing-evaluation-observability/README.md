# Module 12 — Testing, Evaluation & Observability

> **Part 2 — Pro (Modules 09–14)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 12](../../COURSE_OUTLINE.md#module-12--testing-evaluation--observability)

**Goals:** Make quality measurable. Unit-test agents without API calls, integration-test with real models, build LangSmith datasets and evaluators (code, LLM-as-judge, pairwise, trajectory), monitor production with online evaluators, and close the loop with feedback.

**Estimated time:** 2 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 12.01 | Testing strategy for LLM apps | `12-01-testing-strategy.ipynb` | 📝 Planned |
| 12.02 | Observability in depth | `12-02-observability.ipynb` | 📝 Planned |
| 12.03 | Datasets and offline experiments | `12-03-datasets-and-experiments.ipynb` | 📝 Planned |
| 12.04 | Evaluators: code, LLM-as-judge, pairwise | `12-04-evaluators.ipynb` | 📝 Planned |
| 12.05 | Agent evals: trajectories and multi-turn | `12-05-agent-trajectory-evals.ipynb` | 📝 Planned |
| 12.06 | Production monitoring: online evals, feedback, annotation queues | `12-06-online-evaluation-and-feedback.ipynb` | 📝 Planned |
| 12.07 | Prompt management with the Prompt & Context Hub | `12-07-prompt-hub.ipynb` | 📝 Planned |

## Project

**Project 12 — Eval Suite + CI for a Previous Agent**: Turn one earlier project (06, 08, 09, or 10) into an evaluated, regression-tested system.

Project files go in `project/`.

## Jupyter skill

`nbstripout` + headless notebook execution as a smoke test.

## `src/mastery` increment

`mastery/evals/` (shared evaluators, dataset builders) + `tests/unit/`, `tests/integration/`.

## Research checkpoint

Check [Usage and billing](https://docs.langchain.com/langsmith/usage-and-billing) for current free-tier trace limits and retention. Log how many eval runs per week you can afford. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 11](../11-multimodal-and-voice/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 13](../13-production-and-deployment/) →
