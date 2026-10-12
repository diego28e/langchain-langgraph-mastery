# Module 01 — Models, Messages & Prompts

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 01](../../COURSE_OUTLINE.md#module-01--models-messages--prompts)
> Docs verified: **2026-10-11**

**Goals:** Master the model layer that everything else stands on: chat model interfaces, messages and content blocks, multimodal input, structured output, streaming and batching, token and cost awareness. Understand Runnables and LCEL well enough to read older code and the internals. See your first traces.

**Estimated time:** 1.5–2 weeks (about 13–16 hours of lessons plus 4–6 hours for the project).

## How to work through this module

1. **Update the course package once** (Git Bash, repo root, `lc-mastery` active). Module 01 adds `mastery.models`, `mastery.pricing` and `mastery.display`, and the `llm` extra pulls in the LangChain packages the tests need:
   ```bash
   cd ~/path/to/langchain-langgraph-mastery
   conda activate lc-mastery
   git pull
   python -m pip install -e ".[dev]"
   python -m pytest -q          # expect: all passed (offline, no keys needed)
   ```
2. **Start Jupyter from the repo root** (`jupyter lab` or `jupyter notebook`) and pick the **Python (lc-mastery)** kernel in every notebook.
3. **Go in order.** 01.01 introduces `get_model(role)`, used everywhere after; 01.04 (structured output), 01.05 (batching), 01.06 (rate limits) and 01.08 (tracing) all come together in the project.
4. **Read the cell markers.** 🧪 = offline (fake model, free) · 🌐 = network, no tokens · 💸 = calls a model (free-tier quota). Most concepts are taught first with a 🧪 fake model, then shown live.
5. **No key? Still works.** Every 💸 cell checks a `HAVE_*_KEY` flag and prints `⏭️ Skipped`, so **Restart & Run All** always completes. The project has a full OFFLINE DEMO mode.
6. **Before you commit:** *Kernel → Restart Kernel and Run All Cells…*, *Edit → Clear Outputs of All Cells*, save, then `python -m pytest -q`.

## Lessons

| Lesson | Title | Notebook | Time | Keys |
|---|---|---|---|---|
| 01.01 | Chat models and `init_chat_model` | [`01-01-chat-models.ipynb`](01-01-chat-models.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 01.02 | Messages and standard content blocks | [`01-02-messages-and-content-blocks.ipynb`](01-02-messages-and-content-blocks.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 01.03 | Prompting fundamentals for open-weight models | [`01-03-prompting-fundamentals.ipynb`](01-03-prompting-fundamentals.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 01.04 | Structured output you can trust | [`01-04-structured-output.ipynb`](01-04-structured-output.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 01.05 | Streaming, batching, and async basics | [`01-05-streaming-and-batching.ipynb`](01-05-streaming-and-batching.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 01.06 | Tokens, cost, and rate limits | [`01-06-tokens-cost-rate-limits.ipynb`](01-06-tokens-cost-rate-limits.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 01.07 | Under the hood: Runnables and LCEL (legacy-aware) | [`01-07-runnables-and-lcel.ipynb`](01-07-runnables-and-lcel.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 01.08 | First look at LangSmith tracing | [`01-08-first-traces.ipynb`](01-08-first-traces.ipynb) | 60–90 min | `LANGSMITH_API_KEY` + `GROQ_API_KEY` (optional) |

**What each lesson gives you**

- **01.01:** one interface for every provider (`BaseChatModel`, a `Runnable`); `ChatGroq` vs `init_chat_model("groq:...")` vs the course's `get_model(role)`; temperature, `max_tokens`, timeouts, retries, and **finding real defaults in code** (`ChatGroq`: temperature 0.7, `max_retries=2`, no timeout); model profiles; `invoke`/`stream`/`batch` and `RunnableConfig`; magics `%pip`, `%env`, `%%time`.
- **01.02:** the four message types and their dict/tuple forms; the anatomy of an `AIMessage`; `content` (provider-shaped) vs `content_blocks` (standard); reasoning and tool-call blocks; an image content block sent to the vision model; JSON serialization; rich display with `mastery.display.show_message`. Module research checkpoint (which providers support `content_blocks` natively).
- **01.03:** Groq's five prompt building blocks, role channels and instruction priority, delimiters for untrusted input (and why they are not a security boundary), few-shot as message pairs, `ChatPromptTemplate` (`partial`, `MessagesPlaceholder`, escaping braces), and an honest prompt A/B experiment on 12 support tickets.
- **01.04:** Pydantic, `TypedDict` and JSON Schema outputs; `with_structured_output` methods (`function_calling`, `json_schema` strict/best-effort, `json_mode`); integration defaults read from code (they disagree with the docs); `include_raw=True` and a retry that feeds the error back; strict-mode schema design.
- **01.05:** `AIMessageChunk` aggregation and `chunk_position`; reasoning vs answer while streaming; time-to-first-token; a live-updating Markdown renderer (display handles); `batch` with `max_concurrency`, `return_exceptions`, `batch_as_completed`; first async code (top-level `await`, `gather` + `Semaphore`, `abatch`, `astream_events`).
- **01.06:** what tokens you pay for (reasoning = output); `usage_metadata`; `get_usage_metadata_callback` + `mastery.pricing.cost_report`; Groq rate-limit types and `x-ratelimit-*` headers; `InMemoryRateLimiter` and its limits; what the Groq SDK does on a 429 (read from its source); `with_retry` and backoff that honors `retry-after`; budgeting a workload.
- **01.07:** the `Runnable` protocol; LCEL pipelines and their ASCII graph; `RunnableLambda`, `RunnableParallel`, `RunnablePassthrough.assign`; `with_fallbacks` with narrow exceptions; a sentence-streaming `RunnableGenerator` (voice-agent pattern); reading legacy code (`LLMChain`, `AgentExecutor`, ... → `langchain-classic` and v1 equivalents); when **not** to use LCEL.
- **01.08:** runs, traces, projects, threads; the run tree captured **locally** with `collect_runs` (no account); run names, tags, metadata, run IDs; selective tracing with `tracing_context`; `wait_for_all_tracers`; `@traceable`; navigating the LangSmith UI; privacy, masking, retention and quota.

## Project

**[Project 01 — Multi-Model Comparison Lab](project/README.md)**: one notebook that extracts a `JobPosting` from 10 postings with 3+ model configurations and reports schema-valid rate, field-level accuracy, latency, tokens and estimated cost, with a live streamed example, rate-limited batches, LangSmith traces (`m01-comparison-lab`) and an error analysis.

| File | Use |
|---|---|
| [`project/README.md`](project/README.md) | Spec, acceptance criteria, TODO list, budget, rubric |
| [`project/01-project-multi-model-comparison-lab.ipynb`](project/01-project-multi-model-comparison-lab.ipynb) | **Starter** with five `# TODO`s (runs from day one, also offline) |
| [`project/solutions/01-project-multi-model-comparison-lab-solution.ipynb`](project/solutions/01-project-multi-model-comparison-lab-solution.ipynb) | **Reference solution** (open after trying) |

Data: [`data/samples/job-postings/`](../../data/samples/job-postings/) (10 synthetic postings + `answer-key.json`). Lessons also use [`data/samples/support-tickets.jsonl`](../../data/samples/support-tickets.jsonl) (01.03) and [`data/samples/images/quarterly-signups.png`](../../data/samples/images/quarterly-signups.png) (01.02).

## Jupyter skills in this module

Magics and rich display, each taught where it is first useful:

| Skill | Where |
|---|---|
| `%pip install` into the running kernel (and when to restart) | Step 0 of every notebook; explained in 01.01 |
| `%env` for non-secret config (never for keys) | 01.01 |
| `%%time` (line 1 only; **cannot** time top-level `await`) | 01.01, 01.05 |
| Rich display: HTML message cards (`mastery.display.show_message`), DataFrames, Markdown | 01.02, 01.06, project |
| Live-updating output with `display(..., display_id=True)` + `handle.update()` | 01.05 |
| Top-level `await` (Jupyter's running event loop) vs `asyncio.run` in scripts | 01.05 |

## `src/mastery` increment

| File | What it does | Tests |
|---|---|---|
| [`src/mastery/models.py`](../../src/mastery/models.py) | `get_model(role, provider)` from `.env` (no hard-coded IDs), friendly missing-key/missing-package errors, `PreviewModelWarning`, `explain_model_error()` for any provider (SDK or `langchain_core` exceptions; 401/404/429/498/5xx, `retry-after`), `describe_model()` | [`tests/unit/test_models.py`](../../tests/unit/test_models.py) |
| [`src/mastery/pricing.py`](../../src/mastery/pricing.py) | Dated price table (`PRICES`), `estimate_cost(usage, model)`, `cost_report()` for `get_usage_metadata_callback` | [`tests/unit/test_pricing.py`](../../tests/unit/test_pricing.py) |
| [`src/mastery/display.py`](../../src/mastery/display.py) | `message_summary()`, `render_message_html()` (escaped, testable), `show_message()` for Jupyter | [`tests/unit/test_display.py`](../../tests/unit/test_display.py) |
| [`src/mastery/config.py`](../../src/mastery/config.py) | Extended: `model_vision`, `benchmark_model`, `benchmark_model_strong` settings | [`tests/unit/test_config.py`](../../tests/unit/test_config.py) |
| [`tests/unit/test_notebook_structure.py`](../../tests/unit/test_notebook_structure.py) | Every Module 01+ lesson has the template sections; every live model call is guarded by a key flag | – |

## Research checkpoint

Module question (Lesson 01.02): which providers currently support standard `content_blocks` natively, and is `langchain-groq` one of them? Every lesson also ends with its own short research task. Log findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

✅ **Built** (2026-10-11). Every notebook passes Restart & Run All without keys (💸 cells skip) and against a local Groq/LangSmith stand-in (maintainer QA). Live calls are verified by the learner at each checkpoint.

---

← [Module 00](../00-foundations/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 02](../02-tools-and-agents/) →
