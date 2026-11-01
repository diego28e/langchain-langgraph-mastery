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
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path

__all__ = [
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
    "install_command",
    "prepare_runtime",
]

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


def colab_repo_root() -> Path | None:
    """The clone made by ``colab/START_HERE.ipynb`` (Drive first, then /content), or ``None``."""
    for folder in COLAB_REPO_DIRS:
        if (folder / "pyproject.toml").is_file() and (folder / "src" / "mastery").is_dir():
            return folder
    return None


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


def prepare_runtime(
    repo_root: str | Path,
    *,
    extras: str | None = None,
    runner: Runner | None = None,
    load_secrets: bool = True,
    force: bool = False,
) -> list[str]:
    """Install the course into this Colab runtime (once) and load Colab Secrets. No-op outside Colab.

    Args:
        repo_root: The course clone (the setup cell's ``REPO_ROOT``).
        extras: Which extras to install. By default ``"colab"`` (``[dev]`` without ``[studio]``), plus
            ``studio`` / ``embeddings`` when the lesson's Step 0 already installed langgraph-api / fastembed.
        runner: Runs the install command and returns its exit code (tests pass a fake).
        load_secrets: Also copy Colab Secrets into ``os.environ`` (never overwriting a set variable).
        force: Install even if this runtime already did.

    Returns:
        The names of the secrets that were loaded (never their values).

    Raises:
        RestartRequired: The install changed a package this kernel had already imported. Restart the
            session once (Runtime → Restart session) and run the notebook again: the install is skipped.
        RuntimeError: The install failed (the pip output above says why).
    """
    if not in_colab():
        return []
    root = Path(repo_root).resolve()
    before = _versions()
    extras = extras or _extras_for(before)
    stamp = _stamp(root, extras)
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
    if not load_secrets:
        return []
    from mastery.config import load_colab_secrets

    return load_colab_secrets()
