"""Run metadata: record exactly which prompt, model config, data and code produced a result.

Introduced in Module 01 (Lessons 01.03 and 01.08, Project 01) and reused by
every later module that runs an experiment or logs to LangSmith.

The convention:
    Every experiment run carries the same small set of keys, so two results
    can always be traced back to what produced them:

    - ``prompt_version``: a human name you bump on purpose (``"tickets-v2"``).
    - ``prompt_hash``: a short content hash of the prompt. If the prompt
      changes and you forget to bump the version, the hash still changes.
    - ``model`` and ``config_hash``: the model ID and a hash of every setting
      that can change outputs (temperature, reasoning effort, bound tools...).
    - ``dataset_version`` / ``dataset_hash``: which data was scored.
    - ``git_sha`` / ``git_dirty``: which code ran, and whether it had
      uncommitted changes.
    - ``python`` and ``pkg_*``: library versions (behaviour changes between
      releases).

    :func:`run_metadata` builds that dict. Pass it as LangSmith metadata
    (``config={"metadata": run_metadata(...)}``) and print it at the top of a
    report with :func:`format_metadata`.

Hashes are SHA-256 over a canonical JSON form (sorted keys), shortened to 12
hex characters: stable across runs, machines and dict ordering, and short
enough to read. Secrets are never included: model settings are read from an
allow-list, and keys that look like credentials are dropped.

Pure standard library (``hashlib``, ``json``, ``subprocess``, ``importlib.metadata``).
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_PACKAGES",
    "HASH_LENGTH",
    "content_hash",
    "file_hash",
    "format_metadata",
    "git_info",
    "model_fingerprint",
    "package_versions",
    "run_metadata",
]

# 12 hex characters = 48 bits: collisions are negligible for course-sized
# experiment logs, and the hash still fits in a table column.
HASH_LENGTH = 12
# Libraries whose version is recorded by default (missing ones are reported as None).
DEFAULT_PACKAGES = ("langchain", "langchain-core", "langchain-groq", "langgraph", "langsmith")
# Seconds before a git call is abandoned (never block a notebook on git).
GIT_TIMEOUT_S = 5
# Environment variables CI systems use for the commit being built.
CI_SHA_VARIABLES = ("GITHUB_SHA", "CI_COMMIT_SHA")

# Model settings that can change outputs. Read from an allow-list so that
# api_key, headers, clients and other secrets can never leak into metadata.
MODEL_PARAMS = (
    "temperature",
    "top_p",
    "top_k",
    "max_tokens",
    "max_completion_tokens",
    "max_output_tokens",
    "reasoning_effort",
    "reasoning_format",
    "reasoning",
    "thinking_level",
    "thinking_budget",
    "include_thoughts",
    "service_tier",
    "seed",
    "stop",
    "n",
    "frequency_penalty",
    "presence_penalty",
    "verbosity",
    "use_responses_api",
    "output_version",
)
# Keys that look like credentials are dropped from any mapping we record.
# "token" and "key" only match as whole name parts, so "max_tokens" or
# "keywords" are kept while "api_key", "user_token" or "x-api-key" are dropped.
_SECRET_KEY = re.compile(
    r"secret|passw(or)?d|credential|cookie|authori[sz]ation|bearer|api_?key|access_?token"
    r"|(^|[_\-.])(keys?|token|auth|headers?)($|[_\-.])",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Canonical form and hashes
# ---------------------------------------------------------------------------


def _canonical_prompt(obj: Any) -> Any:
    """Describe a LangChain prompt by its templates, not by its Python class path."""
    if hasattr(obj, "messages") and hasattr(obj, "input_variables"):  # ChatPromptTemplate
        partials = {
            key: f"<callable {getattr(value, '__name__', '?')}>" if callable(value) else _canonical(value)
            for key, value in (getattr(obj, "partial_variables", None) or {}).items()
        }
        return {"chat_prompt": [_canonical(m) for m in obj.messages], "partials": partials}
    if hasattr(obj, "variable_name") and hasattr(obj, "optional"):  # MessagesPlaceholder
        return {
            "placeholder": obj.variable_name,
            "optional": obj.optional,
            "n_messages": getattr(obj, "n_messages", None),
        }
    if hasattr(obj, "prompt") and hasattr(obj, "additional_kwargs"):  # message prompt templates
        return {
            "message_template": type(obj).__name__,
            "role": getattr(obj, "role", None),
            "prompt": _canonical(obj.prompt),
        }
    if hasattr(obj, "template"):  # PromptTemplate, ImagePromptTemplate
        return {"template": _canonical(obj.template), "format": getattr(obj, "template_format", None)}
    raise TypeError(f"cannot describe prompt object of type {type(obj).__name__}")


def _is_prompt(obj: Any) -> bool:
    module = type(obj).__module__
    return module.startswith("langchain_core.prompts") or module.startswith("langchain.prompts")


def _is_message(obj: Any) -> bool:
    return type(obj).__module__.startswith("langchain_core.messages") and hasattr(obj, "content")


def _canonical_message(message: Any) -> dict[str, Any]:
    """The parts of a message that reach the model (no ids, no response metadata)."""
    data: dict[str, Any] = {"type": message.type, "content": _canonical(message.content)}
    for attr in ("name", "tool_call_id"):
        if getattr(message, attr, None):
            data[attr] = getattr(message, attr)
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        data["tool_calls"] = [{"name": c.get("name"), "args": _canonical(c.get("args"))} for c in tool_calls]
    return data


def _canonical(obj: Any) -> Any:
    """Convert ``obj`` to plain JSON data whose serialization does not depend on ordering."""
    if obj is None or isinstance(obj, bool | int | float | str):
        return obj
    if isinstance(obj, Path):
        raise TypeError(f"use file_hash({str(obj)!r}) to hash a file's contents (content_hash would hash the path)")
    if isinstance(obj, bytes | bytearray):
        return {"bytes_sha256": hashlib.sha256(bytes(obj)).hexdigest()}
    if isinstance(obj, Mapping):
        return {str(k): _canonical(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_canonical(v) for v in obj]
    if isinstance(obj, set | frozenset):
        items = [_canonical(v) for v in obj]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    if isinstance(obj, type) and hasattr(obj, "model_json_schema"):  # a Pydantic model class
        return {"schema": obj.model_json_schema()}
    if _is_prompt(obj):
        return _canonical_prompt(obj)
    if _is_message(obj):
        return _canonical_message(obj)
    if hasattr(obj, "invoke"):  # a model, binding or chain: describe the model inside
        if _find_model(obj, {}) is None:
            raise TypeError(
                f"content_hash found no chat model inside {type(obj).__name__}; "
                "hash its prompt and settings instead"
            )
        return model_fingerprint(obj)
    if hasattr(obj, "model_dump"):  # any other Pydantic object
        return _canonical(obj.model_dump(mode="json"))
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _canonical(dataclasses.asdict(obj))
    raise TypeError(
        f"content_hash cannot hash {type(obj).__name__!r} reproducibly; "
        "convert it to a dict/list/str first (repr() would include memory addresses)"
    )


def content_hash(obj: Any, length: int = HASH_LENGTH) -> str:
    """Short, stable SHA-256 hash of a prompt, config or dataset held in memory.

    Equal content gives an equal hash on every machine and in every run,
    regardless of dict key order. Change one character and the hash changes.

    Supported: str, numbers, None, dicts, lists, tuples, sets, bytes, Pydantic
    classes (their JSON schema) and objects, dataclasses, LangChain prompt
    templates (their templates and placeholders) and chat models (their
    :func:`model_fingerprint`).

    Args:
        obj: What to hash.
        length: Number of hex characters to keep (1-64).

    Returns:
        A lowercase hex string of ``length`` characters.

    Raises:
        TypeError: For objects with no reproducible form (functions, clients)
            and for ``Path`` (use :func:`file_hash`).
        ValueError: If ``length`` is not between 1 and 64.
    """
    if not 1 <= length <= 64:
        raise ValueError(f"length must be between 1 and 64, got {length}")
    text = json.dumps(_canonical(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def file_hash(path: str | os.PathLike[str], length: int = HASH_LENGTH, *, normalize_newlines: bool = True) -> str:
    """Short SHA-256 hash of a file's bytes, or of every file in a folder.

    Args:
        path: A file, or a folder (all files below it are hashed together,
            in sorted order, with their relative paths).
        length: Number of hex characters to keep (1-64).
        normalize_newlines: Treat ``\\r\\n`` as ``\\n``, so a dataset checked
            out on Windows (Git may convert line endings) hashes the same as
            on macOS/Linux. Default True.

    Returns:
        A lowercase hex string of ``length`` characters.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If ``length`` is not between 1 and 64.
    """
    if not 1 <= length <= 64:
        raise ValueError(f"length must be between 1 and 64, got {length}")
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"no such file or folder: {root}")
    files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
    digest = hashlib.sha256()
    for file in files:
        if root.is_dir():
            digest.update(file.relative_to(root).as_posix().encode("utf-8") + b"\0")
        data = file.read_bytes()
        if normalize_newlines:
            data = data.replace(b"\r\n", b"\n")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()[:length]


# ---------------------------------------------------------------------------
# Model, code and environment
# ---------------------------------------------------------------------------


def _drop_secrets(value: Any) -> Any:
    """Remove credential-looking keys from nested mappings."""
    if isinstance(value, Mapping):
        return {str(k): _drop_secrets(v) for k, v in value.items() if not _SECRET_KEY.search(str(k))}
    if isinstance(value, list | tuple):
        return [_drop_secrets(v) for v in value]
    return value


def _plain_or_hash(value: Any) -> Any:
    """Keep JSON scalars; replace anything bigger by its content hash."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    try:
        return f"sha256:{content_hash(_drop_secrets(value))}"
    except TypeError:
        return f"<{type(value).__name__}>"


