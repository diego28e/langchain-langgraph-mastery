"""The Orbita Cloud support desk on LangGraph's Agent Server (Lesson 12.08, optional reference).

Run from this folder, in the course env (Git Bash, `(lc-mastery)` active):

    langgraph dev            # local Agent Server, in memory; Studio at the printed URL

The same desk as apps/m12_service, served by the Agent Server instead of our FastAPI app.
DEMO (default): the offline rule-based model, no key, no cost. LIVE: MASTERY_SERVICE_MODE=live
and GROQ_API_KEY in the repo's .env (about 4-6K tokens per run). The server brings its own
checkpointer, so the graph is compiled without one. Who the customer is comes from auth.py.
"""
from __future__ import annotations

import os

from mastery.agents.support import SupportDesk, build_handoffs_desk, make_support_tools, offline_model
from mastery.config import load_env

load_env()
LIVE = os.environ.get("MASTERY_SERVICE_MODE", "demo").strip().lower() == "live"

if LIVE:
    from langchain_core.rate_limiters import InMemoryRateLimiter

    from mastery.models import get_model

    _limiter = InMemoryRateLimiter(requests_per_second=0.4, check_every_n_seconds=0.1, max_bucket_size=2)

    def model_for(role: str):  # noqa: ANN201
        return get_model("fast", max_tokens=600, rate_limiter=_limiter)
else:
    from mastery.service.desk import slow

    # Simulated model latency for the double-texting demo (Lesson 12.08); 0 = instant.
    _delay = float(os.environ.get("MASTERY_DEMO_DELAY_S", "0") or 0)

    def model_for(role: str):  # noqa: ANN201
        return slow(offline_model(role), _delay)

desk = SupportDesk.load()
graph = build_handoffs_desk(model_for, make_support_tools(desk), checkpointer=None)
