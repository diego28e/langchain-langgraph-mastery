# Conventions

> How this repository, its notebooks, its code, and its commits are organized. Following these from Module 00 keeps the course clean enough to publish.

---

## 1. Repository structure

```text
langchain-langgraph-mastery/
├── README.md, README.es.md   # Course overview (English / Spanish)
├── COURSE_OUTLINE.md, RESOURCES.md, CONVENTIONS.md
├── requirements.txt          # Minimum versions, verified on PyPI (see RESOURCES §20)
├── .env.example              # Template. Copy to .env (never commit .env)
├── .gitignore
├── setup/
│   ├── VERIFY_ENVIRONMENT.md # Verification-only commands (now)
│   ├── PYTHON_ENVIRONMENTS_COMPARED.md # pip, venv, conda, uv, Poetry… in plain English
│   └── FULL_SETUP_APPENDIX.md# Full install guide (written at the end of the course)
├── docs/
│   ├── research-log.md       # Research checkpoints (one entry per module)
│   ├── decision-log.md       # Model & provider decisions
│   ├── production-notes.md   # Index of course shortcuts and their production best practice
│   ├── paid-benchmark-openai-vs-gemini.md
│   ├── web-search-groq-vs-tavily.md
│   ├── glossary.md           # (later)
│   └── cheatsheets/          # (later)
├── modules/
│   └── NN-slug/
│       ├── README.md         # Lesson list, project summary, status
│       ├── NN-LL-lesson-slug.ipynb
│       ├── project/          # The module project (notebook + any app code)
│       ├── labs/             # Use-case labs, when a module has them (Module 10: labs/10a-repo-cartographer/ …)
│       └── assets/           # Small images/diagrams used by the notebooks
├── apps/                     # Deployable apps (langgraph.json / FastAPI) from Modules 07+
├── capstones/
│   └── cN-slug/
├── src/
│   └── mastery/              # Reusable package grown across modules
├── tests/
│   ├── unit/                 # No network, no API keys, fast
│   └── integration/          # Real APIs. Marked, skipped by default
└── data/
    ├── samples/              # Small, committed sample data (< 1 MB per file)
    ├── raw/                  # Gitignored: downloaded corpora
    ├── outputs/              # Gitignored: generated CSVs, audio, images
    └── vectorstores/         # Gitignored: Chroma and other persisted indexes
```

**Rules**
- Folder and file names: lowercase, kebab-case for folders/notebooks, snake_case for Python modules.
- No file over 5 MB is committed. Large data is downloaded by a notebook cell into `data/raw/`.
- `apps/` and `.github/workflows/` appear only when a module introduces them.
- Folders starting with `_` are private working notes. They are gitignored and never part of the course.

## 2. Notebook naming

`modules/<NN>-<module-slug>/<NN>-<LL>-<lesson-slug>.ipynb`

| Part | Meaning | Example |
|---|---|---|
| `NN` | Two-digit module number | `03` |
| `LL` | Two-digit lesson number inside the module | `02` |
| `lesson-slug` | 2–5 lowercase words, kebab-case | `short-term-memory` |

Example: `modules/03-memory-and-context/03-02-short-term-memory.ipynb`.
Project notebooks: `modules/03-memory-and-context/project/03-project-study-buddy.ipynb`.
Lab notebooks: `modules/10-deep-agents/labs/10a-repo-cartographer/10a-lab-repo-cartographer.ipynb`.
Exercise solutions (if separated): `.../solutions/03-02-short-term-memory-solutions.ipynb`.

## 3. Lesson notebook structure (template)

Every lesson notebook follows the same order, so learners (and video viewers) always know where they are.

| # | Cell(s) | Content |
|---|---|---|
| 1 | **Title** (Markdown) | `# 03.02 · Short-term memory with checkpointers`, plus module, est. time, prerequisites, "Docs verified: YYYY-MM-DD" |
| 2 | **Learning objectives** | 3–5 bullets starting with a verb |
| 3 | **Official reading** | Links from COURSE_OUTLINE.md for this lesson |
| 4 | **Setup** (code) | Imports → `load_dotenv()` → key check (never print keys) → print versions of key packages → model IDs pulled from `mastery.models` |
| 5 | **Concept sections** | Repeat: Markdown explanation → small code cell(s) → **"What just happened?"** Markdown recap |
| 6 | **Pitfalls** | Common errors and how to read them |
| 7 | **Exercises** | 2–4 exercises, from easy to stretch. Solutions in a collapsed cell or in `solutions/` |
| 8 | **Research checkpoint** | The prompt from the outline + a link to `docs/research-log.md` |
| 9 | **Summary & next** | 3–5 bullet takeaways and a link to the next lesson |

