# Orbita Cloud support desk as a service (Module 12)

The Project 09 support desk behind a FastAPI service: background runs, resumable SSE streams,
cancel, manager approvals, idempotency keys, a cost budget. Built in Lessons 12.03–12.04;
Lesson 12.05 adds Postgres/SQLite state and JWT auth, 12.06 the container and Compose stack, 12.07 logs,
metrics, alerts and a runbook; 12.09 adds a UI and a release gate.

```bash
# from the repository root, course env active (python -m pip install -e ".[dev]" includes [service])
uvicorn apps.m12_service.main:app --port 8000
```

- **DEMO mode** (default): the offline rule-based model. No key, no cost. Demo API keys:
  `demo-customer` (C-1002), `demo-other` (C-1001), `demo-manager` (approves refunds over $50).
  They are in the source code, so they protect nothing: use them only on your own machine.
- **LIVE mode:** `MASTERY_SERVICE_MODE=live` and `GROQ_API_KEY` in `.env` (💸 about 4–6K tokens per run).
- **Settings:** `MASTERY_SERVICE_*` variables, see `src/mastery/service/settings.py`
  (`MAX_CONCURRENT`, `MAX_QUEUE`, `RUN_TIMEOUT_S`, `API_KEYS`, budgets).
- **API docs:** http://127.0.0.1:8000/docs once it runs.

Try it (Git Bash or PowerShell; on Windows type `curl.exe`):

```bash
curl.exe -s -X POST -H "Authorization: Bearer demo-customer" http://127.0.0.1:8000/threads
curl.exe -s -X POST -H "Authorization: Bearer demo-customer" -H "Content-Type: application/json" -d "{\"message\": \"I'm C-1002, show my invoices\"}" http://127.0.0.1:8000/threads/THREAD_ID/runs
curl.exe -N -H "Authorization: Bearer demo-customer" http://127.0.0.1:8000/runs/RUN_ID/stream
python -m mastery.service.loadtest --users 20
```

**State:** in memory unless `MASTERY_SERVICE_DATABASE_URL` is set: `sqlite:///data/outputs/m12/service.db`
(one process) or `postgresql://agent:agent@localhost:5432/agent` (Lesson 12.05). **Tokens:** set
`MASTERY_SERVICE_JWT_SECRET` (demo) or `MASTERY_SERVICE_JWKS_URL` + issuer + audience (an identity provider).

## Docker (Lesson 12.06)

From the repository root (Docker Desktop running):

```bash
docker compose -f apps/m12_service/compose.yaml up --build -d     # API + Postgres 17, DEMO mode
curl.exe -s http://127.0.0.1:8000/ready
docker compose -f apps/m12_service/compose.yaml logs -f api       # JSON log lines
docker compose -f apps/m12_service/compose.yaml down              # keeps the database volume (-v deletes it)
```

The image (`Dockerfile`, context allowlist in `Dockerfile.dockerignore`) installs the tested versions from
`constraints/`, runs as a non-root user, and drains runs on `SIGTERM`. Your `.env` is read at run time if it exists
(never copied into the image): add `MASTERY_SERVICE_MODE=live` there for LIVE mode.

## Operations (Lesson 12.07)

- `GET /ok` liveness · `GET /ready` readiness (503 while starting, draining, or when the database is down) ·
  `GET /metrics` Prometheus (set `MASTERY_SERVICE_METRICS_TOKEN` to require a bearer token).
- Every response has `X-Request-ID`; log lines and trace metadata carry the same id.
- `--profile obs` adds Prometheus at http://localhost:9090 with the alerts in [`ops/alerts.yml`](ops/alerts.yml).
  What to do when one fires: [`RUNBOOK.md`](RUNBOOK.md). Drill: `DEMO_FAIL_RATE=0.1` makes 10% of DEMO model calls fail.

## UI, releases and deployment (Lesson 12.09)

- **UI:** `GET /` redirects to `/ui/`, three static files in [`ui/`](ui/) (fetch-based SSE, resume after a reload with
  `Last-Event-ID`, Stop, Idempotency-Key per message) served with a strict Content-Security-Policy.
- **Public demo guards:** `MASTERY_SERVICE_PUBLIC=true` refuses demo keys, keys under 24 characters and short JWT secrets;
  `BUDGET_GLOBAL_DAY_USD` caps a day's spend; `POST /admin/pause {"paused": true}` (managers) or `MASTERY_SERVICE_PAUSED=true`
  refuses new runs with 503; `GET /version` shows release, mode, model and the pause flag.
- **Pipeline:** [`.github/workflows/m12-service.yml`](../../.github/workflows/m12-service.yml): lint, service tests, image
  tagged with the commit, smoke test, push to GHCR and deploy through Render's deploy hook (main only), then wait for `/version`.
- **Safe releases:** `mastery.service.release`: `shadow_compare`, `CanaryRouter`, `canary_decision` with `RollbackCriteria`.
- **Deploy:** [`render.yaml`](render.yaml) (Render free web service from the GHCR image, Neon free Postgres). Secrets go in
  the Render dashboard; set `RENDER_DEPLOY_HOOK_URL` (secret) and `M12_PUBLIC_URL` (variable) in GitHub.
