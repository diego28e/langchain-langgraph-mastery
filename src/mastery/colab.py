"""Google Colab support: find the course clone, install the course into the runtime, load Colab Secrets.

Introduced with ``colab/START_HERE.ipynb`` (docs/COLAB.md). Every lesson's setup cell calls
:func:`prepare_runtime` when it runs on Colab; on your PC nothing here runs.

Why this module exists:
    Colab gives each notebook its own fresh runtime, so packages installed for one lesson are gone in the
    next. :func:`prepare_runtime` installs the course (``pip install -e ".[colab]"`` with
    ``constraints/colab-2026-10.txt``) once per runtime, then loads your Colab Secrets into ``os.environ``
    (:func:`mastery.config.load_colab_secrets`), so a lesson runs the same way it does on your PC.

It imports only the standard library at module level: the setup cell imports it before the course's
dependencies are installed.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata as metadata
import os
import re
import shutil
import subprocess
import sys
import time
import warnings
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

__all__ = [
    "API_LEVEL",
    "COLAB_CONSTRAINTS",
    "COLAB_DOCS_URL",
    "COLAB_EXTRA",
    "COLAB_REPO_DIRS",
    "DRIVE_MYDRIVE",
    "REPO_NAME",
    "REPO_URL",
    "RestartRequired",
    "colab_note",
    "colab_repo_root",
    "in_colab",
    "drive_file_id",
    "drive_folder_url",
    "install_command",
    "installed_root",
    "lesson_links",
    "notebook_source",
    "prepare_runtime",
    "show_lesson_links",
    "wait_for_path",
]

# The setup-cell API this module offers. Each lesson's setup cell checks it before calling prepare_runtime and
# falls back (with a clear fix) when Colab loaded an older copy of the course. Raise it whenever setup cells
# start passing a new prepare_runtime argument, then run _maintainer/tools/qa/colab_patch.py.
#   1: prepare_runtime(repo_root)   2: + secrets= and notebook=   3: + checks where the course is installed from
API_LEVEL = 3
REPO_NAME = "langchain-langgraph-mastery"
DRIVE_MYDRIVE = Path("/content/drive/MyDrive")
# Where colab/START_HERE.ipynb puts the clone: Drive (kept between sessions) first, then /content (temporary).
COLAB_REPO_DIRS = (DRIVE_MYDRIVE / REPO_NAME, Path("/content") / REPO_NAME)
COLAB_EXTRA = "colab"
# Optional extras a lesson's Step 0 may already have put in the runtime: install them at the tested versions too.
_OPTIONAL_EXTRAS = {"studio": "langgraph-api", "embeddings": "fastembed"}
COLAB_CONSTRAINTS = "constraints/colab-2026-10.txt"
# /tmp lives as long as the runtime (it survives "Restart session"), so the install runs once per runtime.
_STAMP_DIR = Path("/tmp")
REPO_URL = "https://github.com/diego28e/langchain-langgraph-mastery"
COLAB_DOCS_URL = f"{REPO_URL}/blob/main/docs/COLAB.md"

Runner = Callable[[Sequence[str]], int]


class RestartRequired(RuntimeError):
    """The install upgraded a package this kernel had already imported: restart once, then run again."""


def in_colab() -> bool:
    """Return ``True`` inside a Google Colab runtime (also in a subprocess started from one)."""
    return "google.colab" in sys.modules or "COLAB_RELEASE_TAG" in os.environ


# Drive (FUSE) can take a few seconds to show files another process (git, or START_HERE's runtime) just wrote.
DRIVE_LAG_SECONDS = 30


def wait_for_path(path: str | Path, seconds: float = DRIVE_LAG_SECONDS, *, interval: float = 1.0) -> bool:
    """Wait up to ``seconds`` for ``path`` to exist (Drive lag); ``True`` as soon as it does. Never raises."""
    path = Path(path)
    for _ in range(max(0, round(seconds / interval))):
        if path.exists():
            return True
        try:
            os.listdir(path.parent)  # Re-read the folder from Drive.
        except OSError:
            pass
        time.sleep(interval)
    return path.exists()


def _is_clone(folder: Path) -> bool:
    return (folder / "pyproject.toml").is_file() and (folder / "src" / "mastery").is_dir()


def colab_repo_root(wait: float = 0) -> Path | None:
    """The clone made by ``colab/START_HERE.ipynb`` (Drive first, then /content), or ``None``.

    ``wait``: seconds to keep looking while Drive catches up (a fresh mount, or a clone still uploading).
    """
    for attempt in range(max(0, round(wait)) + 1):
        for folder in COLAB_REPO_DIRS:
            if _is_clone(folder):
                return folder
        if attempt < round(wait):
            time.sleep(1)
    return None


CLONE_MISSING = (
    "The course clone at {root} has no {missing} (yet). If you just ran colab/START_HERE.ipynb, Drive may still be"
    " showing or uploading it: wait a minute, then run this cell again. Otherwise run START_HERE again ({docs})."
)


def notebook_source(timeout: float = 1.0) -> str:
    """Where Colab opened this notebook from: ``"drive"``, ``"github"``, ``"other"``, or ``""`` (unknown).

    A heuristic: Colab's local Jupyter server lists the session with a ``fileId=...`` path, a Drive file id
    for a notebook opened from Drive and a GitHub address otherwise. Any error means ``""`` (no tip shown).
    """
    try:
        import json
        import socket
        import urllib.request
        from urllib.parse import unquote

        host = socket.gethostbyname(socket.gethostname())
        with urllib.request.urlopen(f"http://{host}:9000/api/sessions", timeout=timeout) as response:  # noqa: S310
            sessions = json.load(response)
        path = unquote(str(sessions[0].get("path", "")))
    except Exception:  # noqa: BLE001 (not Colab, no session, an internal change: just don't guess)
        return ""
    file_id = path.split("=", 1)[1] if path.startswith("fileId=") else path
    if "github" in file_id.lower():
        return "github"
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", file_id):
        return "drive"
    return "other" if file_id else ""


_DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{10,}")


def drive_file_id(path: str | Path) -> str | None:
    """The Drive id of a file or folder on Colab's Drive mount, or ``None`` (not on Drive, or not exposed).

    Colab's Drive mount (drivefs) exposes it as the extended attribute ``user.drive.id``: read it with
    ``os.getxattr``, else the ``xattr`` / ``getfattr`` tools (UNVERIFIED on every runtime: any failure is ``None``).
    """
    path = str(path)
    readers: list[Callable[[], object]] = [lambda: os.getxattr(path, "user.drive.id")]
    tools = (("xattr", ["-p", "user.drive.id", path]), ("getfattr", ["--only-values", "-n", "user.drive.id", path]))
    for tool, args in tools:
        exe = shutil.which(tool)
        if exe:
            readers.append(lambda exe=exe, args=args: subprocess.run(
                [exe, *args], capture_output=True, timeout=5, check=True).stdout)
    for read in readers:
        try:
            value = read()
        except (AttributeError, OSError, ValueError, subprocess.SubprocessError):
            continue
        text = (value.decode(errors="replace") if isinstance(value, bytes) else str(value)).strip().strip("\x00")
        if _DRIVE_ID.fullmatch(text):
            return text
    return None


def drive_folder_url(folder: str | Path) -> str:
    """A clickable Drive link for a folder of the mounted Drive (its own page if Colab exposes its id)."""
    folder_id = drive_file_id(folder)
    return f"https://drive.google.com/drive/folders/{folder_id}" if folder_id else "https://drive.google.com/drive/my-drive"


# A Markdown link to another file of the course: [text](relative/path.ipynb#anchor). Not http(s) links.
_MD_LINK = re.compile(r"\[([^\]]+)\]\((?!https?:|#)([^)\s#]+\.(?:ipynb|md))(#[^)\s]*)?\)")


def _label(text: str) -> str:
    return re.sub(r"[`*_]|!\[[^\]]*\]", "", text).strip() or text


def lesson_links(repo_root: str | Path, notebook: str | Path) -> list[tuple[str, str, bool]]:
    """``(label, url, saves)`` for each course file this notebook's Markdown links to, in order.

    On Colab a relative link such as ``(00-05-first-groq-call.ipynb)`` opens as a Drive file *id* and lands
    on "file missing", so each target gets a real URL instead: its Drive copy
    (``colab.research.google.com/drive/<id>`` for a notebook, Drive's viewer for a ``.md``) when the
    clone is on Drive, otherwise the GitHub copy. ``saves`` is False only for a notebook's GitHub copy
    (edits there are not saved). Notebooks come first.

    Args:
        repo_root: The course clone.
        notebook: The notebook, relative to ``repo_root`` (``modules/...``) or just its file name.
    """
    root = Path(repo_root)
    path = root / notebook
    if not path.is_file():
        path = next((p for p in sorted((root / "modules").rglob(Path(notebook).name))
                     if ".ipynb_checkpoints" not in p.parts), path)
    try:
        import json

        cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    except (OSError, ValueError, KeyError):
        return []
    text = "\n".join("".join(c.get("source", "")) for c in cells if c.get("cell_type") == "markdown")
    targets = _MD_LINK.findall(text)
    lessons = sorted(p.name for p in path.parent.glob("[0-9][0-9]-[0-9][0-9]-*.ipynb"))
    if path.name in lessons and lessons.index(path.name) > 0:  # Lessons link forward only: add the previous one.
        previous = lessons[lessons.index(path.name) - 1]
        targets.insert(0, (f"Previous lesson: {previous}", previous, ""))
    links: list[tuple[str, str, bool]] = []
    seen: set[Path] = set()
    for label, target, anchor in targets:
        file = (path.parent / target).resolve()
        if file in seen or not file.is_file() or not file.is_relative_to(root.resolve()):
            continue
        seen.add(file)
        rel = file.relative_to(root.resolve()).as_posix()
        file_id = drive_file_id(file)
        if file_id:
            url = (f"https://colab.research.google.com/drive/{file_id}{anchor}" if rel.endswith(".ipynb")
                   else f"https://drive.google.com/file/d/{file_id}/view")
        elif rel.endswith(".ipynb"):
            url = f"https://colab.research.google.com/github/{REPO_URL.split('github.com/')[1]}/blob/main/{rel}{anchor}"
        else:
            url = f"{REPO_URL}/blob/main/{rel}{anchor}"
        name, text = rel.rsplit("/", 1)[-1], _label(label)
        following = lessons[lessons.index(path.name) + 1:][:1] if path.name in lessons else []
        if file.parent == path.parent.resolve() and name in following:
            text = f"Next lesson: {text}"
        links.append((text if name in text else f"{text} ({name})", url, bool(file_id) or not rel.endswith(".ipynb")))
    return sorted(links, key=lambda link: ".ipynb" not in link[1] and "/drive/" not in link[1])  # Notebooks first.


def show_lesson_links(repo_root: str | Path, notebook: str | Path) -> int:
    """Print clickable links for this notebook's links to other course files (see :func:`lesson_links`).

    Returns how many links were shown. Never raises: a navigation aid must not break the setup cell.
    """
    try:
        links = lesson_links(repo_root, notebook)
    except Exception:  # noqa: BLE001 - never break the setup cell over links.
        return 0
    if not links:
        return 0
    head = "🔗 On Colab, open other lessons with these links (the Markdown links in this notebook only work on PC/GitHub):"
    readonly = " (GitHub copy: edits won't be saved)"
    try:
        from html import escape

        from IPython.display import HTML, display

        items = "".join(f'<li><a href="{escape(url)}" target="_blank">{escape(label)}</a>{"" if saves else readonly}'
                        "</li>" for label, url, saves in links)
        display(HTML(f"<p>{escape(head)}</p><ul>{items}</ul>"))
    except Exception:  # noqa: BLE001 - no IPython: plain text links (Colab makes them clickable too).
        print(head)
        for label, url, saves in links:
            print(f"   {label}: {url}{'' if saves else readonly}")
    return len(links)


def colab_note(feature: str, anchor: str = "") -> str:
    """One line for a skip message when a lesson needs something a Colab runtime lacks (Docker, Ollama...)."""
    where = f"{COLAB_DOCS_URL}#{anchor}" if anchor else COLAB_DOCS_URL
    return f"ℹ️ Google Colab: {feature} is not available in a Colab runtime, so these cells skip here. Run them on your PC or in the devcontainer: {where}"


def install_command(repo_root: str | Path, *, extras: str = COLAB_EXTRA, use_uv: bool | None = None) -> list[str]:
    """The install command for this runtime: uv when Colab has it (faster), otherwise pip."""
    root = Path(repo_root)
    target = f"{root}[{extras}]" if extras else str(root)
    args = ["install", "--quiet", "-e", target, "-c", str(root / COLAB_CONSTRAINTS)]
    uv = shutil.which("uv") if use_uv is None or use_uv else None
    if uv:
        return [uv, "pip", *args[:1], "--python", sys.executable, *args[1:]]  # Exactly this kernel's Python.
    return [sys.executable, "-m", "pip", *args]


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _versions() -> dict[str, str]:
    return {_normalize(d.metadata["Name"] or ""): d.version for d in metadata.distributions()}


def _loaded_modules(distributions: Sequence[str]) -> list[str]:
    """Modules already imported in this process that belong to ``distributions``."""
    loaded: list[str] = []
    for name in distributions:
        try:
            files = metadata.distribution(name).files or []
        except metadata.PackageNotFoundError:
            continue
        for file in files:
            parts = Path(str(file)).with_suffix("").parts
            if not str(file).endswith(".py") or ".." in parts or parts[0].endswith((".dist-info", ".data")):
                continue
            module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
            if module in sys.modules:
                loaded.append(module)
                break
    return loaded


def _same_version(a: str, b: str) -> bool:
    """``2026.07.22`` == ``2026.7.22``; local tags (``+cu121``) are ignored."""
    def parts(v: str) -> list[object]:
        return [int(x) if x.isdigit() else x for x in re.findall(r"\d+|[a-z]+", v.split("+")[0].lower())]

    return parts(a) == parts(b)


def _outdated_imports() -> list[str]:
    """Imported packages whose installed version is no longer the one in memory (a %pip upgraded them)."""
    try:
        owners = metadata.packages_distributions()
    except Exception:  # noqa: BLE001
        return []
    outdated: list[str] = []
    for name, module in list(sys.modules.items()):
        if "." in name or len(owners.get(name, ())) != 1:
            continue
        with warnings.catch_warnings():  # Some packages deprecate __version__ (jsonschema, markupsafe).
            warnings.simplefilter("ignore")
            loaded = getattr(module, "__version__", None)
        if not isinstance(loaded, str):
            continue
        try:
            installed = metadata.version(owners[name][0])
        except metadata.PackageNotFoundError:
            continue
        if not _same_version(installed, loaded):
            outdated.append(f"{name} {loaded} (installed: {installed})")
    return sorted(outdated)


def installed_root() -> Path | None:
    """The folder the ``mastery`` distribution was installed from (``pip install -e``), or ``None``.

    Read from its PEP 610 ``direct_url.json``; ``None`` when mastery isn't installed or wasn't installed from a folder.
    """
    import json
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    try:
        text = metadata.distribution("mastery").read_text("direct_url.json")
        url = urlparse(json.loads(text or "{}").get("url", ""))
    except (metadata.PackageNotFoundError, ValueError, AttributeError, OSError):
        return None
    if url.scheme != "file" or not url.path:
        return None
    netloc = f"//{url.netloc}" if url.netloc not in ("", "localhost") else ""
    return Path(url2pathname(netloc + url.path)).resolve()  # file:///C:/x is C:\x on Windows


def _default_runner(command: Sequence[str]) -> int:
    return subprocess.run(list(command), check=False).returncode


def _stamp(root: Path, extras: str) -> Path:
    digest = hashlib.sha256()
    for name in ("pyproject.toml", COLAB_CONSTRAINTS):
        path = root / name
        digest.update(path.read_bytes() if path.is_file() else b"")
    digest.update(f"{root}|{extras}".encode())
    return _STAMP_DIR / f"lc-mastery-colab-{digest.hexdigest()[:12]}.ok"


def _extras_for(versions: dict[str, str]) -> str:
    return ",".join([COLAB_EXTRA, *(extra for extra, dist in _OPTIONAL_EXTRAS.items() if dist in versions)])


# Colab reads the PC kernel name saved in each notebook (lc-mastery), can't find it, and falls back to Python 3.
RUNTIME_NOTE = (
    "ℹ️ Colab: Python 3 is the right runtime here. The 'Unrecognized runtime lc-mastery' notice when"
    " opening a notebook is expected (it's the PC kernel name)."
)
GITHUB_TIP = f"💡 Opened from GitHub: your edits won't be saved; open it from Drive (see {COLAB_DOCS_URL}#open-lessons)."


def prepare_runtime(
    repo_root: str | Path,
    *,
    extras: str | None = None,
    runner: Runner | None = None,
    load_secrets: bool = True,
    force: bool = False,
    secrets: Iterable[str] | None = None,
    notebook: str | None = None,
) -> list[str]:
    """Install the course into this Colab runtime (once) and load Colab Secrets. No-op outside Colab.

    Args:
        repo_root: The course clone (the setup cell's ``REPO_ROOT``).
        extras: Which extras to install. By default ``"colab"`` (``[dev]`` without ``[studio]``), plus
            ``studio`` / ``embeddings`` when the lesson's Step 0 already installed langgraph-api / fastembed.
        runner: Runs the install command and returns its exit code (tests pass a fake).
        load_secrets: Also copy Colab Secrets into ``os.environ`` (never overwriting a set variable).
        force: Install even if this runtime already did.
        secrets: The Colab Secrets this notebook uses (its setup cell lists them). Only those are read now,
            so Colab asks for access to those alone; ``require_env`` reads any other one when a cell needs it.
            ``None`` reads every name in :data:`mastery.config.COLAB_SECRET_NAMES`.
        notebook: This notebook's file name (its setup cell passes it): prints Colab-friendly links to the
            files its Markdown links to, because relative links don't open on Colab (:func:`show_lesson_links`).

    Returns:
        The names of the secrets that were loaded (never their values).

    Raises:
        RestartRequired: The install changed a package this kernel had already imported. Restart the
            session once (Runtime → Restart session) and run the notebook again: the install is skipped.
        RuntimeError: The install failed (the pip output above says why).
        FileNotFoundError: ``repo_root`` still has no pyproject.toml or src/mastery after
            :data:`DRIVE_LAG_SECONDS` (a clone Drive doesn't show yet); the message says what to do.
    """
    if not in_colab():
        return []
    root = Path(repo_root)
    for missing in ("pyproject.toml", "src/mastery"):
        if not wait_for_path(root / missing):  # Drive lag: never a pip or subprocess traceback.
            raise FileNotFoundError(CLONE_MISSING.format(root=root, missing=missing, docs=COLAB_DOCS_URL))
    print(RUNTIME_NOTE)
    if notebook_source() in ("github", "other"):
        print(GITHUB_TIP)
    if notebook:
        show_lesson_links(repo_root, notebook)
    root = Path(repo_root).resolve()
    src = str(root / "src")
    if sys.path[:1] != [src]:  # This clone's code first, even if an older setup cell called us.
        sys.path[:] = [src, *(p for p in sys.path if p != src)]
    before = _versions()
    extras = extras or _extras_for(before)
    stamp = _stamp(root, extras)
    elsewhere = installed_root()
    if elsewhere is not None and elsewhere != root:  # e.g. a /content clone, or a renamed Drive folder.
        print(f"ℹ️ Colab: the course was installed from {elsewhere}; reinstalling it from {root}.")
        force = True
    if force or not stamp.exists():
        print(f"⏳ Colab: installing the course [{extras}] into this runtime (once per runtime, 1-3 minutes)...")
        run = runner or _default_runner
        command = install_command(root, extras=extras)
        code = run(command)
        if code != 0 and Path(command[0]).name.startswith("uv"):
            code = run(install_command(root, extras=extras, use_uv=False))  # uv failed: plain pip.
        if code != 0:
            raise RuntimeError(f"Installing the course failed (exit code {code}); see the pip output above.")
        try:
            stamp.write_text("ok\n", encoding="utf-8")
        except OSError:
            pass
        importlib.invalidate_caches()  # see the packages that were just installed
        after = _versions()
        changed = sorted(name for name, version in after.items() if before.get(name, version) != version)
        stale = _loaded_modules(changed)
        print(f"✅ Colab: course installed ({len(changed)} preinstalled packages changed version).")
        if stale:
            raise RestartRequired(
                "Restart once: this kernel had already imported "
                + ", ".join(sorted(stale)[:5])
                + ", which the install just upgraded. Runtime → Restart session, then Runtime → Run all"
                " (the install is skipped the second time)."
            )
    outdated = _outdated_imports()
    asked = stamp.with_suffix(".restart")
    if outdated and not asked.exists():  # Step 0's %pip upgraded something already imported; ask only once.
        try:
            asked.write_text("asked\n", encoding="utf-8")
        except OSError:
            pass
        raise RestartRequired(
            "Restart once: " + ", ".join(outdated[:5]) + " is still the old version in memory."
            " Runtime → Restart session, then Runtime → Run all."
        )
    if outdated:
        print("⚠️ Colab: still old in memory:", ", ".join(outdated[:5]), "(Runtime → Restart session fixes it).")
    from mastery.config import load_colab_secrets, use_colab_secrets

    if secrets is not None:
        use_colab_secrets(secrets)
    if not load_secrets:
        return []
    return load_colab_secrets()
