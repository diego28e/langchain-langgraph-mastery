# Project 09 — Multi-Agent Support Desk

> **Module 09 · Multi-Agent Systems** · ⏱️ 6–8 hours · Docs verified 2026-10-12 · the first project of Part 2

**Goal:** a customer-support system for **Orbita Cloud**, a fictional SaaS that stores and charts data from weather stations. You build the **same** desk twice from the same specialists (billing, technical, account), run both on a 15-conversation test set, and write down which one you would ship and why.

| File | What it is |
|---|---|
| [`09-project-support-desk.ipynb`](09-project-support-desk.ipynb) | **Starter.** Runs top to bottom from the start. Four `# TODO` blocks are yours to complete |
| [`solutions/09-project-support-desk-solution.ipynb`](solutions/09-project-support-desk-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried, or when you are stuck on one TODO |
| [`data/samples/support-desk/`](../../../data/samples/support-desk/) | `faq/` (billing, technical, account FAQs in Markdown), `customers.json` (3 customers, invoices, service status), `conversations.jsonl` (the test set) |
| [`src/mastery/agents/support.py`](../../../src/mastery/agents/support.py) | The desk: `SupportDesk`, `make_support_tools` (refunds over $50 call `interrupt()`), `faq_search`, `make_specialists`, prompts, `offline_model`, `run_conversation`, `score`, `evaluate`, and the reference builders from the lessons |
| [`src/mastery/agents/specialists.py`](../../../src/mastery/agents/specialists.py) | `Specialist`, `subagent_tool`, `handoff_tool`, `handoff_graph` (what you assemble in TODO 1–2) |
| [`src/mastery/agents/metrics.py`](../../../src/mastery/agents/metrics.py) | `UsageMeter`: model calls and tokens, total and per agent |

Outputs go to the git-ignored `data/outputs/m09/` (`project09-report.json`, `project09-ADR.md`, `project09-acceptance.json`); LIVE mode also builds a small Chroma index in `data/vectorstores/`.

## Requirements

1. **Pattern A (handoffs):** triage → billing / technical / account agents, each with its own tools and system prompt. Agents are nodes of one graph; `transfer_to_*` tools move the conversation (`Command(graph=Command.PARENT)`), and the next user turn starts at the active agent.
2. **Pattern B (subagents):** one coordinator calling the **same** specialists as tools (`billing_agent`, `technical_agent`, `account_agent`).
3. **Shared RAG** over the product FAQ with `mastery.rag` (BM25 offline; Chroma + local embeddings in LIVE). **HITL before any refund over the threshold** ($50, `REFUND_THRESHOLD`): `issue_refund` pauses; a billing manager approves, edits the amount, or rejects with feedback.
4. **A 15-conversation test set**; compare A vs B on resolution correctness, model calls, tokens and latency (`UsageMeter`).

| TODO | Where | What |
|---|---|---|
| 1 | Step 3 | `build_pattern_a`: `handoff_tool(d, carry="turn")` per domain, `make_specialists(tools, handoffs=True)`, a triage `create_agent` with only transfer tools, each specialist with transfers to the **other** domains, then `handoff_graph(agents, entry="triage", checkpointer=...)` |
| 2 | Step 4 | `build_pattern_b`: `subagent_tool(spec.build(model), name=f"{d}_agent", ...)` per domain, a coordinator `create_agent(..., system_prompt=COORDINATOR_PROMPT, checkpointer=...)` |

Build both patterns yourself: wrapping the reference `build_handoffs_desk` / `build_subagents_desk` fails check 1–2. Each step has a collapsed **Hint** with the goal first and code only if you're stuck.
| 3 | Step 5 | `manager_review(payload)`: approve refunds of the **full** invoice amount; reject partial refunds with `{"action": "reject", "feedback": ...}` |
| 4 | Step 7 | `write_adr(reports, path)`: context, the measured table, a `## Recommendation` section, consequences, and the specialist that would benefit from a harness (Module 11) |

## The test set

`data/samples/support-desk/conversations.jsonl`, one conversation per line:

| IDs | What they test |
|---|---|
| S01, S04 | Refunds under the threshold (no pause) |
| S02, S03 | Refunds over the threshold: the manager approves (S02, full refund) or rejects (S03, partial refund) |
| S05 | Invoice lookup |
| S06, S07, S08 | Technical: 429 errors (FAQ), sync outage (service status), webhook retries (FAQ) |
| S09, S10, S11 | Account: password reset, locked account, email change |
| S12 | Repeat request: two billing turns (the second without the customer ID) |
| S13 | Domain switch: billing, then technical |
| S14 | Multi-domain in one message: a refund **and** a 429 question |
| S15 | Vague first turn ("I need some help"), then the details |

Each line has `turns`, an optional manager `decision` (used by the lessons' default reviewer; the project uses **your** `manager_review`), and `expect`: tools that must run (from the desk's event log, so it works for every pattern), the number of pauses, and text the final answer must contain. `score()` checks **outcomes**, not just tool names: the refunds actually issued must match `expect.refunds` (invoice, customer and amount, each once), no side-effect tool (refund, reset, unlock, email change) may run that the conversation didn't ask for, and any refund over $50 issued without the manager fails. Pass the signed-in customer with `run_conversation(..., context=SupportContext("C-1003"))` (`from mastery.agents.support import SupportContext`): the tools then act only on that customer's account, whatever the chat text claims (Lesson 09.02 Part 8).

## Acceptance criteria (9 checks in Step 8)

1–2. **Pattern A is your handoffs graph** (built with `handoff_tool` + `handoff_graph`) and **Pattern B your coordinator** (built with `subagent_tool`), not the reference builders.
3–4. **Both patterns pass ≥ 12/15 conversations** (offline: all 15 run; LIVE: ≥ 80% of the `LIVE_LIMIT` conversations that ran).
5. **Refunds over the threshold pause exactly once** (S02 and S03, both patterns; parallel refunds count one review each).
6. **No refund over $50 is issued without the manager.**
7. **The manager policy works:** S02 refunds exactly $199 on INV-2001, S03 refunds nothing, and every synthetic policy probe in Step 5 (partial, unknown invoice, over-amount…) gets the right decision.
8. **ADR** in `data/outputs/m09/project09-ADR.md` with Context, Evidence, Recommendation and Consequences sections, naming the recommended pattern.
9. **ADR Evidence table** with one row per pattern carrying **its** measured pass count and model calls.

Plus: **Restart & Run All** passes with `GROQ_API_KEY` and without any key. Outputs cleared; `data/outputs/` and `data/vectorstores/` never committed.
- **Restart & Run All** passes with `GROQ_API_KEY` and without any key. Outputs cleared; `data/outputs/` and `data/vectorstores/` never committed.

## Modes

- **LIVE** (`GROQ_API_KEY` set): `openai/gpt-oss-20b` (`reasoning_effort="low"`) for every agent; FAQ search over a Chroma index with `default_embeddings()` (fastembed `BAAI/bge-small-en-v1.5` if the `[embeddings]` extra is installed, else the offline hashing embeddings). `LIVE_LIMIT = 5` conversations per pattern by default (≈ 40–80 model calls in total, 30–60k tokens: free on the free tier). Set `LIVE_LIMIT = 15` for the full acceptance run; on the free tier you may hit the requests-per-minute limit, which `get_model` retries (slower, not broken). Expect a few ❌: read the failing rows before changing prompts.
- **OFFLINE DEMO** (no key): `offline_model()` is rule-based: it reads its role from the system prompt (triage, billing, technical, account, coordinator) and its options from the tool names it is bound to, so your TODO code drives it like a real model. Reference result: A 15/15 with 53 model calls, B 15/15 with 71, 9/9 checks. The untouched starter passes 0/9, with ❌ pointing at the TODOs.

## Stretch goals

- **Pattern C** (Step 9): `build_custom_desk` routes refund-only messages through the custom refund workflow of Lesson 09.05 (parse → validate → approve → issue → reply) and everything else through the handoffs desk. Offline it needs 42 model calls for the test set. Build your own version of the workflow instead of the reference one, and add a duplicate-charge rule.
- **Harness candidate:** name the specialist that would benefit from a full harness (planning, a filesystem, its own subagents) in your ADR. Module 11 rebuilds it as a deep agent.
- **Stronger coordinator (paid or free-tier 120b):** give only Pattern B's coordinator `get_model("reasoning")` and compare pass rate and tokens.
- **One-agent handoffs:** add `build_single_agent_desk` (Lesson 09.03 Part 1) as a third column.
- **Harder conversations:** add 5 of your own (typos, two refunds in one message, "the invoice from last month") to a copy of the JSONL.

## Stack

Free: Groq (`gpt-oss-20b`), Chroma + fastembed (local embeddings) or BM25, `InMemorySaver` (swap in SQLite from Module 08 to keep threads across restarts). Paid alternative: a stronger coordinator model (Pattern B's hottest path).

## Before you commit

- [ ] Restart & Run All passes (LIVE and without a key).
- [ ] All TODOs done; 9/9 acceptance checks; ADR and findings written; decision logged in [`docs/decision-log.md`](../../../docs/decision-log.md).
- [ ] Outputs cleared (`jupyter nbconvert --clear-output --inplace <notebook>`); no keys in outputs; `data/outputs/` and `data/vectorstores/` not committed.

---

← [Module 09 README](../README.md) · [Course outline](../../../COURSE_OUTLINE.md#project-09--multi-agent-support-desk) · Next: [Module 10 — Testing, Evaluation & Observability](../../10-testing-evaluation-observability/README.md) →
