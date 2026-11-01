# Module 11 · Use-case labs (choose 1 of 3)

> **Part 2 — Pro** · Module 11 · about 5–8 h · Do the lab after the lesson it names. The two you skip are ready-made capstone seeds.

Each lab is a **brief**, not a tutorial: a real problem, requirements, acceptance criteria and a stretch goal, with no starter notebook. Deciding how to structure the work is part of the exercise, as it is on the job. The full briefs are in the course outline; this page tells you how to start and how to know you're done.

| Lab | After | The problem | Grows into |
|---|---|---|---|
| [11A · Repo Cartographer](../../../COURSE_OUTLINE.md#lab-11a--repo-cartographer-codebase-analysis--refactor-planning) | Lesson 11.05 | Understand an unfamiliar codebase and plan a safe refactor, with every claim pointing at a real file and line | Capstone C6 (repo maintainer) |
| [11B · Sandboxed Data Analyst](../../../COURSE_OUTLINE.md#lab-11b--sandboxed-data-analyst) | Lesson 11.09 | Turn a raw CSV into a reproducible report with charts, without running model-written code on your machine | Capstone C4 (data-analyst variant) |
| [11C · Policy & Contract Review Desk](../../../COURSE_OUTLINE.md#lab-11c--policy--contract-review-desk-hitl-compliance-review) | Lesson 11.08 | Review documents against a checklist, with a person signing off before anything is approved | Capstone C6 (due-diligence pack) or C8 |

Pick the one closest to the work you want to be hired for.

## Where your files go

Do the lab in your `workspace/` ([setup/LEARNER_WORKFLOW.md](../../../setup/LEARNER_WORKFLOW.md)), for example `workspace/11-deep-agents/labs/11a-repo-cartographer/`:

- `lab.ipynb`: the runs, the evaluation and the results, top to bottom (Restart & Run All must pass);
- `README.md`: the problem in two sentences, how to run it, and each acceptance criterion with its measured value;
- any helper module the notebook imports, so cells stay short ([CONVENTIONS.md](../../../CONVENTIONS.md) §3).

## Start from what you built

| You need | Use | Lesson |
|---|---|---|
| A deep agent with the course defaults: model from settings, filesystem layout, secret deny rules, call budgets | `mastery.deep`: `build_deep_agent`, `course_backend`, `secret_deny_rules`, `budget_middleware` | 11.01–11.04 |
| Read-only inputs, writes only under `/reports/` | `deny_everything_else` plus your own allow rules | 11.04 |
| Subagents with small tool sets that return structured findings | subagent specs with `response_format` | 11.05 |
| A person approves before a risky tool runs | `interrupt_on` | 11.08 |
| Model-written code runs away from your machine | `mastery.deep.DockerSandbox` (`--network none`, no mounts, no secrets) | 11.09 |
| Evaluate the run, not just the final answer | `mastery.deep.evals`: `trajectory_matches`, `subagents_called`, `forbidden_calls`, `file_text`, `grounding` | 11.11 |
| Rates over several runs, with intervals | `mastery.evals`: `wilson_interval`, `summarize_repeats` | Module 10 |

## Before you call it done

- [ ] Every acceptance criterion in the brief has a **measured** value from at least three runs, with an interval wherever you report or compare a rate.
- [ ] The run stays inside a token budget you set and logged.
- [ ] Nothing was written outside the folders the brief allows (checked from the run's file operations, not assumed).
- [ ] The data is public or synthetic, as the brief requires on free tiers (their prompts may be read by human reviewers).
- [ ] Your README says what you would change before real users touch it.

← [Module 11 README](../README.md) · [Course outline](../../../COURSE_OUTLINE.md)
