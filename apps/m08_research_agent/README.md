# Research-and-write agent (Project 08 app)

The Project 08 graph (`mastery.graphs.research.build_research_graph`) served by `langgraph dev`:

```
clarify_question (⏸️ if vague) → plan → research [search_docs → search_web] → draft → approval (⏸️) → finalize
```

```bash
cd apps/m08_research_agent
conda activate lc-mastery
langgraph dev            # Safari or Brave: add --tunnel
```

- **Studio** opens on the graph. Start a run with `{"question": "Battery?"}` to see the clarifying interrupt, or a full question to go straight to the approval interrupt. Resume with `{"action": "approve"}`, `{"action": "edit", "text": "..."}` or `{"action": "reject", "feedback": "make it shorter"}`.
- **Agent Chat UI** (stretch): the graph's state has no `messages` key, so it is not a chat graph; use Studio. Project 08's README describes the stretch goal: a thin chat wrapper graph with a `messages` key.
- **Keys:** none needed (offline models). With `GROQ_API_KEY` in `.env`: live models and Groq browser search (💸 free tier). `MASTERY_OFFLINE=1 langgraph dev` forces offline.
- **Persistence:** the dev server keeps threads in memory and saves them to `.langgraph_api/` (git-ignored) between restarts of `langgraph dev`. Pass the user for the preferences store with the run: `context={"user_id": "ana"}`. Project 08's notebook shows durable SQLite persistence explicitly.
