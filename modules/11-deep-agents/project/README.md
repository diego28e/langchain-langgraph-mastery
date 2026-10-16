# Project 11 — Deep Research Analyst

> **Module 11 · Deep Agents** · ⏱️ 6–8 hours · Docs verified 2026-10-16

**The job:** Orbita Labs' sales and support teams keep asking questions that need a short, *sourced* answer ("how often must a Marine station be rinsed?", "what is the API rate limit?") and some that the documents can't answer. You build a deep agent that researches the documents (and the web if needed), has a critic check its findings, and writes a brief that a review policy approves before it is saved. Then you prove it works with an evaluation and write the report your lead reads.

| File | What it is |
|---|---|
| [`11-project-deep-research-analyst.ipynb`](11-project-deep-research-analyst.ipynb) | **Starter.** Runs top to bottom from the start. Five `# TODO` blocks, each with a collapsed goal-style hint |
| [`solutions/11-project-deep-research-analyst-solution.ipynb`](solutions/11-project-deep-research-analyst-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried |
| [`src/mastery/deep/research.py`](../../../src/mastery/deep/research.py) | The research tools with a source ledger, the questions, the brief helpers and the offline scripted models |
| [`data/samples/rag/golden-set.jsonl`](../../../data/samples/rag/golden-set.jsonl) | 20 golden questions: 16 answerable from the Orbita documents, 4 to decline |

Outputs go to the git-ignored `data/outputs/m11/`: `project11-report.md`, `project11-example-brief.md`, `project11-acceptance.json`.

## Requirements

1. **Agent:** a coordinator with a `researcher` (only `search_docs` and `web_search`) and a `critic` (no tools), and system prompts that define the workflow, the brief format (`## Answer`, `## Evidence`, `## Sources`, `## Confidence`) and the citation style (`[doc: path]` or a URL).
2. **Safety:** secret files denied; **every** write under `/reports/` paused for review; ≤ 12 model calls per run.
3. **Review policy:** `review(action)` approves good briefs and rejects, with reasons, briefs that miss a section, answer without sources, or decline with anything but low confidence.
4. **Evaluation:** `check_brief(run, q)` checks format, grounding (citations against what the tools returned, not what the brief claims), workflow (researcher, critic, then write), budget and correctness. Run it on all 20 questions offline (and on the 3-question smoke set live).
5. **Report:** a Markdown report with **Decision**, **Results**, **Failures**, **Cost** and **Risks and next steps**, every number formatted from the measured objects. SHIP only if the pass-rate lower bound is ≥ 60% and all 4 out-of-scope questions are declined.

| TODO | Where | What |
|---|---|---|
| 1 | Step 2 | `PROMPTS` for coordinator, researcher and critic |
| 2 | Step 3 | `build_analyst(models, tools, checkpointer=...)` |
| 3 | Step 4 | `review(action)` |
| 4 | Step 5 | `check_brief(run, q)` |
| 5 | Step 8 | `write_report(path)` |

## Acceptance checks

The notebook ends with 8 checks. All fail on the untouched starter (0/8), and none passes with a shortcut:

- the secret rule is probed with a real `read_file("/.env")` call;
- the review policy and the checker are tested on fixtures with known answers (an invented source, a skipped critic, a wrong price);
- every one of the 20 runs must have paused for review and followed the workflow;
- the report must carry the measured pass rate and interval, and its decision must follow the bar.

## Modes

Everything runs **offline** with scripted models that follow the workflow (`offline_models()`), so Restart & Run All always completes at $0. Offline the reader quotes the best-matching sentence, so it scores 17/20: that is the baseline to beat. With a key, Step 7 runs the same analyst on your models: the smoke set (3 questions) costs ≈ 45–75K tokens; the full set (`LIVE_FULL = True`, 20 questions) ≈ 300–500K, so spread it over several days on a free tier or use a paid plan. Set `MASTERY_FALLBACK_MODELS` in `.env` so a quota error switches models instead of failing the run. `LIVE_WEB = True` uses real web search (Groq browser search or Tavily). Free-tier prompts may be read by humans: public or synthetic documents only.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Agent | Researcher and critic with the right tools; prompts cover the workflow and format | The critic's REJECT makes the coordinator re-research once, and you show a case where it helped |
| Safety | Secrets denied, every brief reviewed, budget enforced | A `PIIMiddleware` on the brief and a test that proves it |
| Evaluation | All checks validated on fixtures; 20 offline runs with an interval | The smoke set run live on two days, with the difference discussed |
| Report | Measured numbers and a decision that follows the bar | A failure analysis that names the cause (prompt, tools or documents) of each live failure |
| Hygiene | 8/8 checks; Restart & Run All passes without a key; outputs cleared | Your report states what 20 questions can't detect |

## Stretch

- Beat the offline baseline on `g01`, `g02` and `g10` with a better query or reader, without breaking a decline.
- Add `RubricMiddleware` (Lesson 11.12, F4) with your brief rubric and compare pass rates and tokens.
- Deploy it with `langgraph.json` (Lesson 11.11) and stream the review step to a UI (Lesson 11.10).
