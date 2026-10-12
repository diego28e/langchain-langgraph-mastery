# Verify Your Environment (Windows · Git Bash first)

> **Purpose:** confirm what is already installed. **Nothing in this file installs or changes anything.**
> Full installation instructions will be written at the end of the course in [FULL_SETUP_APPENDIX.md](FULL_SETUP_APPENDIX.md).
> Creating the course environment (`lc-mastery` + Jupyter kernel) is covered step by step in [Lesson 00.02's guide](../modules/00-foundations/00-02-create-course-env.md).
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
| Docker Desktop *(Lab 10B and Module 13 only)* | Any recent version | Self-hosted deployment | not required yet |

---

## Option A: Git Bash (recommended on Windows)

Git Bash comes with [Git for Windows](https://gitforwindows.org/). Open it from **Start → Git Bash**. It is the same `bash` shell the course uses on macOS and Linux, so every command in the course works unchanged.

### Make conda work in Git Bash

A default Anaconda install does **not** put `conda` on Git Bash's PATH. Load it for this window only (read-only: nothing on disk changes):

```bash
# Per-user install (the default): C:\Users\<you>\anaconda3  ->  ~/anaconda3 in Git Bash
source ~/anaconda3/etc/profile.d/conda.sh

# All-users install instead? Use:  source /c/ProgramData/anaconda3/etc/profile.d/conda.sh
# Miniconda?                   Use:  source ~/miniconda3/etc/profile.d/conda.sh
# Not sure where it is? List the candidates:
ls -d ~/anaconda3 ~/miniconda3 /c/ProgramData/anaconda3 2>/dev/null

conda activate base      # Activates Anaconda's base env in this window only
```

**You should now see** `(base)` at the start of your prompt. Closing the window undoes it. Making this permanent (`conda init bash`) is a one-time setup step, explained in [Lesson 00.02's guide](../modules/00-foundations/00-02-create-course-env.md) ([conda init docs](https://docs.conda.io/projects/conda/en/latest/commands/init.html)).

### Run the checks

```bash
# 1) Python version and which python answers (first match wins)
python --version
which -a python
python -c 'import sys; print(sys.executable)'

# 2) conda version, base location, and existing environments
conda --version
conda info
conda env list

# 3) pip version (and which Python it belongs to)
python -m pip --version

# 4) Jupyter components and available kernels
jupyter --version
jupyter notebook --version
jupyter lab --version
jupyter kernelspec list

# 5) git (and bash itself)
git --version
echo "$BASH_VERSION"

# 5b) Optional tools ("command not found" is fine: neither is required yet)
uv --version
docker --version

# 6) Are any course packages already present? ("not found" warnings are fine)
python -m pip show langchain langgraph langchain-groq python-dotenv ipykernel
```

**You should now see** Python 3.11 or newer (for example `Python 3.13.5`), a `sys.executable` under your Anaconda folder (Git Bash prints it in Windows form, e.g. `C:\Users\<you>\anaconda3\python.exe`), and versions for conda, pip, Jupyter, and git.

### Git Bash path quirks (read once)

| Windows writes | Git Bash writes | Note |
|---|---|---|
| `C:\Users\Ana\anaconda3` | `/c/Users/Ana/anaconda3` | Forward slashes; drive letter becomes `/c/` |
| `%USERPROFILE%` | `~` or `$HOME` | `cd ~` goes to `C:\Users\<you>` |
| `C:\Users\Ana Maria\repo` | `"/c/Users/Ana Maria/repo"` | Quote paths with spaces (or escape: `Ana\ Maria`) |
| `cd` (no args) prints the folder | `pwd` (`pwd -W` prints the Windows form) | |

### Troubleshooting

| Symptom | Fix |
|---|---|
| `conda: command not found` | Run the `source .../conda.sh` line from [Make conda work in Git Bash](#make-conda-work-in-git-bash) (check the path with the `ls -d` line) |
| `python` opens the Microsoft Store or prints nothing | Windows "App execution aliases" are intercepting it. **Settings → Apps → Advanced app settings → App execution aliases**, turn off `python.exe` and `python3.exe`, then open a new Git Bash window. Or load and activate conda first (see above) |
| `python` with no arguments seems to hang | The interactive Python prompt needs a console helper in some Git Bash versions. Use `winpty python`, or just run scripts and notebooks (the course never needs the interactive prompt) |
| API clients (Groq, LangSmith, httpx) fail with `FileNotFoundError: [Errno 2] No such file or directory` from `ssl.create_default_context`, or `mastery` raises `CertificateSettingError` | `SSL_CERT_FILE` points to a missing file (Anaconda's openssl script uses the wrong path in Git Bash). Check with `echo "$SSL_CERT_FILE"`; fix with [Step 4b of the create-course-env guide](../modules/00-foundations/00-02-create-course-env.md#step-4b) |
| `Jupyter command jupyter-nbconvert not found` (when clearing outputs with `jupyter nbconvert --clear-output --inplace ...`) | `nbconvert` is not installed in the active env. It comes with the course `[dev]` install (`python -m pip install -e ".[dev]"`); or install it alone with `python -m pip install nbconvert` |
| `which -a python` shows several paths | Normal. The first one is what runs. After `conda activate`, the env's Python should be first |

## Option B: macOS / Linux terminal

Open **Terminal**. If you installed Anaconda with its installer and accepted `conda init`, `(base)` is already in your prompt; otherwise run `source ~/anaconda3/etc/profile.d/conda.sh`. Then run the same commands as [Run the checks](#run-the-checks). Python is usually `python3` outside conda; inside a conda env, `python` works.

## Fallback: Anaconda Prompt (Windows)

If Git Bash isn't available, open **Start → Anaconda Prompt**, where `conda` is already on the PATH. Commands differ slightly in `cmd`:

```bat
:: Same checks as above, cmd syntax
python --version
where python
python -c "import sys; print(sys.executable)"
conda --version
conda env list
python -m pip --version
jupyter --version
jupyter kernelspec list
git --version
```

---

## Option C: Verify from inside a notebook

Open [`modules/00-foundations/00-02-verify-environment.ipynb`](../modules/00-foundations/00-02-verify-environment.ipynb) (it runs these checks with explanations), or paste these cells into a scratch notebook:

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
- If `sys.executable` points to `...\anaconda3\python.exe`, you're in the **base** environment. Lesson 00.02's guide creates the dedicated `lc-mastery` env and kernel: [00-02-create-course-env.md](../modules/00-foundations/00-02-create-course-env.md).
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
