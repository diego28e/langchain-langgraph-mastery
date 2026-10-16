# Module 00 — Foundations, Tooling & Research Skills

> **Part 1 — Core (Modules 00–08)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 00](../../COURSE_OUTLINE.md#module-00--foundations-tooling--research-skills)
> Docs verified: **2026-10-11**

**Goals:** Explain what an AI engineer does in 2026. Confirm that your machine is ready and create the course environment. Use Jupyter properly. Keep secrets safe. Make your first Groq call through LangChain. Learn to find, read, and verify official docs. Choose providers with evidence.

**Estimated time:** 1–1.5 weeks (about 8–11 hours of lessons plus 2.5–3.5 hours for the project).

## Before you start this module

Nothing to install yet: this module **is** the setup. You need:

| | |
|---|---|
| 💻 Machine | Windows 10/11 with **Git Bash** ([git-scm.com](https://git-scm.com/)), or macOS/Linux; **Anaconda** or Miniconda; ~5 GB free disk |
| 🔑 Keys | None until Lesson 00.04, where you create a free `GROQ_API_KEY` |
| 💰 Cost | $0 (Groq free tier, no card needed) |
| ✅ Ready when | Lesson 00.02 notebook prints all ✅ and the [setup guide](00-02-create-course-env.md) ends with `python -m pytest` passing |

Already finished Module 00 and pulled updates? Run `git pull` then `python -m pip install -e ".[dev]"` in Git Bash at the repo root with `lc-mastery` active.

## How to work through this module

1. **Use Git Bash on Windows** (macOS/Linux: your normal terminal). Every command in this module is written for bash. The Anaconda Prompt is only a fallback. See [CONVENTIONS.md §10](../../CONVENTIONS.md#10-shells-git-bash-first) for path and quoting rules.
2. **Go in order.** Lessons build on each other: 00.02 creates the environment that 00.03–00.07 run in, 00.04 creates the `.env` file that 00.05 and the project need.
3. **Start Jupyter from the repo root** so every notebook can find `.env`, `data/`, and `src/`:
   ```bash
   cd ~/path/to/langchain-langgraph-mastery   # quote the path if it has spaces
   conda activate lc-mastery                  # after Lesson 00.02's guide
   jupyter notebook                           # or: jupyter lab
   ```
4. **In each notebook:** check the kernel name in the top-right corner (00.01–00.02 use the default **Python 3 (ipykernel)**; from 00.03 on, **Python (lc-mastery)**), then run cells top to bottom with **Shift + Enter**. Read each "What just happened?" cell before moving on.
5. **Tick the ✅ Checkpoint** at the end of each lesson. If something fails, every lesson has a **Pitfalls** table, and the [setup guide](00-02-create-course-env.md#troubleshooting) has a troubleshooting index.
6. **Before you commit:** *Kernel → Restart Kernel and Run All Cells…*, then *Edit → Clear Outputs of All Cells*, save, and run `python -m pytest` from the repo root.
7. **No API key yet?** Only Lesson 00.05 and the project use one, and even there API cells print `⏭️ Skipped` instead of crashing, so you can read along and come back after creating your key (Lesson 00.04). Every other lesson needs no key.

## Lessons

| Lesson | Title | Files | Time | Key needed? |
|---|---|---|---|---|
| 00.01 | What an AI engineer actually does in 2026 | [`00-01-the-ai-engineer-role.ipynb`](00-01-the-ai-engineer-role.ipynb) | 45–60 min | No |
| 00.02 | Verify your environment (no installs yet) | [`00-02-verify-environment.ipynb`](00-02-verify-environment.ipynb) + guide [`00-02-create-course-env.md`](00-02-create-course-env.md) + [setup/VERIFY_ENVIRONMENT.md](../../setup/VERIFY_ENVIRONMENT.md) | 45–75 min + 45–90 min guide (Windows; 20–30 min on macOS/Linux) | No |
| 00.03 | Jupyter fundamentals | [`00-03-jupyter-fundamentals.ipynb`](00-03-jupyter-fundamentals.ipynb) | 60–90 min | No |
| 00.04 | Secrets and `.env` hygiene | [`00-04-secrets-and-env.ipynb`](00-04-secrets-and-env.ipynb) | 60–75 min | Creates it |
| 00.05 | First contact: Groq + LangChain | [`00-05-first-groq-call.ipynb`](00-05-first-groq-call.ipynb) | 75–90 min | `GROQ_API_KEY` |
| 00.06 | Researching like a pro: docs, llms.txt, changelogs, model cards | [`00-06-research-skills.ipynb`](00-06-research-skills.ipynb) | 75–90 min | No (internet) |
| 00.07 | Free vs paid vs local: a decision framework | [`00-07-provider-decision-framework.ipynb`](00-07-provider-decision-framework.ipynb) | 60–75 min | No |

**What each lesson gives you**

- **00.01:** the Build → Test → Deploy → Monitor lifecycle, and where LangChain, LangGraph, Deep Agents, and LangSmith fit. Your first notebook cells and Markdown.
- **00.02:** which Python your terminal and your kernel really use (`sys.executable`), base vs project env. The guide makes `conda` work in Git Bash, creates the `lc-mastery` env (Python 3.13), installs the course package `mastery` in editable mode, and registers the **Python (lc-mastery)** kernel.
- **00.03:** command vs edit mode, shortcuts, kernel state and out-of-order bugs, Restart & Run All, magics (`%time`, `%timeit`, `%who`, `%env`, `!`, `%pip`), rich display, what's inside an `.ipynb`, clearing outputs, `nbstripout`.
- **00.04:** a Groq API key, `.env` vs `.env.example`, `git check-ignore`, python-dotenv, `mastery.config` (load, validate, mask), what to do if a key leaks.
- **00.05:** `%pip` installs, the Groq Models API, `ChatGroq` and `init_chat_model("groq:...")`, the parts of an `AIMessage`, token cost, streaming, and handling 401/4xx/429 errors.
- **00.06:** a ranked list of sources, LangChain's `llms.txt` and `.md` pages, catching retired model IDs in official examples, PyPI versions, changelogs, deprecation pages, and model cards.
- **00.07:** cost per run from token prices, what a free tier really allows (TPM usually binds first), data-use terms, production vs preview, your first decision-log entry.

## Project

**[Project 00 — Groq Model Explorer](project/README.md)**: a notebook that tells you, today, which Groq chat models are live and how they compare on the same three prompts (factual, reasoning, creative), saved to `data/outputs/00-model-explorer.csv`.

| File | Use |
|---|---|
| [`project/README.md`](project/README.md) | Spec, acceptance criteria, TODO list, rubric |
| [`project/00-project-groq-model-explorer.ipynb`](project/00-project-groq-model-explorer.ipynb) | **Starter** with five `# TODO`s (runs from day one) |
| [`project/solutions/00-project-groq-model-explorer-solution.ipynb`](project/solutions/00-project-groq-model-explorer-solution.ipynb) | **Reference solution** (open after trying) |

## Jupyter skills in this module

Launching Jupyter from the repo root, kernels and kernel switching, command/edit mode and shortcuts, Markdown cells, Restart & Run All as the "does it really work?" test, magics, `%pip` vs `!pip`, rich display, notebook JSON, and clearing outputs before every commit.

## `src/mastery` increment

| File | What it does | Tests |
|---|---|---|
| [`src/mastery/config.py`](../../src/mastery/config.py) | Load `.env`, check keys without revealing them, friendly `MissingSettingError`, course settings (model IDs from `.env`) | [`tests/unit/test_config.py`](../../tests/unit/test_config.py) |
| [`src/mastery/groq_catalog.py`](../../src/mastery/groq_catalog.py) | List live Groq models via `GET /openai/v1/models`, friendly HTTP errors | [`tests/unit/test_groq_catalog.py`](../../tests/unit/test_groq_catalog.py) (offline, `httpx.MockTransport`) · [`tests/integration/test_groq_live.py`](../../tests/integration/test_groq_live.py) (live) |
| [`pyproject.toml`](../../pyproject.toml) | Makes `mastery` installable (`python -m pip install -e ".[dev]"`) and configures pytest | [`tests/unit/test_notebook_hygiene.py`](../../tests/unit/test_notebook_hygiene.py) checks every notebook |

## Research checkpoint

Open [Groq deprecations](https://console.groq.com/docs/deprecations) and the [LangChain changelog](https://docs.langchain.com/oss/python/releases/changelog). Log one model that was deprecated in the last 90 days and one new LangChain feature in [`docs/research-log.md`](../../docs/research-log.md).

## Status

✅ **Built** (2026-10-11). All notebooks pass Restart & Run All without an API key (API cells skip with a message). Live Groq calls are verified by the learner (see the 00.05 checkpoint).

---

[Course outline](../../COURSE_OUTLINE.md) · [Module 01](../01-models-messages-prompts/) →
