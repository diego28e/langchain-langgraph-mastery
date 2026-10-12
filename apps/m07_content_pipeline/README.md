# `apps/m07_content_pipeline` — the Project 07 graph as a LangGraph app

Used in [Lesson 07.06](../../modules/07-langgraph-fundamentals/07-06-app-structure-and-studio.ipynb) and [Project 07](../../modules/07-langgraph-fundamentals/project/README.md).

| File | What it is |
|---|---|
| `langgraph.json` | Which graph to serve (`content_pipeline` → `./pipeline.py:graph`), dependencies (`.`; the `mastery` package comes from your editable install), and the `.env` to load (the repo's) |
| `pipeline.py` | Builds the graph with `mastery.graphs.content.build_content_graph`: Groq models when `GROQ_API_KEY` is set, scripted offline models otherwise (or with `MASTERY_OFFLINE=1`) |

## Run it (Git Bash, `(lc-mastery)` active)

```bash
cd apps/m07_content_pipeline
langgraph dev                 # opens Studio in your browser; API at http://127.0.0.1:2024
# no browser? langgraph dev --no-browser, then open the "Studio UI" link it prints
```

In Studio, pick **content_pipeline**, enter `{"topic": "Battery care in winter"}` and run. Stop with **Ctrl + C**.

- `langgraph dev` is an in-memory development server: runs, threads and checkpoints disappear when you stop it. Not for production (Module 13).
- Studio needs a (free) LangSmith account to open; the local API works without one.
- Port in use? `langgraph dev --port 2025`.
