# Module 12 — Production & Deployment

> **Part 2 — Pro (Modules 09–14)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 12](../../COURSE_OUTLINE.md#module-12--production--deployment)

**Goals:** Ship an agent as a reliable, **self-hosted** service you fully control, and put it on a **public URL**: configuration, resilience, cost control, caching, async, a FastAPI API that runs agents as background jobs (resumable streams, cancellation, a double-texting policy, idempotency keys), Postgres persistence, real auth (API keys, then JWT/OIDC) with per-user quotas, tenant isolation and data deletion, Docker + Docker Compose, OpenTelemetry traces and metrics against written SLOs, an incident runbook, safe releases (versioned prompts and models, canary, rollback), a small UI, and CI/CD. The main path is free: it runs on your machine, then on a free hosting tier. LangSmith's managed deployment (Agent Server / LangSmith Cloud) is an **optional reference** lesson (12.08), so you can compare before you choose.

**Estimated time:** about 36–46 h (≈ 4.5–6 weeks at 8 h/week).

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 12.01 | Production readiness: checklist, SLOs, and budgets | `12-01-production-checklist.ipynb` | ✅ Ready |
| 12.02 | Resilience, rate limits, cost and caching | `12-02-resilience-cost-caching.ipynb` | ✅ Ready |
| 12.03 | Async agents and concurrency | `12-03-async-and-concurrency.ipynb` | ✅ Ready |
| 12.04 | A FastAPI service for long-running agents: runs, resumable streams, cancellation | `12-04-fastapi-service.ipynb` | ✅ Ready |
| 12.05 | Persistence, auth, and multi-user data | `12-05-persistence-and-auth.ipynb` | ✅ Ready |
| 12.06 | Docker and Docker Compose | `12-06-docker-and-compose.ipynb` | ✅ Ready |
| 12.07 | Observability and operations: logs, metrics, traces, SLOs and incidents | `12-07-observability-and-operations.ipynb` | ✅ Ready |
| 12.08 | (Optional reference) LangSmith Deployment and Agent Server | `12-08-optional-langsmith-deployment.ipynb` | ✅ Ready |
| 12.09 | Ship it: UI, CI/CD, safe releases, and a public deployment | `12-09-ship-it.ipynb` | ✅ Ready |

## Production notes

> ⚠️ **Production note: "it runs in Compose on my laptop" is not production.**
> Compose on one machine has no redundancy, TLS, or zero-downtime deploys. In production: put a reverse proxy with TLS in front, use a managed Postgres with backups, keep secrets in a secret manager, set CPU/memory limits, ship logs and traces centrally, and deploy images built by CI (not from your laptop). Docker Desktop is free for personal use and small businesses, but commercial use in larger enterprises (more than 250 employees **or** more than $10M annual revenue) needs a paid subscription ([Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/)).

## Project

**Project 12 — Self-Hosted Agent Service, Live on a Public URL**: Deploy one capstone-candidate agent (ideally your Project 10 or Project 11 agent) as a real, self-hosted service that anyone can run from a fresh clone, and that is live on a public URL.

| Project | Notebook | Status |
|---|---|---|
| [Project 12](project/README.md) | `project/12-project-production-agent-service.ipynb` (starter) · `project/solutions/…-solution.ipynb` | ✅ Ready |

The notebook is the release review (8 acceptance checks, offline, $0); the deliverable is the deployed service with its URL in your README.

## Jupyter skill

From notebook to module/service (`nbconvert --to script`, refactoring).

## `src/mastery` increment

`mastery/service/`: SLOs, error budgets and burn rates (`slo.py`), latency and cost budgets with a spend ledger (`budgets.py`), failure injection for resilience tests (`resilience.py`). Background runs with a concurrency limit, bounded queue, idempotency, cancel and timeouts (`runs.py`); the FastAPI app factory with API-key auth, ownership checks and native SSE with `Last-Event-ID` resume (`app.py`); settings via `pydantic-settings` (`settings.py`); the support desk wiring (`desk.py`); an SSE client (`client.py`) and an async load test (`loadtest.py`). Durable state on SQLite or Postgres (`store.py`) and JWT verification (`auth.py`). Readiness, graceful shutdown with a run drain, JSON logs with request ids, Prometheus metrics and trace metadata (`observability.py`). Install with the `[service]` extra (part of `[dev]`). The container image, Compose stack, Prometheus alerts and runbook are in `apps/m12_service/`.

## Research checkpoint

Re-check the [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/) and [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) for changes since this course was written. Then compare running your service yourself vs LangSmith Cloud using [Usage and billing](https://docs.langchain.com/langsmith/usage-and-billing), and log the decision. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

✅ Module 12 complete: Lessons 12.01–12.09 and Project 12 (verified 2026-10-16). The service app lives in [`apps/m12_service/`](../../apps/m12_service/); the Agent Server version (12.08) in [`apps/m12_agent_server/`](../../apps/m12_agent_server/).

**Free-tier budget (LIVE cells):** 12.01 ≈ 1–2K tokens (TTFT probe), 12.02 ≈ 2–3K tokens (prompt-cache probe), 12.03 ≈ 1K tokens (concurrent calls), 12.04 ≈ 4–6K tokens (one LIVE run through the service), 12.05 none (its 🐳 cells use a local Postgres in Docker, optional), 12.06 none (🐳 build and Compose stack in DEMO mode), 12.07 none (🌐 one LangSmith trace of a DEMO run; 🐳 Prometheus drill), 12.08 none (a local `langgraph dev` with the offline desk), 12.09 none offline (optional 💸 one LIVE run on your public deployment, ≈ 4–6K tokens of its quota), Project 12 none offline (the deployed service spends only what its daily cap allows). Every 🧪 cell runs offline for free; simulated traffic is labelled as such.

---

← [Module 11](../11-deep-agents/) · [Course outline](../../COURSE_OUTLINE.md) · Next: [Capstones](../../capstones/README.md), or the electives [Module 13](../13-multimodal-and-voice/) and [Module 14](../14-local-models-and-fine-tuning/) →
