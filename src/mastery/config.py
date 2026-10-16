"""Configuration helpers: load ``.env``, validate keys, fail with friendly errors.

Introduced in Module 00, Lesson 00.04 ("Secrets and .env hygiene").
Extended in Module 01, Lesson 01.01: vision and paid-benchmark model settings,
read by ``mastery.models``.

Why this module exists:
    Every notebook in the course needs the same three things before it can call
    a model: (1) find and load the ``.env`` file, (2) check that the keys it
    needs are present, and (3) read course-wide settings such as model IDs.
    Doing this in one tested place means notebooks stay short and every
    "missing key" problem produces the same clear, actionable message.

Security rules this module enforces:
    - It never returns or prints a secret value. ``require_env`` only raises or
      returns ``None``; ``env_status`` and ``mask_secret`` show a short prefix and
      the length, never the full value.
    - It never overrides variables that are already set in your environment
      unless you ask for it (``override=True``). The real environment wins,
      which is the twelve-factor convention (https://12factor.net/config).
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from mastery.doctor import require_valid_ssl_env

__all__ = [
    "REPO_ROOT_ENV",
    "package_repo_root",
    "DEFAULT_BENCHMARK_MODEL",
    "DEFAULT_BENCHMARK_MODEL_STRONG",
    "DEFAULT_MODEL_FAST",
    "DEFAULT_MODEL_REASONING",
    "DEFAULT_MODEL_VISION",
    "KEY_HELP_URLS",
    "MissingSettingError",
    "Settings",
    "env_status",
    "find_repo_root",
    "get_setting",
    "is_set",
    "load_env",
    "load_settings",
    "mask_secret",
    "require_env",
]

# --- Course defaults ---------------------------------------------------------
# These are fallbacks only. The real values come from `.env` (MASTERY_MODEL_*),
# so you can switch models without touching code.
# VERIFIED 2026-10-11: both are Groq *production* models
# (https://console.groq.com/docs/models). Re-check at every research checkpoint.
DEFAULT_MODEL_FAST = "openai/gpt-oss-20b"
DEFAULT_MODEL_REASONING = "openai/gpt-oss-120b"
# VERIFIED 2026-10-11: qwen/qwen3.8-27b is Groq's only vision model and it is a
# PREVIEW model (evaluation only, may be retired at short notice).
# https://console.groq.com/docs/vision
DEFAULT_MODEL_VISION = "qwen/qwen3.8-27b"
# Paid benchmark, as "provider:model" strings (docs/paid-benchmark-openai-vs-gemini.md).
# VERIFIED 2026-10-11: https://developers.openai.com/api/docs/models
DEFAULT_BENCHMARK_MODEL = "openai:gpt-6-luna"
DEFAULT_BENCHMARK_MODEL_STRONG = "openai:gpt-6.1-sol"
DEFAULT_LANGSMITH_PROJECT = "langchain-langgraph-mastery"

# Where to create each key. Shown in error messages so the fix is one click away.
KEY_HELP_URLS: dict[str, str] = {
    "GROQ_API_KEY": "https://console.groq.com/keys",
    "LANGSMITH_API_KEY": "https://smith.langchain.com/",
    "OPENAI_API_KEY": "https://developers.openai.com/api/docs/quickstart",
    "GOOGLE_API_KEY": "https://ai.google.dev/gemini-api/docs/api-key",
    "TAVILY_API_KEY": "https://docs.tavily.com/documentation/api-credits",
    "HF_TOKEN": "https://huggingface.co/docs/inference-providers/index",
}

# Values people paste by accident from tutorials. Treated as "not set".
# WHY so specific: a real key is random text, so we only match obvious
# tutorial placeholders, never short substrings a real key could contain.
_PLACEHOLDER_MARKERS = ("your-api-key", "your_api_key", "your-groq-api-key", "your api key")
_PLACEHOLDER_VALUES = {"changeme", "change-me", "...", "todo"}

# Files that only exist at the root of this repository.
_REPO_MARKERS = ("pyproject.toml", "COURSE_OUTLINE.md")

# Optional override: point it at your clone when you start Jupyter or a script from
# somewhere else (for example an IDE that opens kernels in your home folder).
REPO_ROOT_ENV = "LC_MASTERY_ROOT"


def _is_repo_root(folder: Path) -> bool:
    return all((folder / marker).is_file() for marker in _REPO_MARKERS)


class MissingSettingError(RuntimeError):
    """Raised when required environment variables are missing or empty.

    The message is written for a learner: it lists the missing names, says
    which ``.env`` file was loaded (if any), and links to where each key is
    created. It never contains secret values.

    Attributes:
        missing: Names of the variables that are missing.
        dotenv_path: The ``.env`` file that was loaded, or ``None``.
    """

    def __init__(self, missing: Iterable[str], dotenv_path: Path | None = None) -> None:
        self.missing: tuple[str, ...] = tuple(missing)
        self.dotenv_path = dotenv_path
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        lines = [f"Missing required setting(s): {', '.join(self.missing)}."]
        if self.dotenv_path is None:
            lines.append(
                "No .env file was found. In Git Bash, from the repo root, run:  "
                "cp .env.example .env   then open .env and paste your key(s)."
            )
        else:
            lines.append(f"Loaded .env from: {self.dotenv_path}")
            lines.append("Open that file and make sure each line looks like  NAME=value  (no quotes needed).")
        for name in self.missing:
            if name in KEY_HELP_URLS:
                lines.append(f"  - Create {name} at {KEY_HELP_URLS[name]}")
        lines.append("Then restart the kernel (Kernel -> Restart Kernel...) and run the notebook again.")
        return "\n".join(lines)


def find_repo_root(start: str | Path | None = None) -> Path:
    """Return the course repository root by walking up from ``start``.

    Jupyter starts each kernel in the notebook's own folder (for example
    ``modules/00-foundations``), but ``.env``, ``data/`` and ``src/`` live at
    the repo root. This function finds that root no matter where you start.

    If the ``LC_MASTERY_ROOT`` environment variable is set (and ``start`` is
    not given), that folder wins: use it when you launch from outside the clone.
    No machine-specific path is ever hardcoded.

    Args:
        start: Folder to start from. Defaults to the current working directory.

    Returns:
        The first folder (``start`` or one of its parents) that contains both
        ``pyproject.toml`` and ``COURSE_OUTLINE.md``.

    Raises:
        FileNotFoundError: If no such folder exists above ``start``, or
            ``LC_MASTERY_ROOT`` points to a folder that is not the course repo.
    """
    override = os.environ.get(REPO_ROOT_ENV, "").strip()
    if start is None and override:
        root = Path(override).expanduser().resolve()
        if not _is_repo_root(root):
            raise FileNotFoundError(
                f"{REPO_ROOT_ENV}={override} is not the course repository "
                "(no pyproject.toml + COURSE_OUTLINE.md there). Fix or unset it."
            )
        return root
    here = Path(start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if _is_repo_root(folder):
            return folder
    raise FileNotFoundError(
        f"Could not find the course repository root above {here}. "
        "Start Jupyter from inside your clone of langchain-langgraph-mastery."
    )


def package_repo_root() -> Path:
    """Repo root for code that ships inside ``mastery`` (MCP servers, sample data).

    With the editable install from this clone (``pip install -e ".[dev]"``) the
    package sits in ``<repo>/src/mastery``, so the root is two folders up. If the
    package was installed some other way, fall back to :func:`find_repo_root`
    (``LC_MASTERY_ROOT`` or the current folder's parents).
    """
    guess = Path(__file__).resolve().parents[2]
    if os.environ.get(REPO_ROOT_ENV, "").strip():
        return find_repo_root()
    return guess if _is_repo_root(guess) else find_repo_root()


def load_env(dotenv_path: str | Path | None = None, *, override: bool = False) -> Path | None:
    """Load variables from a ``.env`` file into ``os.environ``.

    Args:
        dotenv_path: Explicit file to load. When omitted, python-dotenv's
            ``find_dotenv(usecwd=True)`` searches the current working directory
            and then each parent folder, so a notebook in ``modules/00-foundations``
            finds the ``.env`` at the repo root.
        override: If ``False`` (default), variables already set in the real
            environment win over values in the file. Set ``True`` only when you
            deliberately want the file to replace them (for example after
            editing ``.env`` without restarting the kernel).

    Returns:
        The path of the file that was loaded, or ``None`` if no file was found.
        A missing file is not an error: in CI or production the variables come
        from the real environment instead.

    In Jupyter it also installs a friendly message for Groq rate-limit errors (429), see
    :func:`mastery.models.install_notebook_error_hints`.
    """
    try:  # Never let the hint machinery break loading .env.
        from mastery.models import install_notebook_error_hints

        install_notebook_error_hints()
    except Exception:  # noqa: BLE001
        pass
    if dotenv_path is None:
        # WHY usecwd=True: without it, python-dotenv starts searching from the
        # folder of the *calling .py file* (here: src/mastery/), which is wrong
        # if the package is ever installed outside the repo. The kernel's
        # working directory is what the learner expects.
        found = find_dotenv(usecwd=True)
        if not found:
            return None
        path = Path(found)
    else:
        path = Path(dotenv_path)
        if not path.is_file():
            return None
    load_dotenv(dotenv_path=path, override=override)
    return path.resolve()


def _looks_like_placeholder(value: str) -> bool:
    """Return True for values copied from docs, e.g. ``<your-api-key-here>``."""
    lowered = value.strip().strip("'\"").lower()
    if lowered.startswith("<") and lowered.endswith(">"):
        return True
    return lowered in _PLACEHOLDER_VALUES or any(m in lowered for m in _PLACEHOLDER_MARKERS)


def is_set(name: str) -> bool:
    """Return ``True`` if the variable exists, is not blank, and is not a placeholder.

    Args:
        name: Environment variable name, for example ``"GROQ_API_KEY"``.

    Returns:
        Whether the variable holds a usable (non-empty, non-placeholder) value.
    """
    value = os.environ.get(name)
    return bool(value and value.strip()) and not _looks_like_placeholder(value or "")


def require_env(*names: str, dotenv_path: Path | None = None) -> None:
    """Check that every variable in ``names`` is set. Raise a friendly error if not.

    Call it at the top of a notebook *after* :func:`load_env`. It returns
    nothing on purpose: libraries such as ``langchain-groq`` read their key
    from the environment themselves, so your code never needs to hold it.

    Args:
        *names: Variable names to check.
        dotenv_path: The file returned by :func:`load_env`, used only to make
            the error message more helpful.

    Raises:
        MissingSettingError: If one or more variables are missing, blank, or
            still contain a placeholder such as ``<your-api-key-here>``.
    """
    missing = [name for name in names if not is_set(name)]
    if missing:
        raise MissingSettingError(missing, dotenv_path)


def mask_secret(value: str | None, visible: int = 4) -> str:
    """Return a safe, human-readable description of a secret.

    Shows only the first ``visible`` characters and the total length, which is
    enough to tell two keys apart ("is this my new key or the old one?")
    without exposing anything useful to an attacker.

    Args:
        value: The secret (or ``None``).
        visible: How many leading characters to show. Capped at 4.

    Returns:
        For example ``"gsk_… (56 chars)"``, or ``"<not set>"``.
    """
    if not value:
        return "<not set>"
    # WHY the cap: even "helpful" prefixes leak entropy. Four characters covers
    # the usual provider prefix (gsk_, sk-p, ...); for shorter prefixes (hf_) one
    # character of the secret body shows, which is still safe to print.
    visible = max(0, min(visible, 4))
    if len(value) <= visible * 2:
        return f"*** ({len(value)} chars)"
    return f"{value[:visible]}… ({len(value)} chars)"


def env_status(*names: str) -> dict[str, str]:
    """Describe whether each variable is set, without revealing values.

    Args:
        *names: Variable names to describe.

    Returns:
        A mapping such as ``{"GROQ_API_KEY": "set: gsk_… (56 chars)",
        "LANGSMITH_API_KEY": "missing"}``. Safe to print in a notebook.
    """
    status: dict[str, str] = {}
    for name in names:
        value = os.environ.get(name)
        if not value or not value.strip():
            status[name] = "missing"
        elif _looks_like_placeholder(value):
            status[name] = "placeholder (replace it with your real value)"
        else:
            status[name] = f"set: {mask_secret(value)}"
    return status


def get_setting(name: str, default: str) -> str:
    """Read a non-secret setting from the environment, with a default.

    Args:
        name: Variable name, for example ``"MASTERY_MODEL_FAST"``.
        default: Value to use when the variable is missing or blank.

    Returns:
        The stripped value from the environment, or ``default``.
    """
    value = os.environ.get(name, "")
    return value.strip() or default


@dataclass(frozen=True)
class Settings:
    """Course-wide, non-secret settings read from the environment.

    Frozen (immutable) so a notebook cannot change a setting by accident
    halfway through; reload instead.

    Attributes:
        model_fast: Groq model ID for quick, cheap calls (``MASTERY_MODEL_FAST``).
        model_reasoning: Groq model ID for harder tasks (``MASTERY_MODEL_REASONING``).
        model_vision: Groq model ID that accepts images (``MASTERY_MODEL_VISION``). Preview.
        benchmark_model: Paid benchmark as ``"provider:model"`` (``MASTERY_BENCHMARK_MODEL``).
        benchmark_model_strong: Paid quality ceiling (``MASTERY_BENCHMARK_MODEL_STRONG``).
        langsmith_tracing: Whether LangSmith tracing is on (``LANGSMITH_TRACING``).
        langsmith_project: LangSmith project name (``LANGSMITH_PROJECT``).
    """

    model_fast: str = DEFAULT_MODEL_FAST
    model_reasoning: str = DEFAULT_MODEL_REASONING
    model_vision: str = DEFAULT_MODEL_VISION
    benchmark_model: str = DEFAULT_BENCHMARK_MODEL
    benchmark_model_strong: str = DEFAULT_BENCHMARK_MODEL_STRONG
    langsmith_tracing: bool = False
    langsmith_project: str = DEFAULT_LANGSMITH_PROJECT


def load_settings(*, load_dotenv_file: bool = True) -> Settings:
    """Load ``.env`` (optional) and return the course :class:`Settings`.

    Args:
        load_dotenv_file: Call :func:`load_env` first. Set ``False`` in tests
            or when the environment is already prepared.

    Returns:
        A :class:`Settings` instance built from the environment and the
        verified defaults above.

    Raises:
        mastery.doctor.CertificateSettingError: ``SSL_CERT_FILE`` or
            ``SSL_CERT_DIR`` points to a path that does not exist.
    """
    if load_dotenv_file:
        load_env()
    # Fail early and clearly if SSL_CERT_FILE/SSL_CERT_DIR point nowhere
    # (otherwise httpx raises a bare FileNotFoundError later). Lesson 00.02, step 4b.
    require_valid_ssl_env()
    tracing = get_setting("LANGSMITH_TRACING", "false").lower() in {"1", "true", "yes", "on"}
    return Settings(
        model_fast=get_setting("MASTERY_MODEL_FAST", DEFAULT_MODEL_FAST),
        model_reasoning=get_setting("MASTERY_MODEL_REASONING", DEFAULT_MODEL_REASONING),
        model_vision=get_setting("MASTERY_MODEL_VISION", DEFAULT_MODEL_VISION),
        benchmark_model=get_setting("MASTERY_BENCHMARK_MODEL", DEFAULT_BENCHMARK_MODEL),
        benchmark_model_strong=get_setting("MASTERY_BENCHMARK_MODEL_STRONG", DEFAULT_BENCHMARK_MODEL_STRONG),
        langsmith_tracing=tracing,
        langsmith_project=get_setting("LANGSMITH_PROJECT", DEFAULT_LANGSMITH_PROJECT),
    )
