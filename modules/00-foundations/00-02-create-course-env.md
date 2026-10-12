# 00.02 (guide) · Create the course environment `lc-mastery`

> **Lesson 00.02, part 2.** Do this after [00-02-verify-environment.ipynb](00-02-verify-environment.ipynb) and before Lesson 00.03.
> **Time:** 10–20 minutes (most of it is waiting for downloads).
> **Shell:** Git Bash on Windows (Terminal on macOS/Linux). Anaconda Prompt works as a fallback; the differences are noted.
> **Docs verified:** 2026-10-11.

This is the **only install step in Module 00**. You will create one isolated environment for the whole course, so nothing you install can break Anaconda's `base` environment (or the other way round). The full, explained setup guide comes at the end of the course in [FULL_SETUP_APPENDIX.md](../../setup/FULL_SETUP_APPENDIX.md); this page is the minimum you need now.

**What you will have at the end**

| Thing | Name | Why |
|---|---|---|
| A conda environment | `lc-mastery` (Python 3.13) | All course packages live here, isolated from `base` |
| A Jupyter kernel | **Python (lc-mastery)** | Lets Jupyter (running from `base`) execute code with the course environment |
| The course package | `mastery`, installed in *editable* mode | Notebooks `import mastery`; your edits in `src/mastery/` apply after a kernel restart |

---

## Step 1 · Open Git Bash in the repository folder

**Option A (Explorer):** open the repo folder in File Explorer, right-click an empty area → *Show more options* (Windows 11) → **Open Git Bash here**.

**Option B (type it):** open Git Bash from the Start menu and `cd` into the repo. Paths with spaces **must be quoted**:

```bash
cd "/c/Users/<you>/Documents/AI courses/My-langchain-course/langchain-langgraph-mastery"
```

> Git Bash writes Windows paths with forward slashes and a lowercase drive: `C:\Users\you` becomes `/c/Users/you`, and `~` is your user folder. Tab completion (press **Tab** after typing a few letters) adds the quotes or escapes for you.

**Check:**

```bash
pwd
ls
```

**You should now see** your repo path, and files including `README.md`, `pyproject.toml`, `requirements.txt`, and folders `modules/`, `src/`, `tests/`.

---

## Step 2 · Make `conda` available in this Git Bash window

Anaconda does not add `conda` to Git Bash by default. Load conda's Bash support for this session (nothing is changed on disk):

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda --version
```

**You should now see** a version such as `conda 25.x.x` or `conda 26.x.x`. Any recent version works.

| If you see | Do this |
|---|---|
| `No such file or directory` | Anaconda is installed somewhere else. Try `source /c/ProgramData/anaconda3/etc/profile.d/conda.sh` (all-users install) or `source ~/miniconda3/etc/profile.d/conda.sh` (Miniconda). Find the folder with `ls ~ /c/ProgramData \| grep -i conda` |
| `conda: command not found` after sourcing | The path was wrong (see above). `type conda` should say *conda is a function* |

**Want this permanently?** Run once, then close and reopen Git Bash:

```bash
conda init bash
```

`conda init bash` adds a small block between `# >>> conda initialize >>>` markers to `~/.bash_profile`, which Git Bash reads at startup ([conda init docs](https://docs.conda.io/projects/conda/en/latest/commands/init.html)). Undo it any time with `conda init --reverse bash`. Details and the VS Code caveat: [VERIFY_ENVIRONMENT.md → Make conda work in Git Bash](../../setup/VERIFY_ENVIRONMENT.md#make-conda-work-in-git-bash).

> **macOS/Linux:** `conda init zsh` (macOS default shell) or `conda init bash`, then open a new terminal.
> **Anaconda Prompt (fallback):** `conda` already works there. Skip this step.

---

## Step 3 · Create the environment

```bash
conda create -n lc-mastery python=3.13 ipykernel -y
```

What each part means:

