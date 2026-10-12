# Python Environments, Compared (in Plain English)

> pip, venv, virtualenv, conda (Anaconda / Miniconda / Miniforge / mamba / conda-forge), uv, Poetry, pipx, pyenv, and pixi: what each one is, when to use it, and how it works with Jupyter on Windows.
> **Verified against the official docs on October 11, 2026.** Versions mentioned: uv 0.13.0, Poetry 2.5.1 (PyPI, same date).
> Related: [VERIFY_ENVIRONMENT.md](VERIFY_ENVIRONMENT.md) (check what you have) · [FULL_SETUP_APPENDIX.md](FULL_SETUP_APPENDIX.md) (step-by-step setup, written at the end of the course).

---

## First, three ideas that make everything else easy

1. **An interpreter** is the `python.exe` that runs your code. You can have several on one machine (3.11, 3.13…).
2. **An environment** is a folder with one interpreter plus its own installed packages. Projects get their own environment so that upgrading a package for project A cannot break project B.
3. **A package installer** downloads packages (from **PyPI** for pip/uv/Poetry, or from **conda channels** like `conda-forge` for conda/mamba/pixi) and puts them into an environment.

Most tools below do one, two, or all three of these jobs. The confusion comes from the overlap.

| Tool | Installs Python itself? | Creates environments? | Installs packages from | Lock file? |
|---|---|---|---|---|
| pip | ❌ | ❌ | PyPI | ❌ (requirements files only) |
| venv | ❌ | ✅ | — (uses pip) | ❌ |
| virtualenv | ❌ | ✅ | — (seeds pip) | ❌ |
| conda / mamba | ✅ | ✅ | conda channels (+ pip inside) | Via extra tools/exports |
| uv | ✅ | ✅ | PyPI | ✅ `uv.lock` |
| Poetry | ❌ | ✅ | PyPI | ✅ `poetry.lock` |
| pipx | ❌ | ✅ (one per app, hidden) | PyPI | ❌ |
| pyenv / pyenv-win | ✅ | ❌ (plugins exist) | — | ❌ |
| pixi | ✅ | ✅ | conda channels + PyPI | ✅ `pixi.lock` |

---

## The tools, one by one

