# Project 00 · Groq Model Explorer

> **Module 00 · Foundations, Tooling & Research Skills** · ⏱️ 2.5–3.5 hours · Docs verified 2026-10-11

**Goal:** a notebook that tells you, *today*, which Groq chat models are live and how they compare on the same prompts.

| File | What it is |
|---|---|
| [`00-project-groq-model-explorer.ipynb`](00-project-groq-model-explorer.ipynb) | **Starter.** Runs top to bottom from the start; five `# TODO` blocks are yours to complete |
| [`solutions/00-project-groq-model-explorer-solution.ipynb`](solutions/00-project-groq-model-explorer-solution.ipynb) | **Reference solution.** Open it after you have tried, or when you are stuck on one TODO |

## Requirements

1. Fetch the live model list from `https://api.groq.com/openai/v1/models` ([API reference](https://console.groq.com/docs/api-reference#models-list)). Show a table of id, owner, context window (when available), and whether the ID appears on the [deprecations](https://console.groq.com/docs/deprecations) page (maintain a small hand-curated list).
2. Pick at least 2 live chat models and send the same 3 prompts (factual, reasoning, creative), each 3 times (`REPEATS`). Record latency, token usage (`usage_metadata`), the answer, and whether it passed that prompt's programmatic grader.
3. Save results to `data/outputs/00-model-explorer.csv` (gitignored).
4. Finish with a Markdown **Findings** cell and one entry in [`docs/decision-log.md`](../../../docs/decision-log.md).

## Acceptance criteria

- **Restart Kernel and Run All Cells** passes with only `GROQ_API_KEY` set.
- No model ID is hard-coded without a comment saying where and when it was verified (`# VERIFIED YYYY-MM-DD: <url>`).
- No secrets appear in outputs.

## Stretch goals

- Add the paid benchmark (`gpt-6-luna`) behind a flag, or Gemini's free tier (`gemini-3.8-flash`, public data only).
- Plot latency vs tokens.

## Stack

| | |
|---|---|
| Free (default) | Groq: `openai/gpt-oss-20b` and `openai/gpt-oss-120b` (production models), via `init_chat_model("groq:...")` |
| Paid (optional) | OpenAI benchmark `gpt-6-luna` ([why](../../../docs/paid-benchmark-openai-vs-gemini.md)) |
| Low-cost option | Gemini free tier (public data only) |
| Course code used | [`mastery.config`](../../../src/mastery/config.py) (keys, settings) · [`mastery.groq_catalog`](../../../src/mastery/groq_catalog.py) (Models API) |

## Your TODOs (starter notebook)

| TODO | Where | What |
|---|---|---|
| 1 | Step 2 | Fill `KNOWN_DEPRECATED` from the deprecations page, with a `VERIFIED` comment |
| 2 | Step 3 | Complete `models_table()` with the required columns |
| 3 | Step 4 | Implement `run_prompt()`: one measured call per dict, errors recorded, never raised |
| 4 | Step 5 | Save the CSV |
| 5 | Step 6 | Summarize per model (median and worst latency, tokens) and pass rate per model and task |

Stuck? Each TODO has a collapsed two-level hint above it. Then write the **Findings** cell and paste your decision-log entry.

## No key yet? Offline demo mode

Without `GROQ_API_KEY`, both notebooks still run: the model table is built from [`data/samples/groq-models-sample.json`](../../../data/samples/groq-models-sample.json), an **illustrative** sample made from Groq's docs on 2026-10-11 (clearly labelled, not live data), and all model calls are skipped with a message.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Live model table | All required columns with real True/False values; deprecated IDs flagged | Adds a column you chose yourself (for example days until shutdown) and uses it in Findings |
| Comparison | 2 models × 3 prompts × 3 runs with latency, tokens and pass rate | Adds prompts of your own, each with a grader you tested on canned answers first |
| Robustness | Runs top to bottom with only `GROQ_API_KEY`; errors recorded, not raised; no 429s | Shows in Findings how much latency was network and queueing vs generation (server `completion_time`) |
| Hygiene | No hard-coded IDs without `VERIFIED`; no secrets in outputs; outputs cleared | Writes one unit test of your own for a grader or `run_prompt` (fake model, no network) |
| Findings | Findings cell + decision-log entry | Pass rates quoted with n and spread, plus answers that show why a grader failed |