def _jsonable(value: Any) -> Any:
    """Small settings (scalars, lists, dicts) in clear, secrets dropped, anything else hashed."""
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items() if not _SECRET_KEY.search(str(k))}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return _plain_or_hash(value)


def _find_model(obj: Any, bound: dict[str, Any], depth: int = 0) -> Any | None:
    """Depth-first search for the chat model inside bindings and chains.

    Collects the kwargs of every ``.bind(...)`` layer crossed on the way
    into ``bound`` (outer layers win, as in LangChain).
    """
    if obj is None or depth > 20:
        return None
    inner = getattr(obj, "bound", None)
    kwargs = getattr(obj, "kwargs", None)
    if inner is not None and isinstance(kwargs, Mapping):
        found = _find_model(inner, bound, depth + 1)
        if found is not None:
            for key, value in kwargs.items():
                bound.setdefault(key, value)
        return found
    if hasattr(obj, "_llm_type"):
        return obj
    children: list[Any] = []
    for attr in ("steps", "middle"):
        group = getattr(obj, attr, None)
        if isinstance(group, list | tuple):
            children.extend(group)
    for attr in ("first", "runnable", "default", "mapper"):
        children.append(getattr(obj, attr, None))
    parallel = getattr(obj, "steps__", None)
    if isinstance(parallel, Mapping):
        children.extend(parallel.values())
    for child in children:
        found = _find_model(child, bound, depth + 1)
        if found is not None:
            return found
    return None


