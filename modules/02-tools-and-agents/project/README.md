# Project 02 · Personal Finance Helper Agent

> **Module 02 · Tools & Your First Agents** · ⏱️ 4–6 hours · Docs verified 2026-10-12

**Goal:** an agent that answers questions about your own (sample) expense log with safe, deterministic tools. It returns a validated `FinanceAnswer` and never does arithmetic itself.

| File | What it is |
|---|---|
| [`02-project-personal-finance-agent.ipynb`](02-project-personal-finance-agent.ipynb) | **Starter.** Runs top to bottom from the start. Six `# TODO` blocks are yours to complete |
| [`solutions/02-project-personal-finance-agent-solution.ipynb`](solutions/02-project-personal-finance-agent-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried, or when you are stuck on one TODO |

## The data

| File | Contents |
|---|---|
| [`data/samples/expenses/expenses-2026.csv`](../../../data/samples/expenses/expenses-2026.csv) | 128 synthetic expenses, July–September 2026, all in COP. Columns: `date, merchant, category, amount, currency, payment_method, note` |
| [`data/samples/expenses/fx-rates.json`](../../../data/samples/expenses/fx-rates.json) | **Illustrative static** exchange rates (as of 2026-10-01): 1 USD = 4,000 COP, 1 EUR = 4,350 COP, 1 MXN = 215 COP. Not real market data |

## Requirements

1. **Tools**, each with a docstring, typed arguments and error handling (`ToolException` with a message that tells the model what to fix):
   - `load_expenses(month)`: count, total and the largest rows of one month (`content_and_artifact`: all rows stay in Python).
   - `sum_by_category(month)`: totals per category and the month total.
   - `top_merchants(n, month)`: the `n` merchants with the highest totals.
   - `convert_currency(amount, from_currency, to_currency)`: uses the static rates file.
   - Plus `mastery.tools.calculator` for differences and ratios, so the model never computes.
2. **Agent**: `create_agent` with `openai/gpt-oss-20b`, a clear system prompt, and `response_format=ToolStrategy(FinanceAnswer)` where `FinanceAnswer(answer: str, figures: list[Figure], caveats: list[str], out_of_scope: bool)`. `ToolStrategy` must be written explicitly, because Groq can't combine JSON-schema output with tools ([Lesson 02.05](../02-05-agent-structured-output.ipynb)).
3. **Streaming and tracing**: stream tool calls into the notebook ([Lesson 02.06](../02-06-streaming-agents.ipynb)). Send traces to the LangSmith project **`m02-finance-agent`**.
4. **Evaluation**: answer the 10 test questions below. At least **8** must be correct.

## The 10 test questions

Expected values come straight from the data (check them yourself with pandas). A **numbers** question counts as correct when every expected value appears among the answer's `figures` (±0.5 for COP amounts, ±0.01 otherwise) **and** in some tool result.

| # | Question | Expected answer | Tools a good run uses |
|---|---|---|---|
| 1 | How much did I spend in total in September 2026? | **5,077,200 COP** | `sum_by_category` |
| 2 | How much did I spend on groceries in September 2026? | **1,694,000 COP** | `sum_by_category` |
| 3 | Which 3 merchants did I spend the most at in August 2026, and how much at each? | **Arriendo Edificio Nogal 1,850,000 · Éxito Calle 80 1,602,000 · Avianca 486,200** | `top_merchants` |
| 4 | Apart from housing, what was my biggest spending category in July 2026? | **groceries, 1,848,600 COP** (housing was 1,850,000) | `sum_by_category` |
| 5 | How many expenses did I record in July 2026? | **42** | `load_expenses` |
| 6 | What was my total September 2026 spending in US dollars? | **1,269.30 USD** (static rate) | `sum_by_category` → `convert_currency` |
| 7 | How much more did I spend in August 2026 than in July 2026? | **870,400 COP** (5,837,600 − 4,967,200) | `sum_by_category` ×2 → `calculator` |
| 8 | How much did I spend on restaurants in September 2026, in euros? | **96.00 EUR** (417,600 COP) | `sum_by_category` → `convert_currency` |
| 9 | How much did I spend in October 2026? | **No data** for that month: say which months exist, give no figures | `sum_by_category` (returns the error) |
| 10 | Should I put my savings into bitcoin? | **Refuse**: `out_of_scope=true`, no figures | none |

## Acceptance criteria

- **No arithmetic by the LLM**: every figure in a `FinanceAnswer` appears in some tool result. The notebook checks this with `invented_numbers()`.
- **Refuses out-of-scope questions** (question 10, and others you try).
- **≥ 8/10 correct** in LIVE mode.
- **Kernel → Restart Kernel and Run All Cells…** passes with only `GROQ_API_KEY`, and also without any key (OFFLINE DEMO mode).
- Model IDs come from `.env` through `mastery.models`, never hard-coded. No secrets in outputs; outputs cleared before committing.

## Modes

- **LIVE** (`GROQ_API_KEY` set): the real model answers. A full evaluation is about 25–40 short calls on the free tier.
- **OFFLINE DEMO** (no key): a scripted stand-in model calls **your** tools in a fixed plan per question and builds its answer from the answer key. Question 7 has a deliberate mistake: it answers 870,000 without the calculator. You can build and test the tools, the checks and the scoring for free. With finished tools and checks, expect **9/10** and an ❌ on "no invented numbers" because of question 7. Demo scores measure your code, not a model.

## Stretch goals

1. **Chart tool**: `chart_by_category(month)` saves a PNG under `data/outputs/m02/` (git-ignored) and returns the path, not the image.
2. **Dynamic model**: route "complex" questions (comparisons, several months) to `openai/gpt-oss-120b` with `@wrap_model_call` ([Lesson 02.03](../02-03-create-agent.ipynb)). Compare the score and the cost.

## Stack

Free: Groq (`openai/gpt-oss-20b`) + pandas + matplotlib. Paid: none needed. LangSmith tracing is optional (free Developer plan).

---

← [Module 02 README](../README.md) · [Course outline](../../../COURSE_OUTLINE.md#project-02--personal-finance-helper-agent)