- `-n lc-mastery`: the environment's name. The course uses this exact name everywhere.
- `python=3.13`: the newest 3.13.x conda can find. The course needs **3.11+** (LangChain v1 needs 3.10+; `deepagents` and `ipykernel` 7.x declare 3.11+ on PyPI).
- `ipykernel`: the package that lets Jupyter run code in this env. Installing it **with conda, at creation time** follows the official advice "install as much as you can with conda first, then pip" ([conda: using pip in an environment](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#using-pip-in-an-environment)) and matches the [IPython kernel guide](https://ipython.readthedocs.io/en/stable/install/kernel_install.html).
- `-y`: answer "yes" to the confirmation.

**You should now see**, after 1–5 minutes, a package list and then:

```text
# To activate this environment, use
#
#     $ conda activate lc-mastery
```

**If it fails:**

| Error | Fix |
|---|---|
| `CondaToSNonInteractiveError: Terms of Service have not been accepted...` | Anaconda's default channels require accepting their Terms of Service once. Read them with `conda tos view`, accept with `conda tos accept`, then rerun Step 3 ([Anaconda: managing ToS on the command line](https://www.anaconda.com/docs/getting-started/tos-plugin)). Organizations should check the [Anaconda Terms of Service](https://www.anaconda.com/legal/terms/terms-of-service) |
| `CondaValueError: prefix already exists` | The env exists already. Use it (go to Step 4), or delete it with `conda remove -n lc-mastery --all` and retry |
| SSL / proxy errors on a company network | Ask IT for the proxy settings; see the conda docs on proxies. Try a personal network to confirm |

---

## Step 4 · Activate it and check which Python answers

```bash
conda activate lc-mastery
python --version
which python
```

**You should now see**

```text
(lc-mastery)              <- in your prompt
Python 3.13.x
/c/Users/<you>/anaconda3/envs/lc-mastery/python
```

If `which python` still shows `.../anaconda3/python` (base) or `.../WindowsApps/python`, the activation did not work: repeat Step 2 in this window, then `conda activate lc-mastery` again.

> **Rule for the whole course:** before any `python` or `pip` command in a terminal, check that the prompt shows `(lc-mastery)`.

---

<a id="step-4b"></a>

## Step 4b · Windows + Git Bash: check (and fix) the certificate path

> **Who needs this:** Windows users working in **Git Bash**. On macOS/Linux, or in Anaconda Prompt/PowerShell, run the check below; it should say `OK` and you can move on.

**Check** (with `(lc-mastery)` active):

```bash
python -c "import os, ssl; ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or None); print('OK, SSL_CERT_FILE =', os.environ.get('SSL_CERT_FILE', '(not set)'))"
```

**You should now see** a line starting with `OK`. If you see instead

```text
FileNotFoundError: [Errno 2] No such file or directory
```

and an `echo "$SSL_CERT_FILE"` that ends in `lc-mastery/ssl/cacert.pem` (no `Library` in it), apply the fix below. Without it, every API client in the course (Groq, LangSmith, ...) crashes before sending a single request.

### What is going on (plain English)

- **HTTPS needs a list of trusted certificate authorities**, the *CA bundle* (a file usually called `cacert.pem`). Python uses it to check that `api.groq.com` really is Groq.
- **`SSL_CERT_FILE`** is an environment variable that says "use *this* bundle file". Python's `ssl` module and `httpx` (the HTTP library inside the Groq and LangSmith SDKs) obey it. If it is not set, the SDKs use the bundle from the `certifi` package, which is fine.
- **Why conda sets it:** the env contains conda's own `openssl` package, which ships a bundle and an *activation script* (in `$CONDA_PREFIX/etc/conda/activate.d/`) that points `SSL_CERT_FILE` to it whenever you `conda activate`.
- **Why the path is wrong in Git Bash:** on Windows, conda packages put such files under `Library\`, so the real bundle is `%CONDA_PREFIX%\Library\ssl\cacert.pem`. The Windows scripts (`.bat`, PowerShell) use that path. But the Bash script, which Anaconda's openssl build also installs on Windows "for Windows Bash users", uses the Linux layout `$CONDA_PREFIX/ssl/cacert.pem`, a file that does not exist. This is a known packaging bug in Anaconda's `defaults` channel (conda-forge's build is not affected), still open at the time of writing: [anaconda-issues #13509](https://github.com/ContinuumIO/anaconda-issues/issues/13509), fix proposed in [AnacondaRecipes/openssl-feedstock PR #45](https://github.com/AnacondaRecipes/openssl-feedstock/pull/45) (background: [conda-forge/openssl-feedstock #231](https://github.com/conda-forge/openssl-feedstock/issues/231)).

### The fix: store the correct path in the environment

First confirm the real bundle exists:

```bash
ls "$CONDA_PREFIX/Library/ssl/cacert.pem"
```

**You should now see** the path printed back (no `No such file or directory`). Then:

```bash
conda env config vars set SSL_CERT_FILE="$(cygpath -m "$CONDA_PREFIX")/Library/ssl/cacert.pem"
conda deactivate && conda activate lc-mastery
```

How it works:

- `conda env config vars set` saves a variable **inside this environment** (in `conda-meta/state`). Conda sets it on every `conda activate lc-mastery`, in every shell (Git Bash, Anaconda Prompt, PowerShell, Jupyter kernels started from the env), and restores the old value on `conda deactivate` ([conda docs: setting environment variables](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#setting-environment-variables)).
- Conda exports these saved variables **before** it runs the packages' activation scripts (you can see the order in conda's `activate.py`). The openssl script only sets `SSL_CERT_FILE` when it is empty, so it now leaves yours alone.
- `cygpath -m` turns Git Bash's `/c/Users/...` into `C:/Users/...`: a Windows path with forward slashes, which Python, Git Bash and `cmd.exe` all understand.
- You must re-activate (second line) because the new value only applies on the next activation.

**Check again:** rerun the `python -c ...` check above. **You should now see** `OK, SSL_CERT_FILE = C:/Users/<you>/anaconda3/envs/lc-mastery/Library/ssl/cacert.pem`. `conda env config vars list` shows the saved value.

**Undo** (for example once Anaconda ships a fixed openssl):

```bash
conda env config vars unset SSL_CERT_FILE
conda deactivate && conda activate lc-mastery
```

> **Why not just `unset SSL_CERT_FILE`?** It works, but only for the current window: the next `conda activate` sets the wrong path again. Pointing the variable to the *right* file is permanent and keeps using conda's maintained bundle.
> **The course package checks this too.** `mastery.get_model()` and `mastery.config.load_settings()` stop with a clear `CertificateSettingError` that names the bad path and this fix, instead of a bare `FileNotFoundError` deep inside `httpx`. `python -m pytest` prints a warning at the top when the variable is broken.

---

## Step 5 · Install the course package (`mastery`) in editable mode

Still in the repo root, with `(lc-mastery)` active:

```bash
python -m pip install -e ".[dev]"
```

- `python -m pip` guarantees you use **this env's** pip (plain `pip` could be another one on the PATH).
- `-e` (editable): Python imports straight from `src/mastery/`, so your edits apply after a kernel restart. No reinstall needed.
- `".[dev]"`: this folder (`.`) plus the optional `dev` tools listed in [`pyproject.toml`](../../pyproject.toml) (`pytest`, `nbformat`). **Keep the quotes**: without them Bash may treat the square brackets as a filename pattern.

This also installs the package's own dependencies, `python-dotenv` and `httpx`. LangChain itself comes in Lesson 00.07, with `%pip` from the notebook.

**You should now see** a final line like `Successfully installed ... mastery-0.1.0 ... python-dotenv-1.2.x ...`.

**Check it, and run the course's unit tests** (offline, no API keys, a few seconds):

```bash
python -c "import mastery, mastery.config; print('mastery', mastery.__version__)"
python -m pytest
```

**You should now see** `mastery 0.1.0`, then a pytest summary ending in `passed` (some `skipped` or `deselected` is normal). If tests fail, read the first failure: it usually names the missing package or the wrong folder. Two common, harmless-to-fix failures are in the table below.

| Error | Fix |
|---|---|
| `ERROR: file:///... does not appear to be a Python project` | You are not in the repo root. `cd` to the folder that contains `pyproject.toml` |
| `No module named pip` | Run `conda install pip -y` in the env, then retry |
| Several tests fail with `mastery.doctor.CertificateSettingError: SSL_CERT_FILE points to a file that does not exist`, or (older checkout) `FileNotFoundError: [Errno 2] No such file or directory` raised from `ssl.create_default_context` / `load_verify_locations` | `SSL_CERT_FILE` points to a missing CA bundle (Windows + Git Bash). Do [Step 4b](#step-4b), then rerun `python -m pytest` |
| `test_notebook_hygiene` fails, saying a notebook (for example `00-02-verify-environment.ipynb`) has saved outputs | Expected if you ran and saved a notebook before this step: the course keeps notebooks **without outputs** in git, and this test enforces it. Clear them with `(lc-mastery)` active: `jupyter nbconvert --clear-output --inplace modules/00-foundations/00-02-verify-environment.ipynb`. `nbconvert` comes with the course's `[dev]` install (`python -m pip install -e ".[dev]"`); if you see `Jupyter command jupyter-nbconvert not found`, install it in the active env with `python -m pip install nbconvert`. Or, in Jupyter, *Edit → Clear Outputs of All Cells*, then save. Lesson 00.03 installs `nbstripout`, which strips outputs automatically at every commit, so this stops happening |

---

## Step 6 · Register the environment as a Jupyter kernel

```bash
python -m ipykernel install --user --name lc-mastery --display-name "Python (lc-mastery)"
jupyter kernelspec list
```

- `--user`: installs the kernelspec for your user only (no admin rights needed).
- `--name`: the internal name (notebooks in this course store `lc-mastery` in their metadata, so Jupyter selects it automatically).
- `--display-name`: what you see in Jupyter's kernel menu.

**You should now see** `Installed kernelspec lc-mastery in C:\Users\<you>\AppData\Roaming\jupyter\kernels\lc-mastery`, and `lc-mastery` in the list.

---

## Step 7 · Start Jupyter (from `base`) and pick the course kernel

Jupyter itself stays in `base`, where Anaconda installed it. It can run any registered kernel ([Python environments, compared → How every tool connects to Jupyter](../../setup/PYTHON_ENVIRONMENTS_COMPARED.md#how-every-tool-connects-to-jupyter-the-one-rule)).

```bash
conda activate base
cd "/c/Users/<you>/Documents/AI courses/My-langchain-course/langchain-langgraph-mastery"   # if not there already
jupyter notebook
```

**You should now see** log lines ending with a URL like `http://localhost:8888/tree?token=...`, and your browser opens the Jupyter file browser in the repo folder. (No browser? Copy that full URL into one.)

Then:

1. Open `modules/00-foundations/00-03-jupyter-fundamentals.ipynb`.
2. Top-right corner should say **Python (lc-mastery)**. If not: **Kernel → Change Kernel… → Python (lc-mastery)**.
3. In a new cell run `import sys; print(sys.executable)`. **You should now see** `C:\Users\<you>\anaconda3\envs\lc-mastery\python.exe`.

**To stop Jupyter:** go back to Git Bash and press **Ctrl + C**, then answer `y` (or press Ctrl + C twice). Save your notebooks first.

> **Anaconda Navigator alternative:** *Home → Jupyter Notebook → Launch*, browse to the repo, then pick the kernel as above.
> **Prefer JupyterLab?** `jupyter lab` works the same way. Everything in the course works in both.

---

## Alternative: the same environment with `uv`

If you prefer `uv` (see [the comparison](../../setup/PYTHON_ENVIRONMENTS_COMPARED.md#uv-one-fast-tool-for-almost-everything)), from the repo root in Git Bash:

```bash
uv venv --python 3.13          # creates .venv/ (gitignored)
source .venv/Scripts/activate  # Windows Git Bash   (macOS/Linux: source .venv/bin/activate)
uv pip install -e ".[dev]" ipykernel
python -m ipykernel install --user --name lc-mastery --display-name "Python (lc-mastery)"
```

The kernel name stays `lc-mastery`, so every notebook works unchanged. Official guide: [uv + Jupyter](https://docs.astral.sh/uv/guides/integration/jupyter/).

---

## Troubleshooting

Quick index of the failures learners hit most, also after pulling a new module. Run every fix in **Git Bash**, at the **repo root**, with `(lc-mastery)` active unless it says otherwise.

| Symptom | Fix |
|---|---|
| `conda: command not found` | [Step 2](#step-2--make-conda-available-in-this-git-bash-window): source `conda.sh` in this window |
| Prompt does not start with `(lc-mastery)` | `conda activate lc-mastery`. Every new Git Bash window needs it |
| `pip install` fails with `SSL: CERTIFICATE_VERIFY_FAILED` or `FileNotFoundError` from `ssl` | [Step 4b](#step-4b): fix `SSL_CERT_FILE`, open a new window, retry |
| `ModuleNotFoundError: No module named 'mastery'` (or `langchain`, `langgraph`) in a notebook | Wrong kernel: pick **Python (lc-mastery)** (top-right). In Git Bash, rerun `python -m pip install -e ".[dev]"`, then **Kernel → Restart** |
| `ImportError` / missing name right after `git pull` | A new module added code or packages: rerun `python -m pip install -e ".[dev]"`, then restart the kernel |
| **Python (lc-mastery)** missing from the kernel list | Redo [Step 6](#step-6--register-the-environment-as-a-jupyter-kernel), then reload the Jupyter browser tab |
| `pytest` fails in `test_notebook_hygiene` | A notebook was saved with outputs: see the table under [Step 5](#step-5--install-the-course-package-mastery-in-editable-mode) |
| `PermissionError: [WinError 32]` deleting a file in `data/outputs/` | A kernel still has it open: **Kernel → Shut Down**, then delete |

Still stuck? Copy the full error (no keys!) plus the output of `which python` and `python --version` into your notes before asking for help.

## Undo everything (if you ever need to start over)

```bash
jupyter kernelspec remove lc-mastery      # remove the kernel registration
conda remove -n lc-mastery --all          # delete the environment
conda init --reverse bash                 # only if you ran `conda init bash`
```

---

## ✅ Checkpoint

- [ ] `conda env list` shows `lc-mastery`.
- [ ] With `(lc-mastery)` active, `which python` points into `anaconda3/envs/lc-mastery`.
- [ ] The certificate check in Step 4b prints `OK`.
- [ ] `python -m pytest` ends with `passed`.
- [ ] Jupyter's kernel menu lists **Python (lc-mastery)**, and `sys.executable` in a notebook points into the env.

> ⚠️ **Production note: a hand-built environment is a learning shortcut.**
> `conda create` + `pip install` with version ranges gives you a working setup today, but not an identical one tomorrow. In production: pin exact versions in a lock file, build the environment in CI from scratch, and ship it as a container image. See [Python environments, compared](../../setup/PYTHON_ENVIRONMENTS_COMPARED.md#recommendation-for-this-course) and Lesson 13.06.

**Next:** [00.03 · Jupyter fundamentals](00-03-jupyter-fundamentals.ipynb) with the **Python (lc-mastery)** kernel.