def model_fingerprint(model: Any) -> dict[str, Any]:
    """Describe a chat model's output-relevant settings, never its secrets.

    Finds the chat model inside ``.bind(...)`` bindings and chains such as
    ``llm.with_structured_output(Schema)``, and records the bound arguments
    too (tool names in clear; response formats and schemas as content hashes).

    Args:
        model: A LangChain chat model, a binding around one, or a chain
            that contains one.

    Returns:
        A JSON-ready dict: ``class``, ``model``, the allow-listed parameters
        that are set (see ``MODEL_PARAMS``), filtered ``model_kwargs``,
        ``bound`` arguments and, for chains, ``wrapper`` (the outer class).
        API keys, headers and clients are never read.
    """
    bound_kwargs: dict[str, Any] = {}
    # Step 1: find the chat model (peeling bindings, looking inside chains).
    obj = _find_model(model, bound_kwargs) or model
    fingerprint: dict[str, Any] = {
        "class": type(obj).__name__,
        "model": getattr(obj, "model_name", None) or getattr(obj, "model", None) or getattr(obj, "model_id", None),
    }
    if obj is not model and getattr(model, "bound", None) is not obj:
        fingerprint["wrapper"] = type(model).__name__
    # Step 2: read the allow-listed settings only.
    for name in MODEL_PARAMS:
        value = getattr(obj, name, None)
        if value is not None and not callable(value):
            fingerprint[name] = _jsonable(value)
    model_kwargs = getattr(obj, "model_kwargs", None)
    if isinstance(model_kwargs, Mapping) and model_kwargs:
        fingerprint["model_kwargs"] = _jsonable(model_kwargs)
    # Step 3: bound arguments: tool names in clear, everything else as values or hashes.
    if bound_kwargs:
        bound: dict[str, Any] = {}
        for key, value in bound_kwargs.items():
            if _SECRET_KEY.search(str(key)):
                continue
            if key == "tools" and isinstance(value, list | tuple):
                bound[key] = [_tool_name(t) for t in value]
            else:
                bound[key] = _plain_or_hash(value)
        fingerprint["bound"] = bound
    if not isinstance(fingerprint["model"], str | None):
        fingerprint["model"] = str(fingerprint["model"])
    return fingerprint


