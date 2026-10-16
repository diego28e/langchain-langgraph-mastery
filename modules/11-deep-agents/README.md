# Module 11 — Deep Agents

> **Part 2 — Pro (Modules 09–14)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 11](../../COURSE_OUTLINE.md#module-11--deep-agents)

**Goals:** Master **Deep Agents**, LangChain's open-source "batteries-included" agent harness for long-running, multi-step work. You first build a small harness yourself, so the abstraction is never magic. By the end you can design, build, secure, evaluate, and ship deep agents that plan, use a virtual filesystem with pluggable backends, delegate to subagents, manage their own context over long runs, load skills and long-term memory, pause for human approval, execute code safely in sandboxes, and stream progress to a UI. You also learn when **not** to use a harness.

**Estimated time:** about 42–56 h (≈ 5–7 weeks at 8 h/week): 11 core lessons, 1 lesson of frontier briefings, **1 use-case lab of your choice** (of 3), and the module project.

**Core vs frontier:** the **core lessons** (Lessons 11.01–11.11) teach skills that should outlast the next releases. The **frontier briefings** (Lesson 11.12) are short, dated sections on beta and fast-moving features (forked, async, and dynamic subagents, interpreters, rubric self-checks, agent protocols, Managed Deep Agents, Deep Agents Code). Expect to re-check and replace them; never build a core path on them without your own evals.

## Default model stack

This is the one module where the default model is **not** Groq. Deep agents run long, multi-step loops, so the course uses a model from the official Deep Agents suggested list that also has a free tier. The rest of the course stays on Groq. Lesson 11.01 ends with your first deep agent on this default; Lesson 11.02 runs the same task on the Groq option and the OpenAI benchmark and has you look up your live free-tier limits in Google AI Studio.

| Role | Course default | Why / caveats |
|---|---|---|
| Orchestrator (main deep agent) | **`google_genai:gemini-3.6-flash`** | **Stable** Gemini model (not preview; no shutdown date announced on Oct 11, 2026). One of the officially suggested models on [Deep Agents models](https://docs.langchain.com/oss/python/deepagents/models), with strong scores on the official eval suite. Function calling, structured outputs, thinking, 1,048,576-token input / 65,536-token output ([model card](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash)). Free tier with no billing account ([pricing](https://ai.google.dev/gemini-api/docs/pricing)) |
| Subagents / workers | `google_genai:gemini-3.6-flash` (same model) | One model means one quota to watch and one model to evaluate. Override `model` per subagent when you want to experiment |
| Web search inside subagents | `mastery/web_search.py`: Groq browser search by default (a regular tool that calls Groq, so `GROQ_API_KEY` is still needed), Tavily as a drop-in | Gemini's own *Grounding with Google Search* is **not available on the free tier** ([pricing](https://ai.google.dev/gemini-api/docs/pricing)), so the course keeps search as a tool |
| Documented option: Groq | `groq:openai/gpt-oss-120b` (orchestrator) · `groq:openai/gpt-oss-20b` (subagents) | The rest of the course's default, cheap and fast, 131K context. **Not** in the official Deep Agents eval matrix, and its free tier is tight (see the note below). Switch with `MASTERY_DEEP_MODEL` / `MASTERY_DEEP_SUBAGENT_MODEL` in `.env` |
| Paid benchmark | `openai:gpt-6-luna` (course benchmark), `openai:gpt-5.5` (officially suggested) | OpenAI models default to the Responses API in Deep Agents ([Models](https://docs.langchain.com/oss/python/deepagents/models)) |

Change the models with `MASTERY_DEEP_MODEL` / `MASTERY_DEEP_SUBAGENT_MODEL` in your `.env` (see [`.env.example`](../../.env.example)).

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 11.01 | Harness thinking: build a mini-harness, then `create_deep_agent` | `11-01-harness-and-first-deep-agent.ipynb` | ✅ Ready |
| 11.02 | Models, harness profiles, and token budgets | `11-02-models-profiles-and-budgets.ipynb` | ✅ Ready |
| 11.03 | The virtual filesystem and planning | `11-03-virtual-filesystem-and-planning.ipynb` | ✅ Ready |
| 11.04 | Backends, routing, and permissions | `11-04-backends-routing-permissions.ipynb` | ✅ Ready |
| 11.05 | Subagents and delegation (+ rebuild the Project 09 technical specialist as a deep agent) | `11-05-subagents-and-delegation.ipynb` | ✅ Ready |
| 11.06 | Context engineering for long-running agents | `11-06-context-engineering-long-runs.ipynb` | ✅ Ready |
| 11.07 | Skills and long-term memory | `11-07-skills-and-memory.ipynb` | ✅ Ready |
| 11.08 | Human-in-the-loop, guardrails, and fault tolerance | `11-08-hitl-guardrails-fault-tolerance.ipynb` | ✅ Ready |
| 11.09 | Code execution in sandboxes | `11-09-code-execution-sandboxes.ipynb` | ✅ Ready |
| 11.10 | Streaming deep agents to a UI | `11-10-streaming-to-a-ui.ipynb` | ✅ Ready |
| 11.11 | Evaluating and shipping deep agents | `11-11-evaluating-and-shipping-deep-agents.ipynb` | ✅ Ready |
| 11.12 | Frontier briefings (dated): subagent modes, interpreters, rubrics, protocols, managed runtimes | `11-12-frontier-briefings.ipynb` | ✅ Ready |

Lessons 11.01–11.11 are the core. Lesson 11.12 holds six short, independent briefings, each with a dated status line, to take right after the core lesson it extends: F1 forked subagents (after 11.05), F2 async subagents (after 11.05/11.10), F3 interpreters and dynamic subagents (after 11.09), F4 `RubricMiddleware` (after 11.11), F5 AG-UI, ACP, and A2A (after 11.10), and F6 Managed Deep Agents and a Deep Agents Code tour (after 11.11).

## Production notes

> ⚠️ **Production note: Deep Agents is pre-1.0, so pin it and expect API churn.**
> Patch releases ship every few days (0.7.21 on Sep 30, 0.7.22 on Oct 5, 0.7.23 on Oct 7, 2026), and real APIs changed within months: backend factory functions were deprecated in 0.5.0, namespace factories switched from `BackendContext` to a LangGraph `Runtime` in 0.5.2, relying on the default model (`model=None`) is deprecated since 0.5.3 and will be removed in 1.0, and v0.7 removed the planning tool from the default stack ([Backends: migrate from backend factories](https://docs.langchain.com/oss/python/deepagents/backends), [`create_deep_agent` reference](https://reference.langchain.com/python/deepagents/graph/create_deep_agent), [Deep Agents v0.7](https://www.langchain.com/blog/deep-agents-v0-7)). The course uses a floor + minor-version ceiling (`deepagents>=0.7.23,<0.8`) so lessons keep working while you learn. **In production:** pin the exact version (`deepagents==0.7.23`) in a lock file (for example `uv.lock`), upgrade deliberately on a branch, read the changelog for every bump, run your trajectory evals (Lesson 11.11) as an upgrade gate, treat `DeprecationWarning`s from `deepagents` as test failures in CI, and keep beta features behind your own small interface (`mastery/deep/`) so a breaking change touches one file.

> ⚠️ **Production note: the Gemini free tier is for learning, not for real data or real traffic.**
> Google's terms say that on unpaid quota, Google uses your prompts and responses to improve its products, **human reviewers may read them**, and you should not submit "sensitive, confidential, or personal information" ([Gemini API terms](https://ai.google.dev/gemini-api/terms)). Google does not publish fixed free-tier numbers: limits are per project (not per API key) and per model, are measured in requests per minute, tokens per minute, and requests per day (daily quotas reset at midnight Pacific time), are shown in Google AI Studio, and "are not guaranteed" ([Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)). The course uses public or synthetic data only, keeps tasks small, adds a rate limiter, and checks your live limits in AI Studio in Lesson 11.02. **In production:** use a paid tier (paid usage is not used to improve Google products), pin the exact model ID in config (`gemini-3.6-flash` is a stable ID; Google calls it its "previous generation" Flash, so watch the [deprecations page](https://ai.google.dev/gemini-api/docs/deprecations)), budget for the list price (**$0.75 input / $3.75 output per 1M tokens through Dec 31, 2026, doubling to $1.50 / $7.50 on Jan 1, 2027**), set per-run token and call budgets (`ModelCallLimitMiddleware`, `ToolCallLimitMiddleware`), retry with backoff on `429 RESOURCE_EXHAUSTED`, and keep a tested fallback model ([Fault tolerance](https://docs.langchain.com/oss/python/deepagents/fault-tolerance)).

> ⚠️ **Production note: if you choose the Groq option, its free tier is too small for serious deep-agent runs.**
> On the free plan, `openai/gpt-oss-120b` and `openai/gpt-oss-20b` are limited to **30 RPM, 1K requests/day, 8K tokens/minute, and 200K tokens/day** ([Groq rate limits](https://console.groq.com/docs/rate-limits)). A deep agent sends its system prompt, tool schemas, and growing history on every step, and spawns subagents, so one research run can use tens of thousands of tokens. If you use Groq here, keep tasks small, throttle with a rate limiter, and consider the Groq Developer plan (pay per token) for the module project. **In production:** use a paid tier with headroom, a model that passes both the official eval suite and *your* evals, per-run token and call budgets (`ModelCallLimitMiddleware`, `ToolCallLimitMiddleware`), retries with backoff, and a tested fallback model ([Fault tolerance](https://docs.langchain.com/oss/python/deepagents/fault-tolerance)).

> ⚠️ **Production note: `FilesystemBackend` and `LocalShellBackend` are for local development only.**
> The docs warn that `FilesystemBackend` gives the agent direct read/write access to real files (including secrets like `.env`), that `virtual_mode=False` gives no protection even with `root_dir`, and that `LocalShellBackend` adds unrestricted shell execution on your host with no isolation ([Backends](https://docs.langchain.com/oss/python/deepagents/backends)). The course uses them on a throwaway copy of a repo, with `virtual_mode=True`, deny rules for secrets, and HITL on writes. **In production:** never use them in web servers or multi-tenant APIs. Use `StateBackend`/`StoreBackend` for agent files, a sandbox backend for code execution, least-privilege permissions, and audit logs of file operations.

> ⚠️ **Production note: writable memory is an attack surface.**
> If an agent can write to memory that other users or future runs read, a prompt injection today becomes a standing instruction tomorrow. The docs recommend organization-level memory be **read-only** ([Memory](https://docs.langchain.com/oss/python/deepagents/memory)). The course demos writable memory on synthetic data in a local `InMemoryStore`. **In production:** scope memory per user, make shared policy memory read-only, review or consolidate writes in the background, version memory files, and use a durable store (Postgres) instead of `InMemoryStore`.

> ⚠️ **Production note: a local Docker container is not a hardened sandbox, and secrets never go inside one.**
> The docs are explicit: **never put secrets inside a sandbox**, because a context-injected agent can read and exfiltrate them; keep credentials in tools that run on the host, block network access when it isn't needed, and treat everything produced inside the sandbox as untrusted ([Sandboxes: security considerations](https://docs.langchain.com/oss/python/deepagents/sandboxes)). The course's `DockerSandbox` is a free learning tool: it starts containers with `--network none`, no host mounts and no environment variables, but containers still share the host kernel. **In production:** use a managed sandbox provider (or hardened microVMs) with egress controls, resource limits, TTLs, and snapshots; never mount your home folder or Docker socket; and log every `execute` call. Interpreters and dynamic subagents are **beta**: keep them off critical paths until they stabilize.

> ⚠️ **Production note: Deep Agents Code is not officially supported on Windows.**
> The docs say Windows users can try it under WSL ([Deep Agents Code quickstart](https://docs.langchain.com/oss/deepagents/code/quickstart)). The course only *tours* `dcode` (optional, in WSL) as an example of a production deep agent; nothing in the course depends on it. Managed Deep Agents is a public-beta hosted service and is optional.

## Use-case labs

- **Lab 11A — Repo Cartographer (codebase analysis & refactor planning)** (After Lesson 11.05). understanding an unfamiliar codebase and planning a safe refactor takes a senior engineer days. *Stack:* Free: Gemini free tier (`google_genai:gemini-3.6-flash`, default; analyze a **public** repo or your own course code only). Option: Groq (`gpt-oss-120b` orchestrator, `gpt-oss-20b` subagents). Paid: OpenAI benchmark for the orchestrator.
- **Lab 11B — Sandboxed Data Analyst** (After Lesson 11.09). turning a raw CSV into a trustworthy analysis report with charts, without running model-written code on your machine. *Stack:* Free: Gemini free tier (default, public dataset only) + Docker Desktop. Option: Groq. Paid (optional): a managed sandbox provider, OpenAI benchmark.
- **Lab 11C — Policy & Contract Review Desk (HITL compliance review)** (After Lesson 11.08). reviewing many documents against a compliance checklist is slow, and a wrong "approved" is expensive, so a human must sign off. *Stack:* Free: Gemini free tier (default; **synthetic documents only**, because free-tier prompts may be read by human reviewers). Option: Groq. Paid: OpenAI benchmark as the rubric grader, and a paid tier for any real contracts.

Lab files go in `labs/`.

## Project

**Project 11 — Deep Research Analyst**: A production-shaped deep research agent that answers a hard question by researching the web **and** your own documents, and delivers a cited report you would actually send to someone.

**Built:** a coordinator with a `researcher` subagent (the Orbita Labs documents through BM25, then the web) and a `critic`; every brief is paused for a review policy before it is saved under `/reports/`; an evaluation on the 20 golden questions (16 answerable, 4 to decline) checks format, grounding against what the tools returned, workflow, budget and correctness, with Wilson intervals and a SHIP/HOLD report. Spec: [project/README.md](project/README.md).

**Stack:** Free: runs fully offline with scripted models; LIVE on the Gemini free tier (`google_genai:gemini-3.6-flash`, default; smoke set ≈ 45–75K tokens) with optional Groq browser search or Tavily for the web. Option: Groq models (Developer plan recommended for the full 20-question run, ≈ 300–500K tokens). Paid: OpenAI benchmark (`gpt-6-luna`).

Project files go in `project/`.

## Jupyter skill

Long-running agents in notebooks: live progress panels with `display(..., display_id=True)` (todos, subagent status), rendering agent-written files and Markdown reports inline with `IPython.display.Markdown`, running a long job as an `asyncio` task so the kernel stays responsive, and saving run artifacts (final state, files, trace URL) to disk for later comparison.

## `src/mastery` increment

`mastery/deep/` with `factory.py` (`build_deep_agent()` with the course defaults: explicit model from settings, rate limiter, call budgets, fallbacks; `course_backend()` with `/memories/` per user and optional `/reports/`; secret deny rules and `deny_everything_else()`), `sandbox.py` (`DockerSandbox(BaseSandbox)`, `docker_available()`), and `evals.py` (trajectory, file-state, grounding and budget checks: `check_case()`).

## Research checkpoint

Open the [Deep Agents changelog](https://docs.langchain.com/oss/python/deepagents/changelog-py) and [releases](https://github.com/langchain-ai/deepagents/releases). Log every release since 0.7.23, any breaking change or new deprecation, whether 1.0 has shipped, and whether any feature this module calls "beta" is now stable. Re-check the suggested-models table on [Models](https://docs.langchain.com/oss/python/deepagents/models) (is `gemini-3.6-flash` still listed? has a newer Gemini Flash or a Groq-hosted model been added?) and the [Gemini deprecations](https://ai.google.dev/gemini-api/docs/deprecations) page (does `gemini-3.6-flash` have a shutdown date yet?). Update the `deepagents` line in `requirements.txt` if needed. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

✅ Ready: Lessons 11.01–11.12 and Project 11 (verified 2026-10-16 against `deepagents` 0.7.26). The three use-case labs are planned.

**Free-tier budget (LIVE cells):** 11.01 ≈ 8–15K tokens, 11.02 ≈ 3–8K tokens per compared model, 11.03 ≈ 20–30K only if you enable its planning experiment, 11.04 none (offline), 11.05 ≈ 6–12K, 11.06 ≈ 10–15K, 11.07 ≈ 6–10K, 11.08 ≈ 5–8K, 11.09 ≈ 8–12K (also needs Docker), 11.10 ≈ 6–10K, 11.11 ≈ 10–20K, 11.12 none (scripted demos), Project 11 smoke ≈ 45–75K, full set ≈ 300–500K (each only if you enable its live cell). Lesson 11.09's 🐳 cells use your local Docker (optional) and spend no tokens. Every 🧪 cell runs offline for free. `mastery.deep.build_deep_agent()` rate-limits calls, caps each run, and uses `MASTERY_FALLBACK_MODELS` (see `.env.example`) when one model's quota runs out.

---

← [Module 10](../10-testing-evaluation-observability/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 12](../12-production-and-deployment/) →
