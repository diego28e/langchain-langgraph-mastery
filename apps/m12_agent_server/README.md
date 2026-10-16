# m12_agent_server: the support desk on LangGraph's Agent Server (Lesson 12.08, optional)

The same Orbita Cloud desk as [`apps/m12_service`](../m12_service/), served by the Agent Server
(what LangSmith Deployment runs) instead of our FastAPI app. Use it to compare; Module 12 ships
`m12_service`.

| File | What it does |
|---|---|
| `langgraph.json` | Manifest: installs the repo (`../..`), graph `support_desk`, `auth.py`, `../../.env` |
| `graph.py` | Builds the handoffs desk. DEMO (default): offline model, free. LIVE: `MASTERY_SERVICE_MODE=live` + `GROQ_API_KEY` (about 4–6K tokens per run) |
| `auth.py` | Custom auth: demo keys or JWTs (`ServiceSettings`), owner filters, server-set `context`, only managers answer approvals or change assistants |

## Run it locally (Git Bash, course env active)

```bash
cd apps/m12_agent_server
langgraph dev            # API on http://127.0.0.1:2024, prints a Studio link
```

Call it with a demo key (from `MASTERY_SERVICE_API_KEYS`, defaults in `ServiceSettings`):

```python
from langgraph_sdk import get_client
client = get_client(url="http://127.0.0.1:2024", headers={"Authorization": "Bearer demo-customer"})
```

`langgraph dev` keeps everything in memory and is for development only.
`MASTERY_DEMO_DELAY_S=0.5` slows the offline model so you can try double texting.

## Hosting (checked 2026-10-16)

- **LangSmith Cloud**: needs the Plus plan; deploy from a GitHub fork, set secrets in the deployment.
- **Standalone**: your containers plus Postgres and Redis, with an Enterprise license key.
- Webhooks: loopback and relative URLs are refused by default. In production, set
  `"webhooks": {"url": {"allowed_domains": [...], "require_https": true}}` in `langgraph.json`.
