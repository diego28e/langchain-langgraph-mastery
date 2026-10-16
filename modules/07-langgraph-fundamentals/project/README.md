# Project 07 — Content Pipeline Graph

> **Module 07 · LangGraph Fundamentals** · ⏱️ 5–7 hours · Docs verified 2026-10-12

**Goal:** a graph that turns a topic into a reviewed blog-post draft using several workflow patterns: an outline (structured output), parallel research (`Send`), a draft, and an evaluator-optimizer loop (critique ⟲ revise, at most 3 revisions). The same graph runs in the notebook, under `langgraph dev` and in Studio, and every run logs cost and latency per node.

| File | What it is |
|---|---|
| [`07-project-content-pipeline.ipynb`](07-project-content-pipeline.ipynb) | **Starter.** Runs top to bottom from the start. Four `# TODO` blocks are yours to complete |
| [`solutions/07-project-content-pipeline-solution.ipynb`](solutions/07-project-content-pipeline-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried, or when you are stuck on one TODO |
| [`apps/m07_content_pipeline/`](../../../apps/m07_content_pipeline/) | The **app**: `pipeline.py` + `langgraph.json`, served by `langgraph dev` (Lesson 07.06) |
| [`src/mastery/graphs/content.py`](../../../src/mastery/graphs/content.py) | The reference graph (`build_content_graph`), prompts, the offline models and the corpus researcher. The app and the tests use it |

Research comes from the Module 06 corpus ([`data/samples/rag/corpus/`](../../../data/samples/rag/corpus/)) with BM25: offline, free, and every note is a copied sentence with its source file. Test topics (`TEST_TOPICS`): *Battery care in winter*, *Calibrating the sensors*, *Mounting the station outdoors*. Outputs go to the git-ignored `data/outputs/m07/`.

## Requirements

1. **Nodes:** `plan_outline` → parallel `research_section` (fan-out with `Send`) → `write_draft` → `critique` → conditional loop to `revise` (max 3 iterations) → `finalize`.
2. **Typed state with reducers** (`ContentState`: `sections`, `scores`, `run_log` use `operator.add`). **Structured outputs** for the outline (`Outline`) and the critique (`Critique`, score 1–10 + issues).
3. **Graph image** in the notebook. The **app** runs under `langgraph dev` and is inspected in **Studio**.
4. **Cost/latency per run:** seconds per node from `run_log` (every node is `@timed`), tokens and $ from `get_usage_metadata_callback` + `mastery.pricing`; saved to `data/outputs/m07/project07-runs.json`. With LangSmith tracing on, the same numbers are in the traces.

| TODO | Where | What |
|---|---|---|
| 1 | Step 2 | `fan_out`: one `Send("research_section", {"title", "question"})` per outline section |
| 2 | Step 2 | `revise`: rewrite the draft from `critique.issues`; `iteration + 1` |
| 3 | Step 2 | `after_critique`: `"finalize"` at score ≥ `THRESHOLD` (8) or after `MAX_ITERATIONS` (3) revisions, else `"revise"` |
| 4 | Step 5 | `cost_latency_table`: one row per node (calls, seconds, share) + a `TOTAL` row with tokens and $ |

## Acceptance criteria (7 checks in Step 7)

- **Deterministic termination:** with a critic that is *never* satisfied, the run still ends after exactly 3 revisions (the counter ends the loop, not the model, not `recursion_limit`). The graph also sets a tight `recursion_limit` (`content_recursion_limit`, Lesson 07.03), so a bug loop fails fast.
- **Same app in the notebook and in Studio:** your graph has the app's node names, and the app (started with `langgraph dev` from the notebook) returns the same scores offline. With `RUN_SERVER = False`, or if the server doesn't start, these two checks show ⏭️ skipped and are not counted as passes.
- **Grounded citations:** every `[source: …]` in every final post is a source the research returned (a made-up citation is caught), and the loop actually ran at least once (offline). The critic's score is the model's opinion; this check is evidence. LIVE, the critic is `gpt-oss-120b`, not the writer.
- **One research note per outline section, each with at least one source** (Send + reducer) and a **cost/latency table** for every run (every node that ran, plus `TOTAL`: `revise` only appears when a revision was needed).
- **Restart & Run All** passes with `GROQ_API_KEY` and without any key. Outputs cleared; `data/outputs/` never committed.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Graph design | Send + reducer research, a revise loop that ends after exactly 3 revisions | A Mermaid sketch in your notes made before the code, and how the real graph differed |
| Grounding | Every `[source: …]` was returned by research; the made-up citation is caught | A second grounding check of your own (e.g. each section cites its own note) |
| Notebook vs Studio | Same node names and offline scores as the app | Forks one Studio run and explains the different result |
| Cost and latency | A cost/latency table for every run, with `TOTAL` | Compares two writer models (stretch) by score and cost per post |
| Hygiene | Restart & Run All with and without a key; outputs cleared | Functional API version (stretch) and a decision-log entry on which you'd keep |

## Modes

- **LIVE** (`GROQ_API_KEY` set): `openai/gpt-oss-20b` (`reasoning_effort="low"`) plans and writes; `openai/gpt-oss-120b` critiques. Roughly 6–12k tokens per pipeline run, and LIVE runs it 5–6 times (first build, 3 topics, the server run, acceptance check 1): about 35–70k tokens, free on the free tier, well under $0.05 at paid prices. `LIVE_TOPICS = 1` cuts only the topic runs. The server step uses the same key from `.env`.
- **OFFLINE DEMO** (no key): `offline_models()` scripts the planner (3 sections), the writer (fixes one issue per revision) and the critic (4 + 2 per fixed issue: intro, citations, conclusion). Reference result: scores **[4, 6, 8]**, 2 revisions on every topic, 7/7 checks. The untouched starter passes 1/7, with ❌ pointing at the TODOs.

## Run it in Studio (once, by hand)

In a second Git Bash window, with `(lc-mastery)` active:

```bash
cd apps/m07_content_pipeline
langgraph dev          # Safari or Brave: langgraph dev --tunnel
```

Open the Studio link it prints, type a topic, and watch `critique` ⇄ `revise`. No key → offline models (free); with a key → live models.

## Stretch goals

- **Functional API version** (Step 8, `RUN_STRETCH = True`): the same pipeline as one `@entrypoint` with a `while` loop and parallel `@task` research. Compare readability, then log your choice in `docs/decision-log.md`.
- **Web research:** swap `corpus_researcher()` for `web_researcher(tool)` with Module 05's `web_search` tool (💸 one Groq browser-search call per section) and compare the drafts.
- **Stronger writer (paid):** keep `gpt-oss-20b` as planner/critic and use a bigger writer (`get_model("reasoning")` or an OpenAI model): does the score go up, and what does it cost per post?

## Stack

Free: Groq (gpt-oss-20b), BM25 over the local corpus, `langgraph dev` + Studio (free LangSmith account). Paid alternatives: a stronger writer model, LangSmith Plus for longer trace retention, LangSmith Deployment instead of `langgraph dev` (Module 12).
