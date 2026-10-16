# Runbook: Orbita Cloud support desk service

What to do when an alert in [`ops/alerts.yml`](ops/alerts.yml) fires (Lesson 12.07). Every step names the signal
to read first. Keep this file next to the code and update it after every incident.

**Signals:** `GET /ready` · `GET /metrics` (Prometheus at http://localhost:9090 with `--profile obs`) ·
`docker compose -f apps/m12_service/compose.yaml logs api` (JSON, one line per request and per run) ·
LangSmith traces (filter by metadata `service_run_id` or `request_id`) · `GET /stats` (manager key).

**First five minutes, every time:** acknowledge the alert · note the time (your zone) · open the dashboard ·
check whether a release went out in the last hour (`release` in `/ready` and in the logs) · if yes, roll back first, debug later.

## AgentDown

Prometheus can't scrape `/metrics`.

1. `docker compose -f apps/m12_service/compose.yaml ps`: is `api` running, restarting or unhealthy?
2. `docker compose ... logs --tail 50 api`: a startup error (bad setting, database unreachable) fails fast with a clear message.
3. `curl -s localhost:8000/ready`: `problems` lists `database: …` or `shutting down`.
4. Database down: `docker compose ... ps db`, then its logs. The API restarts by itself once `db` is healthy (`depends_on … restart: true`).

## AgentErrorBudgetFastBurn

More than 14.4 % of runs failed over both the last hour and the last 5 minutes (availability SLO 99 %).

1. Find the cause in the logs: `docker compose ... logs api | grep '"run_status": "error"'`; the `error` field says
   `SimulatedOutage` (a drill: `MASTERY_SERVICE_DEMO_FAIL_RATE`), `RateLimitError`, `timeout`, or a code bug.
2. Provider errors (429/503): check the provider's status page and your quota (Groq free tier: per-minute and per-day
   limits). Mitigate: lower `MASTERY_SERVICE_MAX_CONCURRENT`, or add a fallback model (`ModelFallbackMiddleware`, Lesson 12.02).
3. After a release: roll back to the previous image tag (`RELEASE=<previous> docker compose ... up -d --no-build`, Lesson 12.09).
4. Open one failed run's trace in LangSmith (metadata `service_run_id`): which node failed?
5. Resolved when the 5-minute error ratio is back under 1 %. Write the postmortem (template below).

## AgentSlowFirstToken

p99 time to first token above 3 s for 10 minutes.

1. Queue or model? Compare `agent_run_queue_seconds` with `agent_run_ttft_seconds`. Waiting in the queue means
   too little concurrency; the model being slow means the provider (or a longer prompt) is to blame.
2. Queue: raise `MAX_CONCURRENT` if the provider's rate limits allow it (Lesson 12.03), or add a replica.
3. Model: check the provider status, and whether a release grew the prompt (input tokens per run in `agent_tokens_total`).

## AgentQueueBacklog

More than 10 runs waiting for 5 minutes. Users see long waits and, past `MAX_QUEUE`, 429s.

1. A traffic spike (`agent_http_requests_total`) or slower runs (`agent_run_duration_seconds`)?
2. Spike from one user: per-user budgets (Lesson 12.02) cap their spend; add a per-user rate limit if it repeats.
3. Otherwise scale out: another `api` replica on the same Postgres (Lesson 12.06, exercise 3).

## AgentSpendHigh

More than $0.25 of model spend in one hour.

1. Who? `GET /stats` and the `cost_usd` field of `run.finished` log lines, grouped by `user_id`.
2. Abuse: revoke that user's key or token. A loop: open its trace; `RunManager(recursion_limit=...)` caps the steps per run.
3. The daily global budget (`BUDGET_GLOBAL_DAY_USD`) is the hard stop: runs past it get 429.

## Playbooks without an alert

- **Model deprecated or renamed** (provider email, or runs failing with `model_not_found`): set `MASTERY_MODEL_FAST`
  to the replacement in `.env`, run the eval gate (Lesson 12.09), restart. The model id is configuration, not code.
- **Prompt-injection or data-leak report:** find the run (request id from the user, or `user_id` and time in the logs),
  open its trace, and if a tool was misused, disable that tool and release; keep the trace for the postmortem.
- **Leaked key or token secret:** rotate it at the provider, update `.env` (or the platform's secrets), restart;
  with JWT, rotate the signing key at the identity provider (the JWKS changes, old tokens stop verifying).
- **Database restore:** stop `api`, restore the Postgres backup into a fresh volume, start `db`, then `api`;
  `recover()` closes runs that were in flight when the backup was taken.

- **Bad release** (errors or wrong answers right after a deploy): pause first if users are harmed
  (`POST /admin/pause {"paused": true}`), then roll back: deploy the previous image tag (Render deploy hook with
  `imgURL=ghcr.io/<you>/mastery-m12-service:<previous sha>`, or *Rollback* on the previous deploy), check `/version`,
  unpause. Rollback criteria and the drill: Lesson 12.09. Target: under five minutes from decision to healthy.
- **Abuse of the public demo:** pause, revoke the key in `MASTERY_SERVICE_API_KEYS`, lower `BUDGET_PER_USER_DAY_USD`, redeploy, unpause.

## Postmortem template

```markdown
# <date> <one-line summary>
- Impact: who, how many runs failed or were slow, for how long (times in your zone)
- Detection: which alert, how long after the start
- Timeline: start, detected, mitigated, resolved
- Root cause: (the "why" behind the "what")
- What went well / what didn't
- Actions: owner, due date (each one makes this class of incident less likely or shorter)
```
Blameless: describe systems and decisions, not people.