**Notebook rules**
- **Restart & Run All must pass** before every commit (with only the keys listed in the setup cell).
- One idea per code cell. Keep cells under ~25 lines. Move longer code to `src/mastery`.
- No hidden state: don't rely on cells executed out of order or deleted cells.
- Every cell that costs money or calls a network API starts with a comment: `# 💸 Calls Groq (openai/gpt-oss-20b), ~1k tokens`.
- Long-running cells print progress. Expensive results are cached to `data/outputs/`.
- Notebooks set `LANGSMITH_PROJECT` to `mNN-<slug>` in the setup cell when tracing is on.
- Every shortcut gets a **⚠️ Production note** callout right where it is used (see §9).

## 4. Code and commenting standard

The code is teaching material, so comments explain **why**, not just what.

```python
"""Short-term memory helpers for course notebooks.

Provides a single factory so every notebook uses the same checkpointer
configuration. Introduced in Module 03, Lesson 03.02.
"""

from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

# Where persistent checkpoints live. Gitignored (see .gitignore → data/).
CHECKPOINT_DIR = Path("data/outputs/checkpoints")


def get_checkpointer(kind: str = "memory"):
    """Return a checkpointer for agents and graphs.

    Args:
        kind: "memory" for tests and quick demos (lost on kernel restart),
            "sqlite" for notebooks that must survive restarts.

    Returns:
        A LangGraph checkpointer instance.

    Raises:
        ValueError: If ``kind`` is not supported.
    """
    # Step 1: The in-memory saver is the default because it has no setup cost.
    if kind == "memory":
        return InMemorySaver()
    ...
```

**Rules**
1. **Module docstring** at the top of every `.py` file: purpose + which lesson introduced it.
2. **Google-style docstrings** (`Args`, `Returns`, `Raises`) for every public function/class.
3. **Type hints everywhere.** Pydantic models for structured data.
4. **Step comments** (`# Step 1: ...`) in notebook code cells that do more than one thing.
5. **Verification tags** for facts that can go stale:
   `# VERIFIED 2026-10-11: openai/gpt-oss-20b is a Groq production model (console.groq.com/docs/models)`
6. **No hard-coded model IDs in notebooks.** Use `mastery.models.get_model(role=...)`, configured in one place.
7. **No secrets in code or outputs.** Read from env. Never `print(os.environ[...])`.
8. Constants in `UPPER_SNAKE_CASE` at the top. No magic numbers.
9. Formatting and linting: `ruff format` + `ruff check` (introduced in Module 12).
10. Every function moved into `src/mastery` gets at least one unit test in `tests/unit/`.

## 5. Environment variables and `.env`

