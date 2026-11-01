# Taking the course on Google Colab (or on your PC)

You can take **most of the course on Google Colab**, with nothing installed on your computer, or **on your own PC** (the setup the course is developed on). You can also mix them: a lesson runs the same way in both places, so you can move between them at any time. A few lessons need things a Colab runtime doesn't have (Docker, Ollama, a server your browser can reach). Those say so at the top and link to the PC setup below.

**On Colab, these are the core steps:**

1. **Run [colab/START_HERE.ipynb](https://colab.research.google.com/github/diego28e/langchain-langgraph-mastery/blob/main/colab/START_HERE.ipynb) once: Runtime → Run all.** When Google asks for Drive access, tick **Select all** ([details](#setup)).
2. **You do NOT upload anything.** START_HERE copies the course into your Drive: **My Drive/langchain-langgraph-mastery**.
3. **Open every lesson from Drive:** [drive.google.com](https://drive.google.com/drive/my-drive) → My Drive → langchain-langgraph-mastery → modules → a module → right-click the `.ipynb` → **Open with → Google Colaboratory**.
4. **Check the title bar shows the Drive icon, not "Save in GitHub"** (that is the read-only GitHub copy: your edits won't be saved).
5. **Next time: File → Open notebook → Recent.** Colab's *Google Drive* tab only lists notebooks you opened recently, so don't use it to browse.
6. **Add your keys as [Colab Secrets](#secrets) (🔑).** Each lesson asks only for the keys it uses.

| | 💻 Your PC (or the devcontainer) | ☁️ Google Colab |
|---|---|---|
| Setup | 20–40 min once: [00-02-create-course-env.md](../modules/00-foundations/00-02-create-course-env.md) | 3–5 min once: run [colab/START_HERE.ipynb](https://colab.research.google.com/github/diego28e/langchain-langgraph-mastery/blob/main/colab/START_HERE.ipynb) |
| Each lesson | Opens instantly in the `Python (lc-mastery)` kernel | Its first cell installs the course into that runtime (1–3 min, once per runtime) |
| Keys | `.env` (copied from `.env.example`) | **Colab Secrets** (🔑 in the sidebar), same names |
| Your files | Your clone | Your clone in Google Drive (`MyDrive/langchain-langgraph-mastery`) |
| Lessons | All of them | All except the few marked ❌ ([the table](#per-module)) |

<a id="setup"></a>
## Setting up Colab, in detail

1. Open [colab/START_HERE.ipynb](https://colab.research.google.com/github/diego28e/langchain-langgraph-mastery/blob/main/colab/START_HERE.ipynb) and choose **Runtime → Run all**. When Google asks for Drive access, choose the account you use for Colab, tick **Select all**, then **Continue** (ticking only some permissions makes the mount fail; allow pop-ups for `colab.research.google.com` if no window opens). It clones the course into your Drive (or updates it later), installs it with the Colab-tested versions, and shows a ✅ table.
2. If it stops with **"Restart once"**: **Runtime → Restart session**, then **Runtime → Run all** again. The second run skips the install.
3. Add your keys as **Colab Secrets** ([below](#secrets)). Then open each lesson **from Drive** ([how](#open-lessons)) and run it from the top.

**How a lesson finds the course on Colab.** Every notebook's first code cell (*Setup 1*) detects Colab, mounts Drive if needed, and uses the clone START_HERE made: `MyDrive/langchain-langgraph-mastery` first, then `/content/langchain-langgraph-mastery`. If Drive is still showing the clone (just after START_HERE), it waits up to 30 s. It then calls `mastery.colab.prepare_runtime()`, which:
- installs the course (`pip install -e ".[colab]" -c constraints/colab-2026-10.txt`) **once per runtime** (a stamp file in `/tmp` survives *Restart session*, so it isn't repeated);
- also installs `[studio]` or `[embeddings]` at the tested versions when the lesson's *Step 0* `%pip` cell already brought `langgraph-cli` or `fastembed`;
- asks you to **restart once** only if it upgraded a package the kernel had already imported;
- copies **only the Colab Secrets this lesson uses** into the environment (the setup cell lists them; a key a cell needs later is read when `require_env` or `get_model` asks for it), never overwriting a variable that is already set. Each secret you read the first time in a notebook shows Colab's access prompt, so fewer names means fewer prompts; a key you never added is just skipped;
- prints **🔗 links to the notebooks and docs this lesson links to** (the previous and next lesson, the module README...). They open the Drive copies, because a lesson's own Markdown links don't work on Colab (see the troubleshooting table below).

On your PC none of this runs: the same cell behaves exactly as before.

<a id="open-lessons"></a>
**Open lessons from Drive to keep your edits.** You do NOT upload anything: START_HERE already put the course in **My Drive/langchain-langgraph-mastery**. In [drive.google.com](https://drive.google.com/drive/my-drive) go to **My Drive → langchain-langgraph-mastery → modules →** a module, right-click the lesson's `.ipynb` → **Open with → Google Colaboratory**. The title bar then shows the Drive icon; afterwards **File → Open notebook → Recent** finds it again. That edits your clone directly, everything the lessons write (`data/outputs/`) lands in your Drive, and Colab remembers the Secrets access you grant each notebook.
- **Title bar says "Save in GitHub"?** You opened the read-only GitHub copy (an **Open in Colab** badge does that): your edits won't be saved. Close it and open the lesson from Drive. The setup cell prints *"Opened from GitHub: ..."* when it can tell.
- **Don't browse with File → Open notebook → Google Drive:** that tab only lists notebooks you opened recently (at first just "Untitled"), not your folders.

<a id="secrets"></a>
## Keys: Colab Secrets

Click **🔑 Secrets** in Colab's left sidebar → **Add new secret**. Use the names below (the same as in `.env.example`) and switch **Notebook access** on for each one. `mastery.config.load_env()` (which every lesson calls) reads the ones that lesson uses (its setup cell lists them); `load_colab_secrets()` is the helper behind it.

| Secret | When |
|---|---|
| `GROQ_API_KEY` | Module 00 onward (most 💸 cells) |
| `LANGSMITH_API_KEY`, `LANGSMITH_TRACING` (`false`), `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT` | Traces, from Lesson 01.08 (optional) |
| `TAVILY_API_KEY`, `MASTERY_WEB_SEARCH` | Web search, Module 05 (optional) |
| `GOOGLE_API_KEY` | Gemini lessons (optional) |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Paid comparisons (optional) |
| `HF_TOKEN` | Hugging Face, Module 14 |
| `DAYTONA_API_KEY` | Cloud sandbox, Lesson 11.09 (optional) |
| `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL` | Module 15 (optional) |
| `PINECONE_API_KEY` | Pinecone stretch goal, Module 06 (optional) |
| `OLLAMA_BASE_URL`, `MASTERY_DEEP_MODEL`, `MASTERY_DEEP_SUBAGENT_MODEL` | Overrides (optional) |

Without a key, 💸 cells print `⏭️ Skipped` and everything else runs, exactly like on your PC. Added a secret mid-lesson? **Runtime → Restart session** and run again (secrets are read once per session). Only the names in this table are read from Secrets. Other settings from `.env.example` (model overrides, `M12_POSTGRES_URL`, ...) go in a `.env` file at the root of your Drive clone, which works exactly as on your PC; a variable already set (for example from a secret) always wins. Keep keys in Secrets: they never end up in a file you might share.

<a id="per-module"></a>
## What runs where

✅ runs on Colab · ⚠️ runs on Colab except the parts named · ❌ take it on your PC or in the devcontainer

| Module | Colab | Notes |
|---|---|---|
| 00 Foundations | ✅ | 00.02 checks *Colab's* Python; the env guide (00-02-create-course-env.md) is for your PC only. 00.03's menus differ slightly (Ctrl + M shortcuts) |
| 01 Models, messages & prompts | ✅ | 01.08: LangSmith keys as Colab Secrets |
| 02 Tools & first agents | ✅ / ❌ 02.07 | **02.07 Studio first look** needs your PC ([Studio](#studio)) |
| 03 Memory & context | ✅ | 03.04's optional real embeddings: install `[embeddings]` (the lesson shows the `%pip` line) |
| 04 Middleware, guardrails, HITL | ✅ | |
| 05 MCP & external tools | ✅ | Terminal commands become `!command` in a code cell; a server that waits blocks its cell, and clients on your PC can't reach it |
| 06 RAG | ✅ | Step 0 installs `fastembed`; the pgvector stretch goal needs [Docker](#docker) |
| 07 LangGraph fundamentals | ⚠️ 07.06, Project 07 | `langgraph dev` runs inside the runtime; opening it in **Studio** needs your PC ([Studio](#studio)) |
| 08 LangGraph production features | ✅ | |
| 09 Multi-agent systems | ✅ | |
| 10 Testing, evaluation & observability | ✅ | Run `pytest` as `!python -m pytest ...` |
| 11 Deep agents | ⚠️ 11.09 | 11.09's 🐳 cells need [Docker](#docker); its in-process and Daytona parts run. Lab 11B needs Docker |
| 12 Production & deployment | ⚠️ 12.04, 12.05, 12.07, 12.08, 12.09 / ❌ 12.06 | **12.06 Docker & Compose** needs your PC. 12.04 Part 10 (calling the server from your browser), 12.05's [Postgres](#postgres) cells, 12.07's Docker stack, 12.08's Studio and 12.09's deploy steps run from your PC |
| 13 Multimodal & voice | ✅ | Work with audio files (no microphone needed) |
| 14 Local models & fine-tuning | ❌ 14.01 / ⚠️ 14.02–14.04, Project 14 | **14.01 Ollama** needs your PC ([Ollama](#ollama)). 14.04's training notebook (`colab/colab-qlora-router.ipynb`) is *made* for Colab (T4 GPU); serving the result with Ollama is on your PC |
| 15 Decision models with Jev | ✅ | |

<a id="pc"></a>
## Your PC or the devcontainer

- **Your PC:** follow [00-02-create-course-env.md](../modules/00-foundations/00-02-create-course-env.md) (conda env `lc-mastery`, `pip install -e ".[dev]"`, the `Python (lc-mastery)` kernel). Check it with Lesson 00.02.
- **Devcontainer (no local Python):** open the repo in **GitHub Codespaces** or **VS Code → Dev Containers: Reopen in Container**. `.devcontainer/devcontainer.json` installs the same stack with the tested pins and registers the `Python (lc-mastery)` kernel. Docker lessons need Docker *inside* the container: in Codespaces, add the [docker-in-docker feature](https://github.com/devcontainers/features/tree/main/src/docker-in-docker); with VS Code locally, Docker Desktop is already there.

Your Drive clone and your PC clone are separate git clones of the same course. Keep your own work in `workspace/` ([setup/LEARNER_WORKFLOW.md](../setup/LEARNER_WORKFLOW.md)) and both stay easy to update.

<a id="docker"></a>
### Docker (11.09, Lab 11B, 12.05–12.07, the pgvector stretch)

1. Install **Docker Desktop**: [Windows](https://docs.docker.com/desktop/setup/install/windows-install/) (WSL 2 backend), [macOS](https://docs.docker.com/desktop/setup/install/mac-install/), or **Docker Engine** on [Linux](https://docs.docker.com/engine/install/).
2. Start Docker Desktop and wait for *Engine running*.
3. Verify in a terminal:
   ```bash
   docker --version
   docker run --rm hello-world
   docker compose version
   ```
   `hello-world` prints *Hello from Docker!* If you see *cannot connect to the Docker daemon*, Docker Desktop isn't running yet.
4. Restart Jupyter's kernel and run the lesson again: the `HAVE_DOCKER` check turns ✅ and the 🐳 cells run.

Colab has no Docker and can't get it (no privileged containers). For 11.09, the **Daytona** cloud sandbox is the no-Docker option: add `DAYTONA_API_KEY` as a secret and run that part on Colab.

<a id="postgres"></a>
### Postgres (12.05)

12.05 starts Postgres with Docker: set up [Docker](#docker) first, then follow the lesson's `docker run ... postgres` line and check it with `docker ps` (the container shows *Up*). The SQLite parts of the lesson run anywhere, Colab included. A hosted Postgres (for example a free Neon database) also works from Colab: put `M12_POSTGRES_URL=<its connection URL>` in a `.env` file in your Drive clone (see the note on other settings [above](#secrets)).

<a id="ollama"></a>
### Ollama (14.01–14.04, Project 14)

1. Install from [ollama.com/download](https://ollama.com/download) ([Windows](https://docs.ollama.com/windows), macOS, Linux).
2. Verify:
   ```bash
   ollama --version
   ollama pull qwen3:0.6b    # or the model the lesson names
   ollama run qwen3:0.6b "Say hi in five words"
   curl http://127.0.0.1:11434/api/version
   ```
3. Run the lesson: `HAVE_OLLAMA` turns ✅.

**Optional, on Colab:** you *can* run Ollama inside a Colab runtime (`!curl -fsSL https://ollama.com/install.sh | sh`, then start `ollama serve` in the background with `subprocess.Popen`, then `ollama pull`). It is slow on CPU, and the install disappears with the runtime, so the course treats Ollama lessons as PC lessons.

<a id="studio"></a>
### LangSmith Studio and `langgraph dev` (02.07, 07.06, Project 07, 12.08)

Studio is a web page (smith.langchain.com) that connects to a `langgraph dev` server at `127.0.0.1:2024` **on your own computer**. On your PC: install the extra (`python -m pip install -e ".[studio]"`), run `langgraph dev` from the app folder the lesson names, and open the Studio link it prints (use Chrome or Edge; Safari blocks localhost by default).

On Colab, the lessons' **Step 0** installs the CLI and the server cells run inside the runtime, so the code parts work. Only the Studio page can't reach that server. **Optional workaround:** `langgraph dev --tunnel` publishes the server through a temporary Cloudflare tunnel URL that Studio can open; it is a beta feature, the URL is public while it runs, so stop it when you are done.

<a id="update"></a>
## Updating, and troubleshooting

| Symptom | Fix |
|---|---|
| A lesson says **"Could not find the course repo ... run colab/START_HERE.ipynb first"** | Run START_HERE (once per account), or check the clone is in `MyDrive/langchain-langgraph-mastery`. Just ran START_HERE? Drive can take a while to show (or finish uploading) the clone in another notebook: the setup cell waits about 30 s, so if it still fails, wait a minute and run it again |
| START_HERE Step 2: **`FileNotFoundError: [Errno 2] No such file or directory: PosixPath('/content/drive/MyDrive/langchain-langgraph-mastery')`** right after *✅ Course cloned*, or *"Drive doesn't show ... after 30 seconds"* | Drive was slower to show the fresh clone than git was to finish it. START_HERE now waits up to 30 s for the clone (open its latest version with the **Open in Colab** badge) and otherwise prints what to do: wait a minute and run Step 2 again (it picks the clone up); if [My Drive](https://drive.google.com/drive/my-drive) has a `langchain-langgraph-mastery` folder without files, rename it and run Step 2 again; then **Runtime → Disconnect and delete runtime** and **Run all** |
| A lesson's setup cell: **`TypeError: prepare_runtime() got an unexpected keyword argument 'secrets'`**, or *"the course code in ... is older than this notebook"* | The runtime loaded an older copy of the course than the notebook: usually your Drive clone is older than a lesson you opened from GitHub (the badge always opens the newest version), or this runtime had already imported the course before it was updated. Don't delete `secrets=(...)` from the cell (Colab's Gemini may suggest it). Fix: run [START_HERE](https://colab.research.google.com/github/diego28e/langchain-langgraph-mastery/blob/main/colab/START_HERE.ipynb) again, which updates your Drive copy (if it says *"Could not update the course"*, see that row below), then in the lesson **Runtime → Disconnect and delete runtime** and run it again. Setup cells from 2026-11-01 on load the course from your clone (dropping an older import, reinstalling if it was installed from another folder) and, with an older clone, still run and print this fix instead of the TypeError |
| **`MessageError: Error: credential propagation was unsuccessful`** (or START_HERE's *"Google Drive did not mount"*) | Only some Drive permissions were ticked, or another account was chosen. **Runtime → Disconnect and delete runtime**, then **Run all** and, in the Google window, choose your Colab account, tick **Select all**, **Continue**. Still failing: at [myaccount.google.com/connections](https://myaccount.google.com/connections) remove **Google Drive for desktop**'s access and try again. Last resort: `USE_DRIVE = False` in START_HERE's Step 1 clones into `/content`, which works only in that runtime (deleted when it resets, and lessons, in their own runtimes, won't find it) |
| A link in a lesson (e.g. *Next: `00-05-first-groq-call.ipynb`*) opens **"Sorry, the file you have requested does not exist"** at `drive.google.com/file/u/0/d/00-05-first-groq-call.ipynb/edit` | Colab reads a relative link as a Drive file **id**, so links between notebooks can't work there (they do on your PC and GitHub). Use the **🔗 links the setup cell printed** instead: they open the Drive copies (`colab.research.google.com/drive/<id>`, read from Drive's `user.drive.id` attribute), so your work saves. If Drive doesn't expose an id, the link opens the read-only GitHub copy and says so. Or open the file [from Drive](#open-lessons), or use **File → Open notebook → Recent** |
| **"Restart once: ..."** | Runtime → Restart session, then Run all. It's asked at most once per runtime |
| **"Unrecognized runtime lc-mastery"** / Colab switches to Python 3 | Normal: the notebooks are saved with the PC kernel name. Colab's Python 3 is correct (the setup cell prints a line saying so, and the kernel checks in 00.02, 00.03, 00.05 and 02.01 print ✅ on Colab) |
| START_HERE: **"Could not update the course"** | `git pull --ff-only` refused because you changed course files. Your clone still works. To get the update: keep your work in `workspace/`, then in a cell `!git -C /content/drive/MyDrive/langchain-langgraph-mastery stash` and run START_HERE again (`git stash pop` brings your edits back) |
| pip prints dependency warnings about `google-auth`, `pandas` or other Colab packages | Expected: the course pins its own versions; Colab tools you don't use in the course may complain |
| The install happens again in every lesson | Each notebook gets its own runtime, and runtimes are recycled after a while. 1–3 min each first run is normal |
| `No module named 'mastery'` | The first code cell (Setup 1) didn't run: run the notebook from the top |
| A 🐳 / 🦙 / Studio cell prints *ℹ️ Google Colab: ... is not available* | That part needs your PC ([above](#pc)); the rest of the lesson still runs |
