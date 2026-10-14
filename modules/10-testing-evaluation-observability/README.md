# Module 10 — Testing, Evaluation & Observability

> **Part 2 — Pro (Modules 09–14)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 10](../../COURSE_OUTLINE.md#module-10--testing-evaluation--observability)

**Goals:** Make quality measurable, starting from how *your* system actually fails rather than from generic metrics. Read traces and build a failure taxonomy; instrument with LangSmith and OpenTelemetry; build versioned datasets from traces, failure categories, and reviewed synthetic data, with a held-out split; write code evaluators and binary LLM judges that you have checked against your own labels; report every result with a confidence interval over repeated runs; evaluate agent trajectories and reliability (pass^k); monitor production with online evaluators and feedback; and gate CI on evals with thresholds and cost budgets.

**Estimated time:** about 30–40 h (8 lessons + project; ≈ 4–5 weeks at 8 h/week). The module is planned; the estimate will be recalibrated when the notebooks are built.

**Why error analysis comes first:** a "helpfulness 1–5" score rarely matches the ways your system fails. Reading 50–100 traces and naming the failures tells you which evaluators to build, which failures are plain bugs to fix, and where your time goes. Every later lesson builds on the taxonomy you write in Lesson 10.01, and every comparison uses the statistics kit `mastery.evals.stats` from Module 01 (confidence intervals, paired comparisons, repeated-run summaries).

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 10.01 | Error analysis first: read traces, build a failure taxonomy | `10-01-error-analysis.ipynb` | 📝 Planned |
| 10.02 | Observability in depth: LangSmith and OpenTelemetry | `10-02-observability.ipynb` | 📝 Planned |
| 10.03 | Datasets and offline experiments, with honest statistics | `10-03-datasets-and-experiments.ipynb` | 📝 Planned |
| 10.04 | Evaluators and LLM-as-judge done right | `10-04-evaluators.ipynb` | 📝 Planned |
| 10.05 | Agent evals: trajectories, multi-turn, and reliability | `10-05-agent-trajectory-evals.ipynb` | 📝 Planned |
| 10.06 | Production monitoring: online evals, feedback, annotation queues | `10-06-online-evaluation-and-feedback.ipynb` | 📝 Planned |
| 10.07 | Prompt management with the Prompt & Context Hub | `10-07-prompt-hub.ipynb` | 📝 Planned |
| 10.08 | Testing strategy, eval gates, and CI | `10-08-testing-and-ci-gates.ipynb` | 📝 Planned |

What runs through the lessons:

- **Judges done right (10.04):** one binary pass/fail judge per failure category, with labelled examples in its prompt, checked against your own labels as a true positive rate and a true negative rate, and re-checked whenever its model or prompt changes. The same rules (calibration, thresholds, an abstain band that escalates to a human) apply to every classifier: guards, routers, judges.
- **Statistics for small evals (10.03, 10.05):** repeated runs, bootstrap and Wilson intervals, paired comparisons, and pass@k vs pass^k for agents. "No detectable difference" is a valid result.
- **Gates (10.08):** CI fails when the lower bound of a pass rate drops below its threshold, when any item of the red-team suite (the Modules 04–05 attacks, kept as a standing eval) regresses, or when cost per run exceeds its budget.

## Production notes

> ⚠️ **Production note: small eval sets only detect big differences, and a judge is a model too.**
> The course runs 30–100-example suites a few times on free or cheap models, because that is what a learner can afford. With 60 pass/fail items and a pass rate around 80%, a 95% interval is roughly ±10 points, so smaller "improvements" are noise unless you use paired comparisons or more data. **In production:** grow datasets continuously from production failures (Lesson 10.06), stratify them by failure category, keep a frozen held-out set, re-check every judge on fresh labels whenever its model or prompt changes and on a schedule, and report each judge's TPR/TNR next to the metrics it produces.

## Project

**Project 10 — Error-Analysis Story: Eval Suite + CI Gate for a Previous Agent**: turn one earlier project (06, 07, 08, or 09) into an evaluated, regression-tested system, and tell it as a story with numbers. Read ≥ 100 traces and build a failure taxonomy → fix the top two failure categories → measure before vs after on a held-out split with confidence intervals → gate CI on the result, and show that a deliberately broken commit is blocked.

Project files go in `project/`.

## Jupyter skill

`nbstripout` + headless notebook execution as a smoke test.

## `src/mastery` increment

`mastery/evals/` grows from the `stats` module of Module 01: `taxonomy.py` (open-coding label sheets, category counts, frequency × severity), `datasets.py` (builders from traces and failure categories, dev/test splits, version tags), `judges.py` (binary judge factory with few-shot examples, TPR/TNR check against your labels, corrected pass rates), and `gates.py` (CI thresholds on confidence bounds, red-team regressions, cost budgets) + `tests/unit/`, `tests/integration/`.

## Research checkpoint

Check [Usage and billing](https://docs.langchain.com/langsmith/usage-and-billing) for current free-tier trace limits and retention, and log how many eval runs per week you can afford. Then check the status of the [OTel GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai) and log whether the attribute names you used changed. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 09](../09-multi-agent-systems/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 11](../11-deep-agents/) →
