# Module 13 — Production & Deployment

> **Part 2 — Pro (Modules 09–14)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 13](../../COURSE_OUTLINE.md#module-13--production--deployment)

**Goals:** Ship an agent as a reliable, **self-hosted** service you fully control: configuration, resilience, cost control, caching, async, a FastAPI API with streaming, Postgres persistence, API-key auth, Docker + Docker Compose, a small UI, and CI. Everything in the main path is free and runs on your own machine. LangSmith's managed deployment (Agent Server / LangSmith Cloud) is covered as an **optional reference** lesson at the end, so you can compare.

**Estimated time:** 2–2.5 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 13.01 | Production readiness checklist | `13-01-production-checklist.ipynb` | 📝 Planned |
| 13.02 | Resilience, rate limits, cost and caching | `13-02-resilience-cost-caching.ipynb` | 📝 Planned |
| 13.03 | Async agents and concurrency | `13-03-async-and-concurrency.ipynb` | 📝 Planned |
| 13.04 | A FastAPI service for your agent | `13-04-fastapi-service.ipynb` | 📝 Planned |
| 13.05 | Persistence, auth, and multi-user data | `13-05-persistence-and-auth.ipynb` | 📝 Planned |
| 13.06 | Docker and Docker Compose | `13-06-docker-and-compose.ipynb` | 📝 Planned |
| 13.07 | UI and CI/CD for the service | `13-07-ui-and-cicd.ipynb` | 📝 Planned |
| 13.08 | (Optional reference) LangSmith Deployment and Agent Server | `13-08-optional-langsmith-deployment.ipynb` | 📝 Planned |

## Production notes

> ⚠️ **Production note: "it runs in Compose on my laptop" is not production.**
> Compose on one machine has no redundancy, TLS, or zero-downtime deploys. In production: put a reverse proxy with TLS in front, use a managed Postgres with backups, keep secrets in a secret manager, set CPU/memory limits, ship logs and traces centrally, and deploy images built by CI (not from your laptop). Docker Desktop is free for personal use and small businesses, but commercial use in larger enterprises (more than 250 employees **or** more than $10M annual revenue) needs a paid subscription ([Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/)).

## Project

**Project 13 — Self-Hosted Agent Service (FastAPI + Docker)**: Deploy one capstone-candidate agent as a real, self-hosted service that anyone can run from a fresh clone.

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

← [Module 12](../12-testing-evaluation-observability/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 14](../14-local-models-and-fine-tuning/) →
