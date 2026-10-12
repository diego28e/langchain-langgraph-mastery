# Module 03 — Memory & Context Engineering

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 03](../../COURSE_OUTLINE.md#module-03--memory--context-engineering)

**Goals:** Give agents short-term memory (threads and checkpointers), manage long conversations (trim, delete, summarize), add long-term memory (stores), and treat context as something you engineer on purpose.

**Estimated time:** 1.5 weeks (about 11–14 hours of lessons plus 4–6 hours for the project).

## How to work through this module

1. **Update the course package once** (Git Bash, repo root, `lc-mastery` active). Module 03 adds `mastery.memory`. The `[dev]` extra now also installs `langgraph-checkpoint-sqlite` (SQLite checkpointer and store, with the `sqlite-vec` extension for vector search).
   ```bash
   cd ~/path/to/langchain-langgraph-mastery
   conda activate lc-mastery
   git pull
   python -m pip install -e ".[dev]"
   python -m pytest -q          # expect: all passed (offline, no keys needed)
   python -c 'import langgraph.checkpoint.sqlite, sqlite_vec; print("sqlite ok")'   # expect: sqlite ok
   ```
2. **Optional, for real semantic search** (Lesson 03.04 Part 4, Project 03 stretch): a local embedding model, no key, no PyTorch (≈150 MB of wheels; the model, ≈70 MB, downloads on first use into `~/.cache/fastembed`):
   ```bash
   python -m pip install -e ".[embeddings]"
   ```
   Skip it and those cells print `⏭️ Skipped`.
3. **Start Jupyter from the repo root** and pick the **Python (lc-mastery)** kernel. Lesson 03.01 adds `%autoreload`, so you can edit `src/mastery/` while notebooks run.
4. **Go in order.** 03.01 is the map; 03.02 short-term memory; 03.03 keeps it short; 03.04 long-term memory; 03.05 ties it together as context engineering. The project uses all five.
5. **Read the cell markers.** 🧪 = offline (scripted model, free) · 🌐 = network, no tokens · 💸 = calls a model (free-tier quota). No key? Every 💸 cell prints `⏭️ Skipped`, so **Restart & Run All** always completes.
6. **Memory files are personal data.** SQLite files go to `data/outputs/memory/` (git-ignored). Close them (or the kernel) before deleting them on Windows.
7. **Before you commit:** *Kernel → Restart Kernel and Run All Cells…*, *Edit → Clear Outputs of All Cells*, save, then `python -m pytest -q`.

## Lessons

| Lesson | Title | Notebook | Time | Keys |
|---|---|---|---|---|
| 03.01 | Memory concepts: short-term vs long-term | [`03-01-memory-concepts.ipynb`](03-01-memory-concepts.ipynb) | 90–120 min | `GROQ_API_KEY` (optional) |
| 03.02 | Short-term memory with checkpointers and threads | [`03-02-short-term-memory.ipynb`](03-02-short-term-memory.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 03.03 | Long conversations: trim, delete, summarize | [`03-03-managing-long-conversations.ipynb`](03-03-managing-long-conversations.ipynb) | 120–150 min | `GROQ_API_KEY` (optional) |
| 03.04 | Long-term memory with stores | [`03-04-long-term-memory.ipynb`](03-04-long-term-memory.ipynb) | 150–180 min | `GROQ_API_KEY` (optional); `fastembed` (optional) |
| 03.05 | Context engineering | [`03-05-context-engineering.ipynb`](03-05-context-engineering.ipynb) | 150–180 min | `GROQ_API_KEY` (optional) |

**What each lesson gives you**

- **03.01:** the **`%autoreload` skill** (below); models are stateless; thread-scoped (checkpointer, `thread_id`) vs cross-thread (store, namespaces) memory; semantic / episodic / procedural memory, profile vs collection, hot path vs background writes; why `ConversationBufferMemory` & co. are deprecated in `langchain-classic`, with a replacement table.
- **03.02:** `checkpointer=` + `thread_config(...)`; `get_state` / `get_state_history` and why one call makes three checkpoints; `SqliteSaver` via `make_checkpointer("sqlite", ...)`, proven across processes; custom state per thread, `update_state` + `RemoveMessage`, `delete_thread`; durability modes; SQLite on Windows (`WinError 32`, `-wal`/`-shm` files, OneDrive).
- **03.03:** tokens per turn measured on a 12-turn chat; `trim_messages` (`start_on`, `include_system`); **transient** trimming (`@wrap_model_call` + `request.override`) vs **permanent** (`@before_model` + `REMOVE_ALL_MESSAGES`); safe deletion that never splits a tool-call pair; `SummarizationMiddleware` (`trigger`, `keep`, profiles and `fraction`); one table comparing tokens sent and what is still remembered.
- **03.04:** the store API (`put`/`get`/`search`/`delete`/`list_namespaces`, `filter`); namespace design and the **prefix-search trap**; `remember_fact` / `recall_facts` tools with the user id from `runtime.context`; semantic search with an `index` (offline `HashingEmbeddings`, then a real local model); `SqliteStore` with sqlite-vec and TTLs.
- **03.05:** why agents fail (capability vs context); a **context probe** middleware; model context from the store (`@dynamic_prompt`), tools / messages / model / response format per call (`override`, and why a format must be declared at creation); life-cycle context (`@after_agent` writing episodic memories); a six-step diagnosis checklist on three broken tutors.

## Project

**[Project 03 — Study Buddy with Memory](project/README.md)**: a tutoring agent with a SQLite checkpointer, a SQLite store under `("learners", user_id)` written by `remember_fact`, the learner's memory injected into the system prompt, `SummarizationMiddleware` under a token budget, and a cross-user leakage test. A scripted 3-session demo checks that session 3 (a new thread, after a restart) uses facts from session 1.

| File | Use |
|---|---|
| [`project/README.md`](project/README.md) | Spec, acceptance criteria, modes, stretch goals |
| [`project/03-project-study-buddy.ipynb`](project/03-project-study-buddy.ipynb) | **Starter** with four `# TODO`s (runs from day one, also offline) |
| [`project/solutions/03-project-study-buddy-solution.ipynb`](project/solutions/03-project-study-buddy-solution.ipynb) | **Reference solution** (open after trying) |

## Jupyter skill in this module

**`%autoreload` for developing `src/mastery` live** (Lesson 03.01, Part 1):

| Skill | Where |
|---|---|
| `%load_ext autoreload` + `%autoreload 2` at the top of notebooks where you edit `src/mastery` | 03.01, then 03.02 |
| Modes `0/off`, `1/explicit` + `%aimport`, `2/all`, `3/complete`, `-p` to print reloads | 03.01 |
| Why import, edit and call must be separate cells; objects built before an edit keep old data | 03.01 |
| Caveats from the IPython docs; when to just restart the kernel | 03.01 |
| `subprocess.run([sys.executable, ...])` to check files from a fresh process (a "restart" inside Run All) | 03.02, Project 03 |

## `src/mastery` increment

| File | What it does | Tests |
|---|---|---|
| [`src/mastery/memory.py`](../../src/mastery/memory.py) | `make_checkpointer("memory" \| "sqlite", path)`, `make_store(kind, path, embed=, dims=, fields=, ttl=)`, `close()`, `memory_dir()` (git-ignored `data/outputs/memory/`), `thread_config()`, `learner_namespace()` / `safe_label()`, `count_tokens()`, offline `HashingEmbeddings`, optional `local_embeddings()` (fastembed) | [`tests/unit/test_memory.py`](../../tests/unit/test_memory.py) |

## Research checkpoint

Compare the memory rows of the [feature comparison table](https://docs.langchain.com/oss/python/concepts/products#feature-comparison) for LangChain, LangGraph and Deep Agents. Log which you would pick for a 3-month-long user relationship, and why, in [`docs/research-log.md`](../../docs/research-log.md) (Lesson 03.01; revisit after 03.04). Every lesson also ends with its own short research task.

## Status

✅ **Built** (2026-10-12). Every notebook passes Restart & Run All without keys (💸 cells skip) and against a local Groq stand-in (maintainer QA). SQLite persistence was checked across processes; local embeddings were run with fastembed 0.9.0 (`BAAI/bge-small-en-v1.5`).

---

← [Module 02](../02-tools-and-agents/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 04](../04-middleware-guardrails-hitl/) →
