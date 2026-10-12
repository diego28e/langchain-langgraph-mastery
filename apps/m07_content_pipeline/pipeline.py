"""Project 07 content pipeline as a LangGraph app (Lesson 07.06, Project 07).

Run from this folder, in the course environment (Git Bash, `(lc-mastery)` active):

    langgraph dev

`langgraph dev` imports this file and serves the graph named in langgraph.json ("content_pipeline").
Keys come from the repo's .env ("env" in langgraph.json).

Models:
- `GROQ_API_KEY` set → gpt-oss-20b plans, writes and critiques (💸 free tier, ~6-12k tokens per run).
- No key, or `MASTERY_OFFLINE=1` → scripted offline models (free), so Studio works without any key.
Research always comes from the Module 06 corpus (offline, BM25). The graph itself is
`mastery.graphs.content.build_content_graph`: the same code the Project 07 notebook runs.
"""

from __future__ import annotations

import os

from mastery.config import is_set, load_env
from mastery.graphs.content import (
    build_content_graph,
    corpus_researcher,
    offline_models,
)

load_env()
LIVE = is_set("GROQ_API_KEY") and os.environ.get("MASTERY_OFFLINE", "") not in {"1", "true", "yes"}

if LIVE:
    from mastery.models import get_model

    _llm = get_model("fast", temperature=0, reasoning_effort="low")
    models = {"planner": _llm, "writer": _llm, "critic": _llm}
else:
    models = offline_models()

graph = build_content_graph(models["planner"], models["writer"], models["critic"], corpus_researcher(),
                            max_iterations=3, threshold=8)
