# Module 04 — Middleware, Guardrails & Human-in-the-Loop

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 04](../../COURSE_OUTLINE.md#module-04--middleware-guardrails--human-in-the-loop)

**Goals:** Use middleware, the defining feature of `create_agent`, to add reliability, safety, and human oversight without rewriting the agent loop. Understand prompt injection and tool security.

**Estimated time:** 1.5–2 weeks (about 13.5–16.5 hours of lessons plus 5–7 hours for the project).

## Before you start this module

Run this **once**, in **Git Bash**, from the **repo root**, with the **`lc-mastery`** environment active (the prompt starts with `(lc-mastery)`).

```bash
cd ~/path/to/langchain-langgraph-mastery   # your clone; quote the path if it has spaces
conda activate lc-mastery
git pull                                   # get this module's files
python -m pip install -e ".[dev]"          # re-run after every pull: new modules add packages
python -m pytest -q                        # expect: "... passed" and no failures (offline, no keys)
python -c "import mastery.middleware as m; print('middleware ok', len(m.__all__))"   # expect: middleware ok 14
```

| | |
|---|---|
| 🔑 Keys | `GROQ_API_KEY` (optional: without it 💸 cells print `⏭️ Skipped`). `LANGSMITH_API_KEY` (optional, free) to see redacted traces in 04.05 and the project. No new keys |
| 💰 Cost | $0 on the Groq free tier. The safety models are cheap and small: `openai/gpt-oss-safeguard-20b` ($0.075 / $0.30 per 1M tokens in/out) and `meta-llama/llama-prompt-guard-2-86m` ($0.04 per 1M), both **Preview** models on Groq (checked 2026-10-12) |
| 📦 Optional extras | None. Every middleware in this module ships with `langchain` (already in `[dev]`) |
| ✅ Ready when | `pytest` shows no failures and `middleware ok 14` prints |

If `pip install` or `pytest` fails, see the [setup guide's troubleshooting](../00-foundations/00-02-create-course-env.md#troubleshooting) (SSL certificate errors on Anaconda: Step 4b).

## How to work through this module

1. **Do [Before you start this module](#before-you-start-this-module) first** (once per pull). Module 04 adds the `mastery.middleware` package (token budget, audit log, role filter, redaction, injection helpers) and a synthetic inbox in `data/samples/inbox/`.
2. **Start Jupyter from the repo root** (`jupyter lab` in Git Bash) and pick the **Python (lc-mastery)** kernel in every notebook.
3. **Go in order.** 04.01 is the mental model (hooks and their order) plus this module's debugging skill; 04.02 tours the prebuilt middleware; 04.03 writes your own; 04.04–04.05 are safety (PII, policies, prompt injection); 04.06 pauses for a human. The project stacks all of it.
4. **Read the cell markers.** 🧪 = offline (scripted model, free) · 🌐 = network, no tokens · 💸 = calls a model (free-tier quota). No key? Every 💸 cell prints `⏭️ Skipped`, so **Restart & Run All** always completes.
5. **Nothing is ever really sent.** All "email" tools write files to `data/outputs/m04/` (git-ignored). The inbox is fictional; its card numbers are public test numbers.
6. **Before you commit:** *Kernel → Restart Kernel and Run All Cells…*, *Edit → Clear Outputs of All Cells*, save, then `python -m pytest -q`.

## Lessons

| Lesson | Title | Notebook | Time | Keys |
|---|---|---|---|---|
| 04.01 | Middleware mental model and hooks | [`04-01-middleware-overview.ipynb`](04-01-middleware-overview.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 04.02 | Prebuilt middleware tour | [`04-02-prebuilt-middleware.ipynb`](04-02-prebuilt-middleware.ipynb) | 150–180 min | `GROQ_API_KEY` (optional) |
| 04.03 | Writing custom middleware | [`04-03-custom-middleware.ipynb`](04-03-custom-middleware.ipynb) | 150–180 min | `GROQ_API_KEY` (optional) |
| 04.04 | Guardrails: PII, content policy, output validation | [`04-04-guardrails.ipynb`](04-04-guardrails.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 04.05 | Prompt injection and tool security | [`04-05-prompt-injection-and-tool-security.ipynb`](04-05-prompt-injection-and-tool-security.ipynb) | 150–180 min | `GROQ_API_KEY`, `LANGSMITH_API_KEY` (both optional) |
| 04.06 | Human-in-the-loop for agents | [`04-06-human-in-the-loop.ipynb`](04-06-human-in-the-loop.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |

**What each lesson gives you**

- **04.01:** the six hooks (`before_agent`, `before_model`, `wrap_model_call`, `wrap_tool_call`, `after_model`, `after_agent`) printed live in the order they run; how two middleware nest; node-style vs wrap-style powers (`jump_to`, short-circuit, retry, `override`); the **debugging skill** (below).
- **04.02:** model retry, model fallback (120b → 20b), tool retry, tool error, model and tool call limits, LLM tool selector, context editing and the to-do list, each with a failure you can see, then **measured** (model calls, tool calls, tokens) in one table and in LangSmith.
- **04.03:** decorator vs class middleware; custom state; a role-based tool filter, a request logger and a token-budget guard built by hand, then their tested versions in `mastery.middleware`; unit-testing a hook without an agent.
- **04.04:** `PIIMiddleware` with `redact` / `mask` / `hash` / `block` and a custom detector; input vs output vs tool-result checks; a before-agent rule filter and an after-agent output validator; a bring-your-own-policy check with `openai/gpt-oss-safeguard-20b`, failing closed.
- **04.05:** direct vs **indirect** injection (a poisoned email read by a tool) shown end to end; six defences in layers: least-privilege tools, allow-lists, fencing untrusted text, input classification with Llama Prompt Guard 2, output checks, HITL on side effects; plus **trace redaction** (LangSmith anonymizer, `TracePolicy`).
- **04.06:** `HumanInTheLoopMiddleware` with approve / edit / reject / respond; `version="v2"` results and `.interrupts`; resuming with `Command(resume=...)`; several decisions at once; conditional `when=` policies; why HITL needs a checkpointer, and a pause that survives a kernel restart.

## Project

**[Project 04 — Safe Email-Triage Agent](project/README.md)**: an agent that reads the fake inbox in `data/samples/inbox/`, returns a `TriageResult(priority, category, needs_reply, summary)` per email, drafts replies, and only "sends" (writes to `data/outputs/m04/outbox/`) after a human approves. Middleware stack: PII redaction, HITL on `send_email`, tool-call limit, model fallback 120b → 20b, and an audit log. One email is a **prompt injection**; the agent must refuse it and log it, 5 out of 5 runs.

| File | Use |
|---|---|
| [`project/README.md`](project/README.md) | Spec, acceptance criteria, modes, stretch goals |
| [`project/04-project-email-triage.ipynb`](project/04-project-email-triage.ipynb) | **Starter** with four `# TODO`s (runs from day one, also offline) |
| [`project/solutions/04-project-email-triage-solution.ipynb`](project/solutions/04-project-email-triage-solution.ipynb) | **Reference solution** (open after trying) |

## Jupyter skill in this module

**Debugging: `%debug`, `%pdb`, `%xmode` and reproducible failing cells** (Lesson 04.01, Part 5; used again in 04.03):

| Skill | Where |
|---|---|
| Read a middleware traceback: the `During task with name '...'` line names the hook that failed | 04.01 |
| `%xmode Minimal` / `Context` / `Verbose` to shorten or expand tracebacks | 04.01 |
| `%debug` right after a failing cell (post-mortem: `p state`, `up`, `q`) | 04.01 |
| `%pdb on` / `%pdb off`: open the debugger automatically on every error | 04.01 |
| A **reproducible failing cell**: a flag (`SHOW_BUG = False`) so Run All stays green, plus a minimal repro that calls the hook directly | 04.01, 04.03 |

## `src/mastery` increment

| File | What it does | Tests |
|---|---|---|
| [`src/mastery/middleware/budget.py`](../../src/mastery/middleware/budget.py) | `TokenBudgetMiddleware(run_limit=, thread_limit=, exit_behavior="end" \| "error")` | [`tests/unit/test_middleware.py`](../../tests/unit/test_middleware.py) |
| [`src/mastery/middleware/audit.py`](../../src/mastery/middleware/audit.py) | `AuditLogMiddleware(path)`: redacted JSONL events (`run_start`, `model_call`, `tool_call`, …) and `record()` for your own; `read_audit_log()` | same |
| [`src/mastery/middleware/roles.py`](../../src/mastery/middleware/roles.py) | `RoleToolFilterMiddleware(policy)`: hides and blocks tools per `runtime.context` role; fails closed | same |
| [`src/mastery/middleware/redaction.py`](../../src/mastery/middleware/redaction.py) | `redact_text`, `redact_obj`, `PII_PATTERNS` for logs and traces | same |
| [`src/mastery/middleware/injection.py`](../../src/mastery/middleware/injection.py) | `injection_signals`, `fence_untrusted`, `parse_guard_score` (Prompt Guard replies) | same |

## Production notes

> ⚠️ **Production note: the safety classifiers in 04.04–04.05 are Groq preview models.**
> `openai/gpt-oss-safeguard-20b` and `meta-llama/llama-prompt-guard-2-*` can be retired at short notice. In production: never let one classifier be your only defence. Layer deterministic rules, a classifier, least-privilege tools, and human approval. Decide what happens when the classifier is down (usually: fail closed for risky actions). Pin the model ID, monitor its error rate, and keep a fallback classifier.

Each lesson has its own production notes; they are collected in [`docs/production-notes.md`](../../docs/production-notes.md).

## Research checkpoint

List the current prebuilt middleware on the [Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) page and log one that did not exist when this course was written (Lesson 04.02 prints the list the course was written against). Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

✅ Built (docs verified 2026-10-12).

---

← [Module 03](../03-memory-and-context/README.md) · [Course outline](../../COURSE_OUTLINE.md) · [Module 05](../05-mcp-and-external-tools/README.md) →