- `.env.example` is committed and documents every variable (no real values).
- `.env` is **never** committed (it's in `.gitignore`). Copy it with `copy .env.example .env` (Windows) and fill in only what the current module needs.
- Load it at the top of each notebook:

```python
from dotenv import load_dotenv

load_dotenv()  # Reads .env from the repo root (or the nearest parent directory)
```

- Check for keys without revealing them:

```python
import os

missing = [k for k in ("GROQ_API_KEY",) if not os.getenv(k)]
assert not missing, f"Missing env vars: {missing}. See .env.example."
```

- Fallback for one-off sessions: `getpass.getpass()` (input is never echoed).
- If a key ever reaches a commit, **rotate it immediately** in the provider console. Deleting the commit is not enough.

## 6. Clearing outputs and keeping notebooks diff-friendly

- **Before every commit:** in Jupyter, *Kernel → Restart Kernel and Run All Cells* (does it work?), then *Edit → Clear All Outputs* (Notebook 7 / JupyterLab), then save.
- **Recommended automation** (Lesson 00.03 bonus, formalized in Module 12): install `nbstripout` in the course env and run `nbstripout --install` in the repo. It strips outputs automatically when you `git add`, and `nbstripout --status` shows whether it's active.
- Exception: notebooks meant to be read on GitHub *with* outputs (e.g., a final project report) are exported to `docs/reports/*.html` or `*.md` instead of committing outputs.
- Optional (Module 09): pair notebooks with `.py` files via Jupytext for readable diffs.

## 7. Git workflow and commit messages

Commit small and often. Review `git status` and `git diff --staged` before every commit, and run all git commands yourself so you always know what goes into history.

### Conventional Commits

Format: `<type>(<scope>): <summary>` ([spec](https://www.conventionalcommits.org/en/v1.0.0/))

| Type | Use for |
|---|---|
| `feat` | New lesson notebook, project, or `src/mastery` feature |
| `fix` | Fixing broken code, wrong facts, or broken links |
| `docs` | README/outline/resources/conventions changes |
| `refactor` | Moving notebook code into `src/mastery` without behavior change |
| `test` | Adding or changing tests |
| `chore` | Repo housekeeping (`.gitignore`, folder skeleton, version bumps) |
| `ci` | GitHub Actions and pre-commit config |
| `style` | Formatting only |

**Scopes:** `m00` … `m13` for modules, `cap1` … `cap5` for capstones, `src`, `setup`, `repo`.

**Examples**

```text
docs(repo): add course outline, resources and conventions
feat(m00): add lesson 00.02 environment verification notebook
fix(m01): replace deprecated Groq model id in comparison lab
refactor(src): extract model factory into mastery.models
test(src): add unit tests for citation formatter
ci(repo): add GitHub Actions workflow for unit tests
```

**Rules**
- Summary in the imperative mood, lowercase, ≤ 72 characters, no trailing period.
- Body (optional) explains *why*, and lists verified doc links when a fact changed.
- One logical change per commit (e.g., one lesson notebook = one commit).
- `BREAKING CHANGE:` footer when the `mastery` API changes in a way that breaks earlier notebooks.

### Branching (simple)
- `main` stays runnable. Work on `module/NN-slug` branches if you like, and merge when the module passes its definition of done (§8).

## 8. Definition of done (per lesson)

- [ ] Follows the notebook template (§3)
- [ ] Restart & Run All passes. Outputs cleared before commit
- [ ] All links in the notebook open, and the "Docs verified" date is updated
- [ ] Model IDs come from `mastery.models`. Any new model ID has a `VERIFIED` tag
- [ ] Reusable code extracted to `src/mastery` with a unit test
- [ ] Research checkpoint logged
- [ ] Every shortcut has a ⚠️ Production note, and new ones are added to `docs/production-notes.md`
- [ ] Module README status updated

## 9. Production notes: every shortcut has one

A course takes shortcuts so you can learn fast: free tiers, **preview models**, in-memory stores, `.env` files, single-container deployments. Shortcuts are fine **only if they are labelled**. The rule:

> Every course shortcut must carry a **⚠️ Production note** that says (1) why it is a shortcut, (2) what to use in production instead, and (3) which lesson teaches the production version, if any.

**Format** (in notebooks and Markdown files):

```markdown
> ⚠️ **Production note: <short title>.**
> <Why this is a shortcut.> In production: <the best practice, concretely>. See <lesson or doc link>.
```

**Example**

> ⚠️ **Production note: `qwen/qwen3.8-27b` is a Groq preview model.**
> Preview models are for evaluation only and can be retired at short notice. In production: use a production/GA vision model with an SLA, pin the model ID in config, keep a tested fallback, and alert on `model_not_found` errors. See [docs/production-notes.md](docs/production-notes.md).

**Always needs a Production note:** preview or experimental models · free tiers used for real data · in-memory or file-based persistence · secrets in `.env` · disabled security checks · hard-coded limits · "run it on your laptop" deployments.

Every new note also gets a row in [docs/production-notes.md](docs/production-notes.md), which explains the general best practice: production/GA models, SLAs, deprecation policies, pinned model IDs, fallbacks, and monitoring.
