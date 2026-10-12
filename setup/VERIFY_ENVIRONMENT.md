# Verify Your Environment (Windows)

> **Purpose:** confirm what is already installed. **Nothing in this file installs or changes anything.**
> Full installation instructions will be written at the end of the course in [FULL_SETUP_APPENDIX.md](FULL_SETUP_APPENDIX.md).
> Not sure what conda, venv, or uv are? Read [Python environments, compared](PYTHON_ENVIRONMENTS_COMPARED.md) first.
> Last reviewed: 2026-10-11.

---

## What you need (minimums)

| Tool | Minimum | Why | Your machine (fill in) |
|---|---|---|---|
| Python | **3.11** (3.10 works for LangChain/LangGraph, but Deep Agents and `ipykernel` 7.x need 3.11+) | [Install LangChain](https://docs.langchain.com/oss/python/langchain/install) says Python 3.10+. PyPI metadata for `deepagents` and `ipykernel` says ≥ 3.11 | e.g. 3.13.5 |
| conda (Anaconda) | Any recent version | Environments and kernels | |
| pip | Any recent version | Installing LangChain packages | |
| Jupyter Notebook / JupyterLab | Notebook 7.x or JupyterLab 4.x recommended | Course notebooks | |
| git | Any recent version | Version control | |
| uv *(optional)* | Any 0.x version | Optional alternative to conda + pip ([comparison](PYTHON_ENVIRONMENTS_COMPARED.md)) | not required |
| Docker Desktop *(Module 12 only)* | Any recent version | Self-hosted deployment | not required yet |

---

## Option A: Anaconda Prompt (recommended)

Open **Start → Anaconda Prompt**. On a default Anaconda install, `conda` is only on the PATH inside this prompt (and inside "Anaconda PowerShell Prompt").

```bat
:: 1) Python version and which python.exe answers
python --version
where python
python -c "import sys; print(sys.executable)"

:: 2) conda version, base location, and existing environments
conda --version
conda info
conda env list

:: 3) pip version (and which Python it belongs to)
pip --version
python -m pip --version

:: 4) Jupyter components and available kernels
jupyter --version
jupyter notebook --version
jupyter lab --version
jupyter kernelspec list

:: 5) git
git --version

:: 5b) Optional tools ("not recognized" is fine: neither is required yet)
uv --version
docker --version

:: 6) Are any course packages already present? ("not found" is fine)
pip show langchain langgraph langchain-groq python-dotenv ipykernel
```

## Option B: Windows PowerShell

`conda` is **not** on your PowerShell PATH, which is the default for Anaconda. You can still verify everything. Pick one of these:

**B1. Use "Anaconda PowerShell Prompt"** (Start menu). It's PowerShell with conda already activated. Run the same commands as Option A (use `#` for comments instead of `::`).

**B2. Use a regular PowerShell window (read-only checks):**

```powershell
# PowerShell version
$PSVersionTable.PSVersion

# Every python.exe on the PATH, in resolution order
Get-Command python -All | Select-Object Source

# Python launcher: list installed interpreters, if the launcher is installed
py -0p

# Python and pip versions of the first python on the PATH
python --version
python -m pip --version

# Jupyter and git (may fail if Anaconda's Scripts folder is not on the PATH, which is expected)
jupyter --version
git --version

# Optional tools ("not recognized" is fine: neither is required yet)
uv --version
docker --version

# Is conda reachable here? (Expected: not found. That's OK, use Option A or B1)
Get-Command conda -ErrorAction SilentlyContinue

# Where is Anaconda installed? (common locations, read-only)
Test-Path "$env:USERPROFILE\anaconda3"
Test-Path "$env:ProgramData\anaconda3"
```

> Don't run `conda init powershell` yet. It edits your PowerShell profile. The full setup appendix will cover it as an optional step.

---

## Option C: Verify from inside a notebook

Create a scratch notebook (or use `modules/00-foundations/00-02-verify-environment.ipynb` once it exists) and run:

```python
# Which interpreter is THIS kernel using? It should match the env you expect.
import platform
import sys
from importlib import metadata

print("Python      :", sys.version.split()[0])
print("Executable  :", sys.executable)
print("Platform    :", platform.platform())

# Versions of course packages (prints "not installed" instead of failing)
packages = [
    "notebook", "jupyterlab", "ipykernel", "pip",
    "langchain", "langchain-core", "langgraph", "langchain-groq",
    "langsmith", "python-dotenv",
]
for name in packages:
    try:
        print(f"{name:<16}", metadata.version(name))
    except metadata.PackageNotFoundError:
        print(f"{name:<16}", "not installed")
```

```python
# %pip always targets the kernel's environment (unlike !pip, which may not).
%pip --version
```

```python
# List the kernels Jupyter knows about
!jupyter kernelspec list
```

**Interpretation**
- If `sys.executable` points to `...\anaconda3\python.exe`, you're in the **base** environment. The course will create a dedicated env + kernel in Module 00/02 (documented in the appendix).
- If `%pip --version` and the terminal's `pip --version` point to different Pythons, packages you install in the terminal won't be visible in the notebook. This is the #1 beginner issue, covered in the Jupyter track ([Installing the IPython kernel](https://ipython.readthedocs.io/en/stable/install/kernel_install.html), [IPython magics](https://ipython.readthedocs.io/en/stable/interactive/magics.html)).

---

## Record your results

Copy this into `docs/research-log.md` (first entry):

```text
Date:
Python:            (version + path)
conda:             (version)
pip:               (version + which python)
Notebook / Lab:    (versions)
Kernels:           (from jupyter kernelspec list)
git:               (version)
uv (optional):     (version or "not installed")
Notes / surprises:
```
