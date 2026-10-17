# Module 15 — Decision Models with Jev (optional)

> **Part 2 — Pro** · optional, after Module 14 · Lessons 15.01–15.07 and two projects (support triage with escalation, agent safety gate).

**Goals:** Know when a *decision model* beats an LLM. Jev, TypeSafe's System One model, answers typed questions (yes/no, choice, score) with calibrated probabilities and writes no text. Learn to put it at the branches of LangChain and LangGraph apps: **cheap by default, frontier on exception**. Thresholds should be chosen from measurements, not guesses.

**Estimated time:** 1–1.5 weeks.

## Setup and cost (read first)

- **No free tier** (verified 2026-10-16). New TypeSafe accounts get no credit, and a key can only be created after you add credit in the [TypeSafe console](https://console.typesafe.ai) (Billing). The console **Playground** is free to use by hand.
- **Price:** Jev bills input tokens at $0.042 per 1M, and output tokens are free ([models page](https://docs.typesafe.ai/models)). Every live cell of this module together costs well under one cent.
- **Without a key, everything still runs.** The notebooks use **replay mode**: recorded Jev answers served through the real client, with no network and $0. Replayed answers are marked `synthetic` while they are hand-written from the documented schema. They teach the API and the decision logic, **not** Jev's accuracy.
- **Alternative endpoints:** [OpenRouter](https://openrouter.ai/docs/guides/community/typesafe-sdk) (`TYPESAFE_BASE_URL=https://openrouter.ai/api`, an OpenRouter key, model `typesafe/jev-1.13`) or Vercel AI Gateway. See `.env.example`.
- **Package:** `langchain-typesafe[experimental]==0.0.1a3`, an **alpha** pinned exactly. `mastery.decisions` wraps it so an API change is fixed in one place.

**Keys:** optional `TYPESAFE_API_KEY` (live Jev), and `GROQ_API_KEY` for the LLM comparisons.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 15.01 | Decision models vs LLMs: first calls to Jev | `15-01-decision-models-vs-llms.ipynb` | ✅ Ready |
| 15.02 | Probabilities, calibration and thresholds | `15-02-calibration-and-thresholds.ipynb` | ✅ Ready |
| 15.03 | Jev in LangChain | `15-03-jev-in-langchain.ipynb` | ✅ Ready |
| 15.04 | Jev in LangGraph: decision nodes and escalation | `15-04-jev-in-langgraph.ipynb` | ✅ Ready |
| 15.05 | Middleware: model routing and tool guardrails | `15-05-middleware-routing-and-guardrails.ipynb` | ✅ Ready |
| 15.06 | Jev as a LangSmith evaluator vs LLM-as-judge | `15-06-jev-as-evaluator.ipynb` | ✅ Ready |
| 15.07 | Benchmarking cost and latency | `15-07-benchmarking-decisions.ipynb` | ✅ Ready |

## Projects

Spec: [project/README.md](project/README.md). Each project has a starter (5 TODOs with hints) and a reference solution, and runs offline at $0.

| Project | What you build | Starter | Status |
|---|---|---|---|
| 15A | Support triage with escalation: Jev by default, an LLM on uncertain tickets, thresholds from costs | [`15a-project-support-triage.ipynb`](project/15a-project-support-triage.ipynb) | ✅ Ready |
| 15B | Agent safety gate: tune, test and prove a `JevToolGate` for an ops agent | [`15b-project-agent-safety-gate.ipynb`](project/15b-project-agent-safety-gate.ipynb) | ✅ Ready |

## `src/mastery` increment

New `mastery/decisions/`:
- `decision_classifier()` builds the classifier in live, replay or record mode.
- Replay and record transports.
- `answer_rows`, `decision_cost`, `provenance` and `with_rate_limit_retry`.
- The Orbita Cloud triage questions and the 234-ticket calibration lab.
- `policy.py` (top probability, margin, Brier, act/ignore/review bands from costs) and `llm_fallback.py` (`llm_decider`: an LLM that answers in Jev's response shape).
- `graph.py` (LangGraph triage with LLM escalation and a human interrupt, batch fan-out with `Send`), `middleware.py` (`with_classifier`, `JevToolGate`: allow / review / block, fails closed) and `ops.py` (sandboxed ops tools and agent scenarios for 15.05).
- `safety.py` (32 labeled tool calls for Project 15B), `evaluator.py` (48 labeled support replies, `jev_evaluators` in LangSmith's evaluator shape) and `bench.py` (`benchmark` with p50 / p95 and cost per 1k, `monthly_cost`, `llm_cost_per_1k`).

`mastery.pricing` gains Jev, and `mastery.doctor` gains `check_decisions_env()`.

## Status

✅ Ready: Lessons 15.01–15.07 and Projects 15A–15B.

---

← [Module 14](../14-local-models-and-fine-tuning/) · [Course outline](../../COURSE_OUTLINE.md)