### pip: the standard package installer
- **What it is:** Python's default installer for packages from PyPI. Comes with Python.
- **Use it when:** you are inside an environment (venv, conda, anything) and need to install packages. Always run it as `python -m pip ...` so you know *which* Python receives the package.
- **Pros:** everywhere, simple, the reference behaviour for everything else.
- **Cons:** does not create environments or manage Python versions. No real lock file. Slower than uv.
- **Windows notes:** prefer `python -m pip` over bare `pip`. In Jupyter, use the `%pip install ...` magic, which installs into the **kernel's** environment (not the `!pip` shell command, which can hit a different Python).
- **Jupyter:** works in any environment that has `ipykernel`.
- **Docs:** [pip](https://pip.pypa.io/en/stable/) · [pip user guide](https://pip.pypa.io/en/stable/user_guide/)

### venv: virtual environments in the standard library
- **What it is:** a module built into Python (since 3.3) that creates lightweight environments: `python -m venv .venv`.
- **Use it when:** you have a normal Python install and want the zero-extra-tools option.
- **Pros:** nothing to install, official, well understood.
- **Cons:** uses whatever Python you run it with (no version management). Slower to create than virtualenv/uv.
- **Windows notes:** activate with `.venv\Scripts\activate.bat` (cmd) or `.venv\Scripts\Activate.ps1` (PowerShell). PowerShell may block the script until you allow it for your user with an execution policy (the venv docs show the command).
- **Jupyter:** `python -m pip install ipykernel`, then `python -m ipykernel install --user --name myproj --display-name "Python (myproj)"`.
- **Docs:** [venv](https://docs.python.org/3/library/venv.html) · [Tutorial: virtual environments](https://docs.python.org/3/tutorial/venv.html) · [Packaging guide: pip + venv](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)

### virtualenv: the faster, older sibling of venv
- **What it is:** a third-party tool that also creates environments. Its docs describe it as "faster and more featureful than venv", while staying pure Python with plugins.
- **Use it when:** a project or tool (for example tox, older CI setups) asks for it, or you need its extra features.
- **Pros:** fast creation with caching, works with many interpreters, extensible.
- **Cons:** one more tool to install. For most new projects, venv or uv is enough.
- **Jupyter:** same as venv (install `ipykernel`, register the kernel).
- **Docs:** [virtualenv](https://virtualenv.pypa.io/en/latest/) · [venv vs virtualenv vs uv](https://virtualenv.pypa.io/en/latest/explanation.html)

### conda and its family: Anaconda, Miniconda, Miniforge, mamba, conda-forge
- **What conda is:** a cross-language package **and** environment manager. It installs Python itself, plus compiled libraries (CUDA, MKL, GDAL…) that pip sometimes struggles with. It now uses the fast **libmamba** solver by default.
- **The family, untangled:**
  - **Anaconda Distribution:** an installer with conda, Python, **Anaconda Navigator**, and hundreds of data-science packages pre-installed in `base`. (This is probably what you have.)
  - **Miniconda:** the same conda, but a minimal install. You add only what you need.
  - **conda-forge:** a community-run **channel** (package source) with a very large collection of packages.
  - **Miniforge:** the installer that the conda-forge project calls its preferred one. It includes conda and mamba and uses conda-forge by default.
  - **mamba / micromamba:** a fast, drop-in replacement for the `conda` command (`mamba install ...`). micromamba is a single static binary, handy in Docker and CI.
- **Use it when:** you already have Anaconda (as in this course), you need non-Python binary dependencies, or you work in data science teams that standardise on conda.
- **Pros:** manages Python versions, great for heavy scientific/GPU stacks, Anaconda Navigator for beginners, works well on Windows.
- **Cons:** big installs (Anaconda), slower than uv, mixing conda and pip needs care. The Anaconda **default channel is covered by Anaconda's Terms of Service**, so organisations should read them (conda-forge is a community alternative).
- **Mixing with pip (official advice):** install as much as you can with conda first, then pip. If you need to change conda packages after using pip, prefer creating a fresh environment. Don't use `pip install --user` in conda environments.
- **Windows notes:** use **Anaconda Prompt** (it puts `conda` on PATH), or run `conda init powershell` once if you want it in PowerShell.
- **Jupyter:** the course pattern is: create `conda create -n lc-mastery python=3.13`, activate it, `conda install ipykernel` (or `python -m pip install ipykernel`), then `python -m ipykernel install --user --name lc-mastery --display-name "Python (lc-mastery)"`. Jupyter can keep running from `base` and still use the course kernel.
- **Docs:** [conda](https://docs.conda.io/projects/conda/en/stable/) · [Getting started](https://docs.conda.io/projects/conda/en/stable/user-guide/getting-started.html) · [Manage environments](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html) · [Using pip in an environment](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html#using-pip-in-an-environment) · [libmamba solver](https://conda.github.io/conda-libmamba-solver/) · [Anaconda vs Miniconda](https://www.anaconda.com/docs/getting-started/concepts/anaconda-or-miniconda) · [Anaconda docs](https://www.anaconda.com/docs/main) · [Anaconda Terms of Service](https://www.anaconda.com/legal/terms/terms-of-service) · [conda-forge](https://conda-forge.org/docs/) · [Miniforge download](https://conda-forge.org/download/) · [Miniforge repo](https://github.com/conda-forge/miniforge) · [mamba](https://mamba.readthedocs.io/en/latest/)

### uv: one fast tool for (almost) everything
- **What it is:** a Python package and project manager written in Rust by Astral. Its docs call it "a single tool to replace pip, pip-tools, pipx, poetry, pyenv, twine, virtualenv, and more", and "10-100x faster than pip".
- **Two ways to use it:**
  - **pip-compatible mode:** `uv venv`, then `uv pip install -r requirements.txt`. Same mental model as venv + pip, just faster.
  - **Project mode:** `uv init`, `uv add langchain`, `uv run ...`. Dependencies go in `pyproject.toml`, exact versions in `uv.lock`, and the `.venv` is kept in sync for you.
- **Also:** installs Python versions (`uv python install 3.13`) and CLI tools (`uv tool install ruff`, like pipx).
- **Use it when:** you start a new project outside conda, want reproducible lock files, or want fast CI and Docker builds (Module 13 uses it in the Dockerfile).
- **Pros:** very fast, lock files, manages Python too, great Docker/CI story, growing fast in the Python community.
- **Cons:** PyPI only (no conda binary packages). Newer tool (0.x versions), so commands still evolve. One more mental model to learn.
- **Windows notes:** install with PowerShell (`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`), WinGet (`winget install --id=astral-sh.uv -e`), Scoop, or `pipx install uv`. Read any script before piping it into your shell.
- **Jupyter (official uv guide):** `uv add --dev ipykernel`, then `uv run ipython kernel install --user --env VIRTUAL_ENV <project>\.venv --name=<project>`, then start Jupyter with `uv run --with jupyter jupyter lab`. Inside a notebook, `!uv add <pkg>` updates the project, and `%pip install` still works.
- **Docs:** [uv](https://docs.astral.sh/uv/) · [Installation](https://docs.astral.sh/uv/getting-started/installation/) · [Projects](https://docs.astral.sh/uv/guides/projects/) · [Install Python](https://docs.astral.sh/uv/guides/install-python/) · [Tools](https://docs.astral.sh/uv/guides/tools/) · [pip interface: environments](https://docs.astral.sh/uv/pip/environments/) · [uv with Jupyter](https://docs.astral.sh/uv/guides/integration/jupyter/)

### Poetry: dependency management and packaging
- **What it is:** "a tool for dependency management and packaging in Python". You declare dependencies in `pyproject.toml`, Poetry resolves them into `poetry.lock`, manages the virtual environment, and builds/publishes your package.
- **Use it when:** you join a team or open-source project that already uses Poetry, or you publish libraries and like its workflow.
- **Pros:** mature, lock files, good packaging and publishing story, clear CLI.
- **Cons:** slower than uv. Does not install Python. Its docs say to install it in its own isolated environment (for example with pipx), not inside your project.
- **Jupyter:** `poetry add --group dev ipykernel`, then `poetry run python -m ipykernel install --user --name myproj`.
- **Docs:** [Poetry](https://python-poetry.org/docs/) · [Managing environments](https://python-poetry.org/docs/managing-environments/)

### pipx: install Python *applications*, not libraries
- **What it is:** installs command-line tools (ruff, pre-commit, poetry, nbstripout…) each in its own hidden environment, and puts the command on your PATH.
- **Use it when:** you want a tool available everywhere without polluting any project environment. (`uv tool install` does the same job.)
- **Pros:** clean global tools, easy upgrades.
- **Cons:** not for libraries you `import` in notebooks.
- **Jupyter:** not relevant (don't install JupyterLab for a course kernel with pipx unless you know why).
- **Docs:** [pipx](https://pipx.pypa.io/stable/)

### pyenv (and pyenv-win): switch between Python versions
- **What it is:** a version manager. It installs several Pythons and lets you choose one per folder or per shell.
- **Windows notes:** **pyenv itself does not support Windows** (only inside WSL). On Windows use the separate project **pyenv-win**, or let uv or conda install Python versions for you.
- **Use it when:** you maintain code for several Python versions on macOS/Linux.
- **Pros:** simple, single-purpose. **Cons:** you still need venv/uv/Poetry for environments.
- **Docs:** [pyenv](https://github.com/pyenv/pyenv) · [pyenv-win](https://github.com/pyenv-win/pyenv-win) · [Using Python on Windows](https://docs.python.org/3/using/windows.html)

### pixi: conda packages with a modern project workflow
- **What it is:** a fast package manager (by prefix.dev) that uses **conda-forge packages plus PyPI**, with built-in lock files, tasks, and multiple environments per project.
- **Use it when:** you need conda's binary packages *and* want uv-style reproducible projects (for example robotics, geospatial, GPU stacks).
- **Pros:** reproducible, cross-platform (Windows included), task runner. **Cons:** smaller community than conda/uv. Another tool to learn.
- **Jupyter:** has an official JupyterLab integration guide.
- **Docs:** [pixi](https://pixi.sh/latest/) · [Python tutorial](https://pixi.sh/latest/python/tutorial/) · [JupyterLab integration](https://pixi.sh/latest/integration/editor/jupyterlab/)

---

## How every tool connects to Jupyter (the one rule)

Jupyter runs code in a **kernel**. A kernel is tied to **one environment's Python**. Whatever tool built that environment, the recipe is the same:

1. Install `ipykernel` **into the project environment**.
2. Register it once: `python -m ipykernel install --user --name <name> --display-name "Python (<name>)"` (run with the environment's Python).
3. In Jupyter, pick that kernel (*Kernel → Change kernel*).
4. Check inside the notebook: `import sys; print(sys.executable)` must point into that environment.
5. Install packages from a notebook with `%pip install ...` (it targets the running kernel).

Docs: [Installing the IPython kernel](https://ipython.readthedocs.io/en/stable/install/kernel_install.html).

---

## Recommendation for this course

| You are… | Use | Why |
|---|---|---|
| **Following the course on Windows with Anaconda (default)** | **conda** for the environment (`lc-mastery`, Python 3.13) + **pip** (`%pip` in notebooks) for LangChain packages | You already have it. Anaconda Prompt + Jupyter work out of the box. LangChain packages are on PyPI, so pip inside the conda env is the simplest path |
| Starting fresh, no Anaconda, or you like modern tooling | **uv** (project mode) | Fast, one tool, lock file. Same notebooks, different setup |
| Packaging `src/mastery` and deploying it (Module 13) | **uv** inside Docker | Reproducible, fast builds. Taught in Lesson 13.06 |
| Global CLI tools (ruff, pre-commit, nbstripout) | **pipx** or `uv tool install` | Keeps tools out of the course env |
| Need heavy binary deps (CUDA, GDAL) in Module 14 | **conda** (conda-forge) or **pixi** | Binary packages pip can't easily provide |

**Rules of thumb:** one environment per project · never install course packages into `base` · always know which Python a command uses (`where python` on Windows, `sys.executable` in Jupyter) · don't mix tools inside one environment unless you follow the tool's official advice (conda first, then pip).

> ⚠️ **Production note: environments on your laptop are not deployments.**
> A conda env you built by hand is hard to reproduce. In production, pin exact versions in a lock file (`uv.lock`, `poetry.lock`, `pixi.lock`, or a fully pinned `requirements.txt`), build in CI from a clean image, and ship a container. The course's `requirements.txt` uses minimum versions with upper bounds for learning; Module 13 shows the locked, containerised version.

General background: [Python Packaging User Guide: tool recommendations](https://packaging.python.org/en/latest/guides/tool-recommendations/) · [Installing packages](https://packaging.python.org/en/latest/tutorials/installing-packages/).
