# Learner workflow: get course updates without losing your work

> **Do this once, before Module 00.** About 10 minutes. Commands are for Git Bash on Windows (the same `bash` as macOS/Linux; see [CONVENTIONS.md §10](../CONVENTIONS.md#10-shells-git-bash-first)).

The course keeps improving: fixed bugs, re-verified model IDs, new lessons. If you edit the course's notebooks in place, every update you pull will conflict with your edits. The fix is a simple rule:

> **Keep the course files pristine. Do your work in copies, inside `workspace/`.**

`workspace/` is listed in `.gitignore`, so git never tracks it and `git pull` never touches it.

## 1. Get the repo

Clone it (or fork it on GitHub first if you plan to send fixes back, and clone your fork):

```bash
git clone https://github.com/diego28e/langchain-langgraph-mastery.git
cd langchain-langgraph-mastery
```

If you cloned a **fork**, also add the original course as `upstream`:

```bash
git remote add upstream https://github.com/diego28e/langchain-langgraph-mastery.git
```

## 2. Work in copies

Copy a lesson or project notebook into `workspace/`, keeping the module path, and open the copy in Jupyter:

```bash
mkdir -p workspace/03-memory-and-context/project
cp modules/03-memory-and-context/project/03-project-study-buddy.ipynb workspace/03-memory-and-context/project/
```

The setup cell finds the repo root by walking up from the notebook's folder, so copies inside `workspace/` still load the course package, `.env` and `data/`. Relative links in a copy's Markdown may point to the wrong place: read along in the original if one breaks. Do the same for your logs: copy `docs/research-log.md` and `docs/decision-log.md` into `workspace/` and write your entries there.

**Want your work versioned?** Make `workspace/` its own git repository (`cd workspace && git init`), or keep a private notes repo next to the course. Either way, your history stays separate from the course's.

## 3. Get course updates

From the repo root, with nothing changed in the course files (`git status` shows a clean tree):

```bash
git pull --ff-only
```

If you work from a fork:

```bash
git fetch upstream
git merge --ff-only upstream/main
```

Then reinstall, in case the course added or upgraded a package (fast when nothing changed):

```bash
python -m pip install -e ".[dev]"
```

Read [COURSE_CHANGELOG.md](../COURSE_CHANGELOG.md) to see what changed, and compare an updated lesson with your copy in `workspace/` if you want the fix in your version.

## If git refuses to pull

`git pull --ff-only` stops when you edited a tracked file. Move your edits out of the way, then pull:

```bash
git status                                  # see which course files you changed
git stash                                   # put your edits aside (git stash pop brings them back)
git pull --ff-only
```

Then copy the notebook you were working on into `workspace/` and continue there. Don't run `git checkout -- <file>` or `git reset --hard` unless you are sure you don't need your edits: both throw them away.