def _tool_name(tool: Any) -> str:
    if isinstance(tool, Mapping):
        function = tool.get("function")
        if isinstance(function, Mapping) and function.get("name"):
            return str(function["name"])
        return str(tool.get("name") or tool.get("title") or "?")
    return str(getattr(tool, "name", None) or getattr(tool, "__name__", None) or type(tool).__name__)


def _run_git(args: list[str], cwd: str | os.PathLike[str] | None) -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        result = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            [git, *args], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def git_info(cwd: str | os.PathLike[str] | None = None, *, short: bool = True) -> dict[str, Any]:
    """Return the current commit and whether there are uncommitted changes.

    Never raises: if git is not installed, the folder is not a repository, or
    git is slow, the values are None. On CI, ``GITHUB_SHA`` / ``CI_COMMIT_SHA``
    are used when git itself is unavailable.

    Args:
        cwd: Folder inside the repository (default: the current directory).
        short: Return the 12-character SHA instead of the full 40.

    Returns:
        ``{"git_sha": str | None, "git_dirty": bool | None}``.
    """
    sha = _run_git(["rev-parse", "HEAD"], cwd)
    dirty: bool | None = None
    if sha:
        status = _run_git(["status", "--porcelain"], cwd)
        dirty = None if status is None else bool(status)
    else:
        sha = next((os.environ[v] for v in CI_SHA_VARIABLES if os.environ.get(v)), None)
    if sha and short:
        sha = sha[:HASH_LENGTH]
    return {"git_sha": sha, "git_dirty": dirty}


def package_versions(packages: Iterable[str] = DEFAULT_PACKAGES) -> dict[str, str | None]:
    """Installed versions of ``packages`` (None for those not installed).

    Args:
        packages: Distribution names as on PyPI, e.g. ``"langchain-core"``.

    Returns:
        ``{name: version or None}`` in the order given.
    """
    versions: dict[str, str | None] = {}
    for name in packages:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


# ---------------------------------------------------------------------------
# The convention
# ---------------------------------------------------------------------------


