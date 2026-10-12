# Module 11 — Testing, Evaluation & Observability

> **Part 2 — Pro (Modules 09–13)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 11](../../COURSE_OUTLINE.md#module-11--testing-evaluation--observability)

**Goals:** Make quality measurable. Unit-test agents without API calls, integration-test with real models, build LangSmith datasets and evaluators (code, LLM-as-judge, pairwise, trajectory), monitor production with online evaluators, and close the loop with feedback.

**Estimated time:** 2 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 11.01 | Testing strategy for LLM apps | `11-01-testing-strategy.ipynb` | 📝 Planned |
| 11.02 | Observability in depth | `11-02-observability.ipynb` | 📝 Planned |
| 11.03 | Datasets and offline experiments | `11-03-datasets-and-experiments.ipynb` | 📝 Planned |
| 11.04 | Evaluators: code, LLM-as-judge, pairwise | `11-04-evaluators.ipynb` | 📝 Planned |
| 11.05 | Agent evals: trajectories and multi-turn | `11-05-agent-trajectory-evals.ipynb` | 📝 Planned |
| 11.06 | Production monitoring: online evals, feedback, annotation queues | `11-06-online-evaluation-and-feedback.ipynb` | 📝 Planned |
| 11.07 | Prompt management with the Prompt & Context Hub | `11-07-prompt-hub.ipynb` | 📝 Planned |

## Project

**Project 11 — Eval Suite + CI for a Previous Agent**: Turn one earlier project (06, 08, or 09) into an evaluated, regression-tested system.

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

← [Module 10](../10-multimodal-and-voice/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 12](../12-production-and-deployment/) →
