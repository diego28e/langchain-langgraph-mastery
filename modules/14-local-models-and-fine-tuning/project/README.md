# Project 14 — Local-First Support Assistant and Ticket Router

> **Module 14 · Local Models & Fine-Tuning** · elective · ⏱️ 4–6 hours · Docs verified 2026-10-16

**The job:** Orbita Cloud's support lead asks two questions before anything touches customer tickets: *can the documentation assistant run on our own laptops?*, and *which ticket router should we deploy, and was fine-tuning worth it?* You answer both with measured numbers on held-out data, paired comparisons, a latency budget and a privacy column, and write the recommendation.

| File | What it is |
|---|---|
| [`14-project-local-first-router.ipynb`](14-project-local-first-router.ipynb) | **Starter.** Runs top to bottom from the start. Five `# TODO` blocks, each with a collapsed goal-style hint |
| [`solutions/14-project-local-first-router-solution.ipynb`](solutions/14-project-local-first-router-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried |
| [`data/samples/local/`](../../../data/samples/local/) | The 900 router tickets (14.03) and the recorded runs: few-shot `qwen3:0.6b`/`qwen3:4b`, the CPU LoRA run, and `qwen3:4b` on the 16 golden questions |
| `data/outputs/m14/fewshot-groq.json` · `qlora-predictions.json` | **Yours**, from Lesson 14.03's 💸 cell and the 14.04 Colab notebook; added automatically when present |
| [`src/mastery/finetune/`](../../../src/mastery/finetune/) · [`src/mastery/local/`](../../../src/mastery/local/) | Dataset, baselines, metrics, recorded runs (14.03–14.04); Ollama status and models (14.01) |

Outputs go to the git-ignored `data/outputs/m14/`: `project14-report.md` and `project14-acceptance.json`.

## Requirements

1. **Assistant:** 16 Project 06 questions (12 answerable, 4 to decline) with the same BM25 context for every reader: the offline extractive reader, a local Ollama reader (live, or the recorded `qwen3:4b` run) and, with a key, Groq's `gpt-oss-20b`. Accuracy with 95% CIs, seconds per question, cost and whether data leaves the machine; one paired comparison.
2. **Router:** every router from 14.03–14.04 on the 234 held-out tickets (split by template family): numpy baselines, few-shot local, few-shot hosted (your 100-ticket Groq run), fine-tuned (the course's CPU LoRA and your Colab QLoRA). Accuracy CI, macro-F1, Spanish, seconds per ticket, USD per 1K tickets, local or not.
3. **Paired tests:** each tuned model against its few-shot base and against few-shot `qwen3:4b`.
4. **Decision:** the router to deploy under Orbita's constraints (tickets stay on the machine, ≤ 0.5 s per ticket on a support laptop), and whether fine-tuning was worth it, citing the paired result.
5. **Report:** Markdown with Assistant, Router, Comparisons, Recommendation, and Privacy and costs.

| TODO | Where | What |
|---|---|---|
| 1 | Step 2 | `score_reader(answers)`: right answers and correct refusals |
| 2 | Step 3 | `router_row(...)`: one router's quality, latency, cost and privacy |
| 3 | Step 3 | `paired_rows(pairs)`: paired tests on shared tickets |
| 4 | Step 4 | `recommend(rows, pairs)`: the router to deploy, and why |
| 5 | Step 5 | `write_report(path, evidence)` |

## Acceptance checks

The notebook ends with 8 checks: readers scored correctly (against an independent scorer); every reader on the same 16 questions with local ones marked private; at least five routers on the full test set with CIs; latency, cost and privacy for every router; the paired tests above; the recommendation equals the most accurate local router within the budget and carries the fine-tuning verdict and paired evidence; the held-out split has no family shared with training; and a report with all sections and the synthetic-data note. The untouched starter passes 2/8 (the shared questions and the split come from the course).

## Modes

Everything runs **offline** at $0 from the recorded runs (labelled with their date and hardware). With Ollama and `qwen3:4b` the local reader runs live (about a minute on a CPU); with `GROQ_API_KEY` the hosted reader adds about 6–8K tokens. Your Groq and Colab router files join the table when they exist; with `orbita-router` served in Ollama (Lesson 14.04, Part 4) its laptop latency is measured on 40 tickets.

> ⚠️ **Production note: the constraint decides, not the leaderboard.**
> Offline, the most accurate router (few-shot `qwen3:4b`, 94%) misses the 0.5 s budget by 3×; the tuned 0.6B (87%, 0.11 s) meets it. A tuned 1.7B from Colab usually closes the gap. Re-run the decision whenever the budget, the hardware or the test set changes, and keep the frozen test set as the release gate.

> ⚠️ **Privacy note:** the tickets and questions are synthetic. Real tickets are customer data: train on anonymized copies, don't upload them to Colab or a hosted API without a data agreement, and log which router (local or hosted) saw each ticket.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Assistant | Local and offline readers on 16 questions with CIs and a paired test | All 72 Project 06 questions on the local reader, with per-stratum accuracy |
| Router | Five or more routers on 234 tickets with latency, cost and privacy | Your Colab QLoRA served and timed on your own laptop |
| Statistics | Paired tests for tuned vs base and vs few-shot 4B | Minimum detectable difference for 234 tickets (Module 10) discussed in the report |
| Decision | Correct router under the constraints, fine-tuning verdict with evidence | A second scenario (hosted allowed, 2 s budget) and how the answer changes |
| Report | Measured numbers in all sections | A retraining trigger: which monitoring signal (Module 12) and which threshold |
| Hygiene | 8/8 checks; Restart & Run All passes without a key or Ollama; outputs cleared | README with known limits of the synthetic data |

## Use-case variants (pick one instead, same acceptance)

- **Email triage for a law firm:** routing with a strict "never leaves the office" rule; queues for intake, billing, scheduling, urgent.
- **Clinic front desk:** appointment, prescription, billing and emergency queues; an "emergency" misroute cost 100× the others in the threshold.
- **IT helpdesk:** password, hardware, access request, outage; Spanish and English tickets from two offices.

## Stretch

- Serve the fine-tuned router behind the Module 12 FastAPI service (`/route`), with the test set as a CI gate.
- vLLM on a cloud GPU with the LoRA adapter loaded per request (`--enable-lora`), measured with Lesson 12.06's load test.
- The two-tier router from 14.03 with the tuned model as tier 1 and `qwen3:4b` as tier 2.
