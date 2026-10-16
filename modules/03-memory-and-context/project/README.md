# Project 03 — Study Buddy with Memory

> **Module 03 · Memory & Context Engineering** · ⏱️ 4–6 hours · Docs verified 2026-10-12

**Goal:** a tutoring agent that remembers the learner across sessions.

| File | What it is |
|---|---|
| [`03-project-study-buddy.ipynb`](03-project-study-buddy.ipynb) | **Starter.** Runs top to bottom from the start. Four `# TODO` blocks are yours to complete |
| [`solutions/03-project-study-buddy-solution.ipynb`](solutions/03-project-study-buddy-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried, or when you are stuck on one TODO |

## Requirements

1. **Short-term memory:** a SQLite checkpointer (`make_checkpointer("sqlite", ...)`). Conversations survive kernel restarts, and you demonstrate it.
2. **Long-term memory:** a SQLite store with namespace `("learners", user_id)` holding the learner **profile**, **weak topics** and **preferred explanation style**, written by a `remember_fact(kind, fact)` tool.
3. **`SummarizationMiddleware`** keeps every model call under a token budget you choose (the notebook uses 900 tokens for system prompt + messages + tool schemas; the tool schema alone is about 180 tokens on every call). Show before/after token counts.
4. **Runtime context** (`LearnerContext(user_id)`) carries the user id. Two different users must not see each other's memories **or threads**: a thread belongs to the user who first used it, and `chat()` refuses anyone else. A test cell proves it.

| TODO | Where | What |
|---|---|---|
| 1 | Step 2 | `remember_fact`: clean the fact, build the namespace from `runtime.context`, update the right key |
| 2 | Step 2 | `learner_memory(store, user_id)`: read profile, weak topics and style |
| 3 | Step 3 | `summarization(summary_model)`: `SummarizationMiddleware` with a trigger that respects the budget |
| 4 | Step 5 | At least four cross-user leakage checks |

## How the demo works

| Session | Thread | What happens | What it proves |
|---|---|---|---|
| 1 | `ana-s1` | Ana says who she is, what's hard (dividing fractions), how she likes explanations (drawings, pizza). The tutor calls `remember_fact` three times | Store writes from a tool, keyed by `runtime.context` |
| 2 | `ana-s2` | Ten practice turns with long replies | Summaries keep each call under the budget |
| restart | — | All SQLite connections closed and reopened; a separate Python process reads both files | Persistence across restarts |
| 3 | `ana-s3` (new) | "What should we practise today?" | The tutor knows Ana's weak topic and style **only** from the store (injected into the system prompt) |
| Bruno | `bruno-s1`, `bruno-s2` | A second learner with his own fact | No cross-user leakage |

## Acceptance criteria

- The scripted 3-session demo shows that **session 3 uses facts from session 1**.
- **No cross-user leakage**: your own ≥4 checks (TODO 4) **and** a fixed suite that you don't edit: a positive control (Bruno's own fact is in his memory and prompt), none of Ana's stored items in Bruno's memory or prompt, Bruno's prompt identical when built from a store that never held Ana's data, and **thread ownership** (Bruno can't open `ana-s2`; `chat()` checks the thread's owner before any checkpoint is read).
- **Token budget respected**: no call in session 2 sends more than the budget, and at least one summary happened.
- **Restart & Run All** passes with only `GROQ_API_KEY`, and also without any key (OFFLINE DEMO).
- No secrets in outputs; outputs cleared; memory files (`data/outputs/memory/`) never committed.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Persistence | A thread survives a kernel restart, shown in the notebook | Also shows what a fresh thread id does and does not remember |
| Long-term memory | Profile, weak topics and style stored per user; session 3 uses a session-1 fact | Semantic search stretch, with one query where it beats a key lookup |
| Isolation | Your ≥ 4 leakage checks and the fixed suite pass | A leakage check of your own that fails on a deliberately broken namespace, then passes |
| Context budget | No session-2 call over the budget; at least one summary | A before/after table of tokens per call, with the cost of the summary calls |
| Hygiene | Restart & Run All in both modes; memory files never committed | A decision-log entry on what you'd store per user, and for how long |

## Modes

- **LIVE** (`GROQ_API_KEY` set): `openai/gpt-oss-20b` tutors and summarizes. About 30–40 short calls. The checks still run, but a real model words facts its own way (*"division of fractions"*), so read the transcript too.
- **OFFLINE DEMO** (no key): scripted stand-ins make the tool calls a good tutor would make, and session 3's reply is built **only from the system prompt it was sent**. If your memory code doesn't inject the facts, the reply doesn't contain them. With all TODOs done: **5/5 checks**. The untouched starter shows what's missing with ❌.

**Manual restart test:** run everything once, set `RESET_MEMORY = False` in Step 0, **Kernel → Restart Kernel**, run Steps 0–3 and then the session-3 cell. Ana is still remembered.

## Stretch goals

1. **Semantic memory search** with local embeddings: `make_store(..., embed=local_embeddings(), fields=["fact"])` (needs `python -m pip install -e ".[embeddings]"`; Lesson 03.04).
2. **`forget_fact` with confirmation**: a two-step tool (first call asks, `confirm=True` deletes). Module 04 replaces this with a proper human-in-the-loop interrupt.

## Stack

Free: Groq + SQLite + local embeddings. Paid (later): Postgres checkpointer and store (Module 12).
