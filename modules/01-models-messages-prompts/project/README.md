# Project 01 · Multi-Model Comparison Lab

> **Module 01 · Models, Messages & Prompts** · ⏱️ 4–6 hours · Docs verified 2026-10-11

**Goal:** a reusable notebook that runs one task across several model configurations and returns validated, structured verdicts, so you choose models with numbers instead of impressions.

| File | What it is |
|---|---|
| [`01-project-multi-model-comparison-lab.ipynb`](01-project-multi-model-comparison-lab.ipynb) | **Starter.** Runs top to bottom from the start; five `# TODO` blocks are yours to complete |
| [`solutions/01-project-multi-model-comparison-lab-solution.ipynb`](solutions/01-project-multi-model-comparison-lab-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried, or when you are stuck on one TODO |

## The task

Extract a `JobPosting` from each of the 10 synthetic postings in [`data/samples/job-postings/`](../../../data/samples/job-postings/) and compare it with the hand-labelled [`answer-key.json`](../../../data/samples/job-postings/answer-key.json):

| Field | Type | Scored by |
|---|---|---|
| `title`, `company` | text | exact match after normalizing case and spaces |
| `seniority` | `intern \| junior \| mid \| senior \| lead \| unknown` | exact match |
| `work_mode` | `remote \| hybrid \| onsite \| unknown` | exact match |
| `skills` | list of lowercase canonical names | F1 between sets |
| `salary` | `{min, max, currency, period}` or `null` | all four match (or both null) |

The labelling rules are in the answer key (`_labelling_notes`). Two borderline cases are deliberate (a "Staff" title, "2 years of experience"): discuss them in your findings.

## Requirements

1. Task: extract structured info from 10 sample texts into a `JobPosting` Pydantic model (Lesson 01.04).
2. Run at least 3 configurations: `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, and one more. Default third: Groq preview `qwen/qwen3.8-27b` (free, best-effort `json_schema`). Options: local Ollama, the paid benchmark `gpt-6-luna` (`RUN_PAID = True`), or Gemini.
3. For each: **schema-valid rate**, **field-level accuracy** against the answer key, **mean latency**, **total tokens**, **estimated cost** (`mastery.pricing`, Lesson 01.06).
4. **Stream** one example live in the notebook (Lesson 01.05). **Batch** the rest with a concurrency limit and a rate limiter (Lessons 01.05–01.06).
5. **Trace** everything to the LangSmith project `m01-comparison-lab` (Lesson 01.08).

## Acceptance criteria

- Results table + bar chart.
- Invalid outputs are caught and counted, never crash the run (`include_raw=True`, Lesson 01.04).
- **Kernel → Restart Kernel and Run All Cells…** passes with only `GROQ_API_KEY` (and also without any key, in OFFLINE DEMO mode).
- Model IDs come from `.env` through `mastery.models`; nothing hard-coded.
- No secrets in outputs; outputs cleared before committing.
- [`docs/decision-log.md`](../../../docs/decision-log.md) updated with a recommendation and why.

## Stretch goals

- Add a `with_fallbacks` chain (120b → 20b) and measure how often the fallback fires (Lesson 01.07). The solution uses a short timeout on the primary to make fallbacks observable. Note: with `include_raw=True`, an *invalid* output does not raise, so it does **not** trigger the fallback; think about whether it should.
- Compare `json_schema` vs `function_calling` structured output on the same model (Lesson 01.04).

Both are implemented in the solution behind `RUN_STRETCH = False`.

## Stack

| | |
|---|---|
| Free (default) | Groq `openai/gpt-oss-20b`, `openai/gpt-oss-120b` (production) and `qwen/qwen3.8-27b` (**preview**, evaluation only) |
| Paid (optional) | OpenAI `gpt-6-luna` (`RUN_PAID = True`; needs `OPENAI_API_KEY` and `%pip install "langchain-openai>=1.7.0,<2"`), `gpt-6.1-sol` as the ceiling ([why](../../../docs/paid-benchmark-openai-vs-gemini.md)) |
| Low-cost option | Gemini `gemini-3.8-flash` (public/synthetic data only on the free tier) |
| Tracing (optional) | LangSmith free Developer plan, project `m01-comparison-lab` |
| Course code used | [`mastery.models`](../../../src/mastery/models.py) (`get_model`, `model_string`, `explain_model_error`) · [`mastery.pricing`](../../../src/mastery/pricing.py) (`estimate_cost`) · [`mastery.config`](../../../src/mastery/config.py) |

## Budget and time (LIVE mode)

About 32 calls (3 configurations × 10 postings + 2 checks), ≈ 1K tokens each: ≈ 32K tokens, well inside the free tier's daily limit. The rate limiter is set to **0.13 requests/second per model** (8K tokens/min ÷ ~1K tokens per call, Lesson 01.06), so the main run takes **about 4 minutes**. If your [Groq limits](https://console.groq.com/settings/limits) are higher, raise it with `MASTERY_LAB_RPS` in `.env` (for example `MASTERY_LAB_RPS=0.5`). The stretch goals add about 20 calls.

## Your TODOs (starter notebook)

| TODO | Where | What |
|---|---|---|
| 1 | Step 2 | Complete `JobPosting` (+ `Salary`) so it accepts every answer-key entry and works in strict mode |
| 2 | Step 2 | Write the system prompt with the five building blocks and the labelling rules |
| 3 | Step 3 | `with_structured_output(..., include_raw=True)` and `extract_posting()`: time the call, read usage, count invalid outputs, never raise |
| 4 | Step 6 | `score_fields()`: exact match, skills F1, salary match |
| 5 | Step 6 | Summary table (latency, tokens, cost, per-field accuracy), bar chart, CSV in `data/outputs/` |

Every check cell prints ✅ or ❌ TODO n, so you always know what's left. Then write the **Findings** cell and paste your decision-log entry.

## No key yet? Offline demo mode

Without `GROQ_API_KEY`, both notebooks still run top to bottom: each configuration is replaced by a **stand-in** built from the answer key with seeded, deterministic mistakes (cell `demo_extractor`). The whole pipeline (batching, scoring, table, chart, error analysis) works, so you can finish TODOs 1–5 for free. Demo numbers are labelled as such and are **not** model results: never put them in the decision log.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Schema and prompt | Strict-compatible schema accepts all 10 answers; five-block prompt with the labelling rules | Field descriptions tuned from the error analysis, with before/after numbers |
| Comparison | ≥ 3 configurations × 10 postings; valid rate, field accuracy, latency, tokens, cost | Repeated runs (variance), or a paid benchmark row |
| Robustness | Invalid outputs and API errors counted, never raised; rate-limited batches | Retries tuned from your real 429 rate; no 429s in the run |
| Observability | Traces in `m01-comparison-lab` with config metadata | Traces used to explain a specific mistake (exact prompt + output) |
| Findings | Findings cell + decision-log entry with evidence | Discusses the borderline labels and whether the key or the model is wrong |
| Hygiene | Restart & Run All passes; no hard-coded IDs; no secrets; outputs cleared | Stretch goals done and interpreted |

---

← [Lesson 01.08](../01-08-first-traces.ipynb) · [Module 01 README](../README.md) · Module 02 →
