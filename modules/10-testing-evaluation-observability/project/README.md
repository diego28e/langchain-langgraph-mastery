# Project 10 — Pre-release Gate and Error-Analysis Report for the Support Desk

> **Module 10 · Testing, Evaluation & Observability** · ⏱️ 6–8 hours · Docs verified 2026-10-15

**The job:** the Orbita Cloud support desk from Project 09 is in production, and support leads say it "feels flaky". Before the next release you do what an eval engineer does: read the traces, name the failures, check the judges you would automate, fix the top two causes, prove the fix, run the release gate (which must also block a known-bad build) and write the release report your lead will read.

| File | What it is |
|---|---|
| [`10-project-release-gate.ipynb`](10-project-release-gate.ipynb) | **Starter.** Runs top to bottom from the start. Five `# TODO` blocks, each with a collapsed goal-style hint |
| [`solutions/10-project-release-gate-solution.ipynb`](solutions/10-project-release-gate-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried |
| [`src/mastery/agents/release_suite.py`](../../../src/mastery/agents/release_suite.py) | The frozen release suite (105 cases), the red team (7 attacks), `Candidate`, `run_suite` |
| [`src/mastery/evals/release_gate.py`](../../../src/mastery/evals/release_gate.py) | `evaluate_release`, `write_baseline` and the CLI that CI runs |
| [`data/samples/support-desk/release-baseline.json`](../../../data/samples/support-desk/release-baseline.json) | The shipped desk's baseline thresholds |
| [`.github/workflows/eval-gate.yml`](../../../.github/workflows/eval-gate.yml) | The same gate on pull requests (Lesson 10.08) |

Outputs go to the git-ignored `data/outputs/m10/`: `project10-labels.csv`, `project10-release-report.md`, `project10-acceptance.json`.

## Requirements

1. **Error analysis:** label ≥ 100 of the 200 production traces with a category and a note, agreeing ≥ 90% with an independent reviewer.
2. **Taxonomy:** every label defined (definition, example, not this, severity 1–5, action) and ranked by frequency × severity; name the top two.
3. **Judges:** TPR and TNR of the `stopped_at_lookup` and `dropped_request` judges on the judge-test split, and a trust decision (TNR lower bound ≥ 85% and TPR ≥ 80%).
4. **Fix:** a `preprocess(message, desk)` that cuts each top-two category by ≥ 50% on the frozen release suite **and** on a held-out suite, wins the paired comparison, and adds no new failure (red team intact).
5. **Gate:** the fixed desk passes this release's bar (pass-rate lower bound ≥ 70%, pass^3 ≥ 75%, red team, cost); the fix **without** the signed-in customer context is blocked.
6. **Report:** a Markdown release report with **Decision**, **Error analysis**, **Judges**, **Before / after**, **Release gate** and **Risks and next steps**, every number formatted from the measured objects.

| TODO | Where | What |
|---|---|---|
| 1 | Step 2 | `label_trace(trace) -> (category, note)` |
| 2 | Step 3 | `TAXONOMY` and `TOP_TWO` |
| 3 | Step 4 | `validate_judges` and `TRUST` |
| 4 | Step 5 | `fix(message, desk)` |
| 5 | Step 7 | `write_report(path)` |

## Acceptance checks

The notebook ends with 9 checks. All fail on the untouched starter (0/9), and none passes with a shortcut:

- labels are compared with an independent reviewer, and `label_trace` must not read the generator's answer key (`want`) or call the reference labeller;
- the top two are recomputed from the reviewer's labels with your severities;
- judge confusion counts are recomputed on judge-test with your labels;
- the fix is also measured on a held-out suite it has never seen, so special-casing suite messages fails;
- the report must carry the measured pass^3 numbers and a decision that matches the gates.

## Modes

Everything runs **offline** (the rule-based `offline_model` desk and scripted judges), so Restart & Run All always completes at $0. With `GROQ_API_KEY`, Step 8 re-measures 10 cases × 3 runs on `gpt-oss-20b` for both desks (≈ 150–200 calls; spread it over time on the free tier) and prints the mean and the worst run.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Labels | Reviewer-checked labels, without reading the answer key | A short note on the traces you labelled differently from the reviewer, and why |
| Prioritization | Top two failure categories recomputed from your labels and severities | A sensitivity check: does the top two change if one severity changes? |
| Judge | Confusion counts recomputed on judge-test | The `dropped_request` judge tightened on judge-dev and re-measured once (stretch) |
| Fix and gate | The fix holds on the held-out suite; the report carries measured pass^3 and a matching decision | A new baseline recorded after approval, with the PR's eval-gate run linked |
| Hygiene | All 9 checks pass; Restart & Run All in both modes; outputs cleared | Your report says what the gate cannot detect at this sample size |

## Stretch

- Make the `dropped_request` judge trustworthy: read its false positives on judge-dev, tighten the definition, re-measure once on judge-test.
- After approval, record a new baseline with your fix merged (`python -m mastery.evals.release_gate --write-baseline`) and open a PR so `eval-gate.yml` runs.
- Fix the third category and show whether the difference is detectable.
