# Project 12 — Self-Hosted Agent Service, Live on a Public URL

> **Module 12 · Production & Deployment** · ⏱️ 6–10 hours · Docs verified 2026-10-16

**The job:** Orbita Cloud wants its support desk (Projects 09–10) on a public URL. You ship it as the self-hosted service you built in Lessons 12.04–12.09, deploy it on free tiers, and run the release review a production team would before anyone gets the link: every promise is checked by code against a running instance, and a SHIP/HOLD report says whether it is ready.

| File | What it is |
|---|---|
| [`12-project-production-agent-service.ipynb`](12-project-production-agent-service.ipynb) | **Starter.** Runs top to bottom from the start. Five `# TODO` blocks, each with a collapsed goal-style hint |
| [`solutions/12-project-production-agent-service-solution.ipynb`](solutions/12-project-production-agent-service-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried |
| [`apps/m12_service/`](../../../apps/m12_service/) | The service: `main.py`, `ui/`, `Dockerfile`, `compose.yaml`, `ops/` (Prometheus alerts), `RUNBOOK.md`, `render.yaml` |
| [`src/mastery/service/`](../../../src/mastery/service/) | Settings, runs, store, auth, budgets, observability, SLOs, release helpers |
| [`.github/workflows/m12-service.yml`](../../../.github/workflows/m12-service.yml) · [`eval-gate.yml`](../../../.github/workflows/eval-gate.yml) | The pipeline and the eval gate |

Outputs go to the git-ignored `data/outputs/m12/`: `project12.db`, `project12-report.md`, `project12-acceptance.json`.

## Requirements

1. **API** under `/v1`: `POST /v1/threads`, `GET /v1/threads/{id}` (history, owner only), `POST /v1/threads/{id}/runs` (202 + `run_id`, `Idempotency-Key`), `GET /v1/runs/{id}`, `GET /v1/runs/{id}/stream` (SSE, resumable with `Last-Event-ID`), `POST /v1/runs/{id}/cancel`, `DELETE /v1/me/data`, plus `/healthz`, `/ready`, `/version`, `/metrics`. Double-texting policy: **reject** (409), documented and tested.
2. **Persistence:** Postgres checkpointer and service store (Compose, named volume; Neon in the public deployment); SQLite for local runs without Docker.
3. **Security:** bearer API keys or JWT (OIDC via JWKS), ownership checks on every endpoint (404, never 403), per-user and global daily cost caps, `MASTERY_SERVICE_PUBLIC=true` on the internet, a kill switch, no secrets in the image or logs.
4. **Reliability and operations:** timeouts, retries, graceful shutdown, JSON logs with request ids, Prometheus metrics, burn-rate alerts, `RUNBOOK.md` with your Lesson 12.07 postmortem.
5. **Packaging and delivery:** the multi-stage image (non-root, health check), `compose.yaml`, the CI pipeline (lint, tests, image by commit, smoke test, eval gate, deploy) and a rehearsed rollback.
6. **UI and public URL:** the browser UI at `/ui/` and the deployed URL in your README.
7. **Release review (this notebook):** the five TODOs and an 8-check acceptance run; the report decides SHIP only if every check passes, the SLOs hold under 20 concurrent users, and the eval gate passes.

| TODO | Where | What |
|---|---|---|
| 1 | Step 2 | `isolation_suite(c, thread_id, run_id)`: another customer and no key, on every endpoint |
| 2 | Step 3 | `exactly_once(c, run_id)`: disconnect and resume with `Last-Event-ID` |
| 3 | Step 4 | `rows_for(db, user, threads, runs)`: a user's rows in every table, checkpoints included |
| 4 | Step 3 | `policy_check(c)`: idempotency key and double texting |
| 5 | Step 8 | `write_report(path, evidence)` |

## Acceptance checks

The notebook ends with 8 checks: tenant isolation, idempotency and double texting, exactly-once resume, data surviving a restart (a paused refund resumed by a new process), `DELETE /v1/me/data` leaving no rows (and another user's data untouched), 20 concurrent runs without errors, and a report with every section, the measured numbers and a decision that follows the bar. The untouched starter passes 1/8 (the load test needs no TODO).

Outside the notebook, with Docker and accounts (run them yourself and note the results in your README):

- `docker compose -f apps/m12_service/compose.yaml up --build` from a fresh clone and `.env` (from `.env.example`) brings up the API and the UI at http://127.0.0.1:8000/ui/.
- The 12.07 drill: the `AgentErrorBudgetFastBurn` alert fires and clears.
- The public URL answers (a cold start is fine), refuses the demo keys, and shows your release at `/version`.
- A deliberate bad release is rolled back in under five minutes (write the time in the runbook).

## Modes

Everything in the notebook runs **offline** (DEMO mode, offline model, SQLite) at $0. The public deployment runs in LIVE mode on Groq's free tier: keep `BUDGET_GLOBAL_DAY_USD` at what you are willing to spend in a day, and use synthetic data only.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| API and security | All endpoints, owner checks, 401/404, caps, kill switch | JWT from a real OIDC provider (Lesson 12.05) on the public URL |
| Persistence | Restart and resume proven; delete leaves no rows | A Postgres backup and restore rehearsed and timed |
| Operations | Metrics, alerts, runbook, postmortem | An alert routed to your phone, tested |
| Delivery | Pipeline green, image by commit, rollback rehearsed | Shadow or canary used on a real change, with the decision recorded |
| Report | Measured numbers; the decision follows the bar | A capacity estimate: users per instance at your SLOs |
| Hygiene | 8/8 checks; Restart & Run All passes without a key; outputs cleared | README with the URL, a privacy note and known limits |

## Stretch

- Serve your Project 11 deep agent behind the same API (Postgres checkpointer and store).
- A separate worker process and a queue for runs.
- An online evaluator on production traces (Module 10) with an alert.
- Try optional Lesson 12.08 and write a one-page comparison: self-hosted vs LangSmith Cloud, with your measured costs.
