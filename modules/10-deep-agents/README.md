# Module 10 — Deep Agents

> **Part 2 — Pro (Modules 09–14)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 10](../../COURSE_OUTLINE.md#module-10--deep-agents)

**Goals:** Master **Deep Agents**, LangChain's open-source "batteries-included" agent harness for long-running, multi-step work. By the end you can design, build, secure, evaluate, and ship deep agents that plan, use a virtual filesystem with pluggable backends, delegate to subagents (sync, forked, async, and dynamic), manage their own context over long runs, load skills and long-term memory, pause for human approval, execute code safely in sandboxes, and stream progress to a UI. You also learn when **not** to use a harness.

**Estimated time:** 3–3.5 weeks (11 lessons, 3 use-case labs, 1 module project).

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 10.01 | Harness thinking: deep agents vs `create_agent` vs LangGraph | `10-01-harness-and-first-deep-agent.ipynb` | 📝 Planned |
| 10.02 | Models, harness profiles, and token budgets | `10-02-models-profiles-and-budgets.ipynb` | 📝 Planned |
| 10.03 | The virtual filesystem and planning | `10-03-virtual-filesystem-and-planning.ipynb` | 📝 Planned |
| 10.04 | Backends, routing, and permissions | `10-04-backends-routing-permissions.ipynb` | 📝 Planned |
| 10.05 | Subagents and delegation | `10-05-subagents-and-delegation.ipynb` | 📝 Planned |
| 10.06 | Context engineering for long-running agents | `10-06-context-engineering-long-runs.ipynb` | 📝 Planned |
| 10.07 | Skills and long-term memory | `10-07-skills-and-memory.ipynb` | 📝 Planned |
| 10.08 | Human-in-the-loop, guardrails, and fault tolerance | `10-08-hitl-guardrails-fault-tolerance.ipynb` | 📝 Planned |
| 10.09 | Code execution: sandboxes, interpreters, and dynamic subagents | `10-09-sandboxes-interpreters-dynamic-subagents.ipynb` | 📝 Planned |
| 10.10 | Async subagents, streaming, and agent protocols | `10-10-async-subagents-streaming-protocols.ipynb` | 📝 Planned |
| 10.11 | Evaluating and shipping deep agents | `10-11-evaluating-and-shipping-deep-agents.ipynb` | 📝 Planned |

## Production notes

> ⚠️ **Production note: Deep Agents is pre-1.0, so pin it and expect API churn.**
> Patch releases ship every few days (0.7.21 on Sep 30, 0.7.22 on Oct 5, 0.7.23 on Oct 7, 2026), and real APIs changed within months: backend factory functions were deprecated in 0.5.0, namespace factories switched from `BackendContext` to a LangGraph `Runtime` in 0.5.2, relying on the default model (`model=None`) is deprecated since 0.5.3 and will be removed in 1.0, and v0.7 removed the planning tool from the default stack ([Backends: migrate from backend factories](https://docs.langchain.com/oss/python/deepagents/backends), [`create_deep_agent` reference](https://reference.langchain.com/python/deepagents/graph/create_deep_agent), [Deep Agents v0.7](https://www.langchain.com/blog/deep-agents-v0-7)). The course uses a floor + minor-version ceiling (`deepagents>=0.7.23,<0.8`) so lessons keep working while you learn. **In production:** pin the exact version (`deepagents==0.7.23`) in a lock file (for example `uv.lock`), upgrade deliberately on a branch, read the changelog for every bump, run your trajectory evals (Lesson 10.11) as an upgrade gate, treat `DeprecationWarning`s from `deepagents` as test failures in CI, and keep beta features behind your own small interface (`mastery/deep/`) so a breaking change touches one file.

> ⚠️ **Production note: Groq's free tier is too small for serious deep-agent runs.**
> On the free plan, `openai/gpt-oss-120b` and `openai/gpt-oss-20b` are limited to **30 RPM, 1K requests/day, 8K tokens/minute, and 200K tokens/day** ([Groq rate limits](https://console.groq.com/docs/rate-limits)). A deep agent sends its system prompt, tool schemas, and growing history on every step, and spawns subagents, so one research run can use tens of thousands of tokens. The course keeps tasks small, throttles with a rate limiter, and suggests the Groq Developer plan (pay per token) or the Gemini free tier for the module project. **In production:** use a paid tier with headroom, a model that passes both the official eval suite and *your* evals, per-run token and call budgets (`ModelCallLimitMiddleware`, `ToolCallLimitMiddleware`), retries with backoff, and a tested fallback model ([Fault tolerance](https://docs.langchain.com/oss/python/deepagents/fault-tolerance)).

> ⚠️ **Production note: `FilesystemBackend` and `LocalShellBackend` are for local development only.**
> The docs warn that `FilesystemBackend` gives the agent direct read/write access to real files (including secrets like `.env`), that `virtual_mode=False` gives no protection even with `root_dir`, and that `LocalShellBackend` adds unrestricted shell execution on your host with no isolation ([Backends](https://docs.langchain.com/oss/python/deepagents/backends)). The course uses them on a throwaway copy of a repo, with `virtual_mode=True`, deny rules for secrets, and HITL on writes. **In production:** never use them in web servers or multi-tenant APIs. Use `StateBackend`/`StoreBackend` for agent files, a sandbox backend for code execution, least-privilege permissions, and audit logs of file operations.

> ⚠️ **Production note: writable memory is an attack surface.**
> If an agent can write to memory that other users or future runs read, a prompt injection today becomes a standing instruction tomorrow. The docs recommend organization-level memory be **read-only** ([Memory](https://docs.langchain.com/oss/python/deepagents/memory)). The course demos writable memory on synthetic data in a local `InMemoryStore`. **In production:** scope memory per user, make shared policy memory read-only, review or consolidate writes in the background, version memory files, and use a durable store (Postgres) instead of `InMemoryStore`.

> ⚠️ **Production note: a local Docker container is not a hardened sandbox, and secrets never go inside one.**
> The docs are explicit: **never put secrets inside a sandbox**, because a context-injected agent can read and exfiltrate them; keep credentials in tools that run on the host, block network access when it isn't needed, and treat everything produced inside the sandbox as untrusted ([Sandboxes: security considerations](https://docs.langchain.com/oss/python/deepagents/sandboxes)). The course's `DockerSandbox` is a free learning tool: containers share the host kernel and, by default, have network access. **In production:** use a managed sandbox provider (or hardened microVMs) with egress controls, resource limits, TTLs, and snapshots; never mount your home folder or Docker socket; and log every `execute` call. Interpreters and dynamic subagents are **beta**: keep them off critical paths until they stabilize.

> ⚠️ **Production note: Deep Agents Code is not officially supported on Windows.**
> The docs say Windows users can try it under WSL ([Deep Agents Code quickstart](https://docs.langchain.com/oss/deepagents/code/quickstart)). The course only *tours* `dcode` (optional, in WSL) as an example of a production deep agent; nothing in the course depends on it. Managed Deep Agents is a public-beta hosted service and is optional.

## Use-case labs

- **Lab 10A — Repo Cartographer (codebase analysis & refactor planning)** (After Lesson 10.05). understanding an unfamiliar codebase and planning a safe refactor takes a senior engineer days.
- **Lab 10B — Sandboxed Data Analyst** (After Lesson 10.09). turning a raw CSV into a trustworthy analysis report with charts, without running model-written code on your machine.
- **Lab 10C — Policy & Contract Review Desk (HITL compliance review)** (After Lesson 10.08). reviewing many documents against a compliance checklist is slow, and a wrong "approved" is expensive, so a human must sign off.

Lab files go in `labs/`.

## Project

**Project 10 — Deep Research Analyst**: A production-shaped deep research agent that answers a hard question by researching the web **and** your own documents, and delivers a cited report you would actually send to someone.

Project files go in `project/`.

## Jupyter skill

Long-running agents in notebooks: live progress panels with `display(..., display_id=True)` (todos, subagent status), rendering agent-written files and Markdown reports inline with `IPython.display.Markdown`, running a long job as an `asyncio` task so the kernel stays responsive, and saving run artifacts (final state, files, trace URL) to disk for later comparison.

## `src/mastery` increment

`mastery/deep/` with `factory.py` (`build_deep_agent()` with the course defaults: explicit model from settings, `CompositeBackend` layout `/workspace/` · `/memories/` · `/reports/`, default deny rules for secrets, rate limiter, call limits), `sandboxes/docker.py` (`DockerSandbox(BaseSandbox)`), `skills/` (course skills), and `evals.py` (trajectory and file-state evaluators).

## Research checkpoint

Open the [Deep Agents changelog](https://docs.langchain.com/oss/python/deepagents/changelog-py) and [releases](https://github.com/langchain-ai/deepagents/releases). Log every release since 0.7.23, any breaking change or new deprecation, whether 1.0 has shipped, and whether any feature this module calls "beta" is now stable. Re-check the suggested-models table on [Models](https://docs.langchain.com/oss/python/deepagents/models) (is a Groq-hosted model listed yet?). Update the `deepagents` line in `requirements.txt` if needed. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 09](../09-multi-agent-systems/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 11](../11-multimodal-and-voice/) →