def run_metadata(
    *,
    prompt_version: str | None = None,
    prompt: Any = None,
    model: Any = None,
    config: Mapping[str, Any] | None = None,
    dataset: Any = None,
    dataset_version: str | None = None,
    packages: Iterable[str] = DEFAULT_PACKAGES,
    include_git: bool = True,
    cwd: str | os.PathLike[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build the course's standard metadata dict for one experiment run.

    Args:
        prompt_version: Human version name you bump on purpose (``"tickets-v2"``).
        prompt: The prompt (string, ChatPromptTemplate, messages...) to hash.
        model: A chat model (fingerprinted) or a ``"provider:model"`` string.
        config: Other settings that change results (``{"method": "json_schema",
            "strict": True}``); hashed together with the model.
        dataset: A ``Path`` to a file/folder (hashed by content) or the
            in-memory data itself.
        dataset_version: Human version of the dataset (e.g. the answer key's
            ``_version``).
        packages: Packages whose versions to record (``pkg_<name>`` keys).
        include_git: Record ``git_sha`` / ``git_dirty`` (set False in tests).
        cwd: Folder used for the git lookup.
        **extra: More flat, JSON-ready keys (``config_name="fast"``, ``run=2``).

    Returns:
        A flat dict of JSON values, the same keys on every call so results
        line up in tables. Unknown values are None.

    Raises:
        ValueError: If an ``extra`` key would overwrite a standard key.
        TypeError: If an ``extra`` value is not JSON-ready, or ``prompt`` /
            ``dataset`` cannot be hashed reproducibly.

    Example:
        >>> meta = run_metadata(prompt_version="tickets-v2", prompt="Classify: {ticket}",
        ...                     include_git=False, packages=())
        >>> meta["prompt_hash"] == content_hash("Classify: {ticket}")
        True
    """
    # Step 1: model id and a hash of everything that can change the outputs.
    if model is None:
        model_id, model_part = None, None
    elif isinstance(model, str):
        model_id, model_part = model, model
    else:
        model_part = model_fingerprint(model)
        model_id = model_part.get("model")
    config_part = _drop_secrets(dict(config)) if config else None
    has_config = model_part is not None or config_part is not None
    # Step 2: dataset hash (a Path is hashed by content, anything else as data).
    if dataset is None:
        dataset_hash = None
    elif isinstance(dataset, Path):
        dataset_hash = file_hash(dataset)
    else:
        dataset_hash = content_hash(dataset)

    meta: dict[str, Any] = {
        "prompt_version": prompt_version,
        "prompt_hash": content_hash(prompt) if prompt is not None else None,
        "model": model_id,
        "config_hash": content_hash({"model": model_part, "config": config_part}) if has_config else None,
        "dataset_version": dataset_version,
        "dataset_hash": dataset_hash,
        "git_sha": None,
        "git_dirty": None,
        "python": platform.python_version(),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if include_git:
        meta.update(git_info(cwd))
    # Step 3: library versions as flat keys (flat keys are easy to filter in LangSmith).
    for name, version in package_versions(packages).items():
        meta["pkg_" + re.sub(r"[^0-9a-zA-Z]+", "_", name).lower()] = version
    # Step 4: caller's extra keys, checked so nothing standard is overwritten silently.
    for key, value in extra.items():
        if key in meta:
            raise ValueError(f"extra key {key!r} would overwrite a standard metadata key")
        try:
            json.dumps(value)
        except TypeError as error:
            raise TypeError(f"metadata value for {key!r} is not JSON-ready: {error}") from None
        meta[key] = value
    return meta


def format_metadata(meta: Mapping[str, Any], *, skip_none: bool = True) -> str:
    """Render metadata as ``key: value`` lines for the top of a report.

    Args:
        meta: Usually the output of :func:`run_metadata`.
        skip_none: Leave out keys whose value is None.

    Returns:
        One ``key: value`` line per key, keys aligned.
    """
    rows = [(str(k), v) for k, v in meta.items() if not (skip_none and v is None)]
    if not rows:
        return ""
    width = max(len(k) for k, _ in rows)
    return "\n".join(f"{k.ljust(width)} : {v}" for k, v in rows)
