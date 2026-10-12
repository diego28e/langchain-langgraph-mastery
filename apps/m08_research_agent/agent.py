"""Project 08 research-and-write agent as a LangGraph app (Lesson 08.03, Project 08).

Run from this folder, in the course environment (Git Bash, `(lc-mastery)` active):

    langgraph dev

Studio shows the graph; a run pauses at `clarify_question` (vague requests) and at `approval`.
Answer in Studio's interrupt panel with {"action": "approve"}, {"action": "edit", "text": "..."}
or {"action": "reject", "feedback": "..."}. The server brings its own checkpointer and store,
so this file passes neither. Keys come from the repo's .env ("env" in langgraph.json).

Models and search:
- `GROQ_API_KEY` set (and `MASTERY_OFFLINE` unset) → gpt-oss-20b clarifies, plans and writes;
  web search uses Groq's built-in browser search (💸 free tier; ~5-15k tokens per run).
- Otherwise → scripted offline models, no web results (free). Docs search is always the offline
  BM25 search over the Module 06 corpus.
"""

from __future__ import annotations

import os

from mastery.config import is_set, load_env
from mastery.graphs.research import (
    build_research_graph,
    corpus_docs_search,
    offline_models,
    offline_web_search,
    web_tool_search,
)

load_env()
LIVE = is_set("GROQ_API_KEY") and os.environ.get("MASTERY_OFFLINE", "") not in {"1", "true", "yes"}

if LIVE:
    from mastery.models import get_model
    from mastery.web_search import make_web_search_tool

    _llm = get_model("fast", temperature=0, reasoning_effort="low")
    models = {"clarifier": _llm, "planner": _llm, "writer": _llm}
    web = web_tool_search(make_web_search_tool("groq", model=_llm))
else:
    models = offline_models()
    web = offline_web_search()

graph = build_research_graph(models, web_search=web, docs_search=corpus_docs_search())
