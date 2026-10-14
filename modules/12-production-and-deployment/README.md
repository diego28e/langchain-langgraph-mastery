# Module 12 — Production & Deployment

> **Part 2 — Pro (Modules 09–14)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 12](../../COURSE_OUTLINE.md#module-12--production--deployment)

**Goals:** Ship an agent as a reliable, **self-hosted** service you fully control, and put it on a **public URL**: configuration, resilience, cost control, caching, async, a FastAPI API that runs agents as background jobs (resumable streams, cancellation, a double-texting policy, idempotency keys), Postgres persistence, real auth (API keys, then JWT/OIDC) with per-user quotas, tenant isolation and data deletion, Docker + Docker Compose, OpenTelemetry traces and metrics against written SLOs, an incident runbook, safe releases (versioned prompts and models, canary, rollback), a small UI, and CI/CD. The main path is free: it runs on your machine, then on a free hosting tier. LangSmith's managed deployment (Agent Server / LangSmith Cloud) is an **optional reference** lesson (12.08), so you can compare before you choose.

**Estimated time:** about 36–46 h (≈ 4.5–6 weeks at 8 h/week).

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 12.01 | Production readiness: checklist, SLOs, and budgets | `12-01-production-checklist.ipynb` | 📝 Planned |
| 12.02 | Resilience, rate limits, cost and caching | `12-02-resilience-cost-caching.ipynb` | 📝 Planned |
| 12.03 | Async agents and concurrency | `12-03-async-and-concurrency.ipynb` | 📝 Planned |
| 12.04 | A FastAPI service for long-running agents: runs, resumable streams, cancellation | `12-04-fastapi-service.ipynb` | 📝 Planned |
| 12.05 | Persistence, auth, and multi-user data | `12-05-persistence-and-auth.ipynb` | 📝 Planned |
| 12.06 | Docker and Docker Compose | `12-06-docker-and-compose.ipynb` | 📝 Planned |
| 12.07 | Observability and operations: OpenTelemetry, SLOs, and incidents | `12-07-observability-and-operations.ipynb` | 📝 Planned |
| 12.08 | (Optional reference) LangSmith Deployment and Agent Server | `12-08-optional-langsmith-deployment.ipynb` | 📝 Planned |
| 12.09 | Ship it: UI, CI/CD, safe releases, and a public deployment | `12-09-ship-it.ipynb` | 📝 Planned |

## Production notes

> ⚠️ **Production note: "it runs in Compose on my laptop" is not production.**
> Compose on one machine has no redundancy, TLS, or zero-downtime deploys. In production: put a reverse proxy with TLS in front, use a managed Postgres with backups, keep secrets in a secret manager, set CPU/memory limits, ship logs and traces centrally, and deploy images built by CI (not from your laptop). Docker Desktop is free for personal use and small businesses, but commercial use in larger enterprises (more than 250 employees **or** more than $10M annual revenue) needs a paid subscription ([Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/)).

## Project

**Project 12 — Self-Hosted Agent Service, Live on a Public URL**: Deploy one capstone-candidate agent (ideally your Project 10 or Project 11 agent) as a real, self-hosted service that anyone can run from a fresh clone, and that is live on a public URL.

Project files go in `project/`.

## Jupyter skill

From notebook to module/service (`nbconvert --to script`, refactoring).

## `src/mastery` increment

`mastery/service/` (FastAPI app factory, settings via `pydantic-settings`, auth dependency, SSE helpers).

## Research checkpoint

Re-check the [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/) and [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) for changes since this course was written. Then compare running your service yourself vs LangSmith Cloud using [Usage and billing](https://docs.langchain.com/langsmith/usage-and-billing), and log the decision. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 11](../11-deep-agents/) · [Course outline](../../COURSE_OUTLINE.md) · Next: [Capstones](../../capstones/README.md), or the electives [Module 13](../13-multimodal-and-voice/) and [Module 14](../14-local-models-and-fine-tuning/) →
