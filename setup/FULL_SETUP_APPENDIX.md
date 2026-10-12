# Appendix A: Full Environment Setup (placeholder)

> **Status:** 📝 To be written at the end of the course, once every module's dependencies are final.
> Until then, use [VERIFY_ENVIRONMENT.md](VERIFY_ENVIRONMENT.md) to check your machine. Each lesson tells you exactly what to install, with `%pip`, when it needs it.
> Background reading: [Python environments, compared](PYTHON_ENVIRONMENTS_COMPARED.md) explains pip, venv, virtualenv, conda (Anaconda/Miniconda/Miniforge/mamba), uv, Poetry, pipx, pyenv, and pixi, and why the course uses conda + pip by default.

## Planned contents

1. **Installing Anaconda or Miniconda on Windows** (and macOS/Linux notes)
   - Reference: [Anaconda docs](https://www.anaconda.com/docs/main)
2. **Creating the course environment** (conda env with Python 3.11+)
   - Reference: [Conda environments](https://www.anaconda.com/docs/getting-started/working-with-conda/environments), [Managing environments](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html)
3. **Registering the env as a Jupyter kernel** with `ipykernel`
   - Reference: [Installing the IPython kernel](https://ipython.readthedocs.io/en/stable/install/kernel_install.html)
4. **Installing course packages** from `requirements.txt` (re-verified on PyPI at publish time)
5. **Optional: `conda init powershell`** and VS Code setup
   - Reference: [VS Code Python environments](https://code.visualstudio.com/docs/python/environments), [VS Code Jupyter](https://code.visualstudio.com/docs/datascience/jupyter-notebooks)
6. **Alternative path: `uv`** instead of conda + pip (same notebooks, different setup)
   - Install on Windows: PowerShell installer, WinGet (`winget install --id=astral-sh.uv -e`), Scoop, or `pipx install uv`. Check with `uv --version`.
   - Course env with uv: `uv venv --python 3.13` then `uv pip install -r requirements.txt` (pip-compatible mode), **or** `uv init` + `uv add ...` (project mode with `uv.lock`).
   - Jupyter kernel with uv (pip-compatible mode): `uv pip install ipykernel`, then `.venv\Scripts\python -m ipykernel install --user --name lc-mastery`. Project mode (official uv guide): `uv add --dev ipykernel`, then `uv run ipython kernel install --user --env VIRTUAL_ENV <repo>\.venv --name=lc-mastery`, then `uv run --with jupyter jupyter lab`.
   - Reference: [uv docs](https://docs.astral.sh/uv/) · [Installation](https://docs.astral.sh/uv/getting-started/installation/) · [Install Python](https://docs.astral.sh/uv/guides/install-python/) · [Projects](https://docs.astral.sh/uv/guides/projects/) · [pip interface](https://docs.astral.sh/uv/pip/environments/) · [uv + Jupyter](https://docs.astral.sh/uv/guides/integration/jupyter/) · [Comparison doc](PYTHON_ENVIRONMENTS_COMPARED.md#uv-one-fast-tool-for-almost-everything)
7. **Git hooks:** `nbstripout --install`, pre-commit
   - Reference: [nbstripout](https://github.com/kynan/nbstripout), [pre-commit](https://pre-commit.com/)
8. **Accounts and API keys:** Groq and LangSmith (required); optional OpenAI (paid benchmark), Gemini (free-tier alternative), Tavily (web search comparison), Hugging Face (see `.env.example`)
9. **Local extras:** Docker Desktop with the WSL 2 backend (Module 12), Ollama on Windows (Module 13)
   - Reference: [Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/) · [Ollama on Windows](https://docs.ollama.com/windows)
10. **Troubleshooting:** kernel not found, `%pip` vs `pip` mismatch, SSL/proxy issues, long path issues on Windows
