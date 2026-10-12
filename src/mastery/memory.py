"""mastery.memory: checkpointer and store factories, plus small memory helpers.

Introduced in Module 03 (Lesson 03.01; SQLite in 03.02, tokens in 03.03, stores and
embeddings in 03.04) and used by Project 03.

Two kinds of memory, two factories:

- **Short-term** (one conversation, a *thread*): a checkpointer.
  ``make_checkpointer("memory")`` for tests and quick demos (lost when the
  kernel stops), ``make_checkpointer("sqlite", path)`` for notebooks that must
  survive a kernel restart.
- **Long-term** (across threads): a store.
  ``make_store("memory")`` or ``make_store("sqlite", path)``; pass
  ``embed=`` and ``dims=`` to enable semantic search.

>>> saver = make_checkpointer("memory")
>>> store = make_store("memory")
>>> learner_namespace("ana")
('learners', 'ana')

SQLite files go under ``data/outputs/memory/`` by default (git-ignored).
Close a SQLite saver or store with :func:`close` before deleting its file:
on Windows an open file can't be deleted (``PermissionError: [WinError 32]``).

Embeddings for semantic search:

- :class:`HashingEmbeddings`: offline, deterministic, no download. It matches
  shared *words* (after a crude stemming), not meaning. For tests and 🧪 cells.
- :func:`local_embeddings`: a real local model through ``fastembed`` (ONNX,
  no PyTorch), installed with ``pip install -e ".[embeddings]"``. The model
  (~70 MB) is downloaded once into ``~/.cache/fastembed``.

``langgraph-checkpoint-sqlite`` (``SqliteSaver``, ``SqliteStore``) and
``fastembed`` are imported lazily, so ``import mastery.memory`` always works.
Verified 2026-10-12 with langgraph 1.2.14, langgraph-checkpoint 4.2.0,
langgraph-checkpoint-sqlite 3.1.1 and fastembed 0.9.0.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import sqlite3
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Literal

from langchain_core.embeddings import Embeddings

__all__ = [
    "HashingEmbeddings",
    "LocalEmbeddings",
    "close",
    "count_tokens",
    "learner_namespace",
    "local_embeddings",
    "make_checkpointer",
    "make_store",
    "memory_dir",
    "safe_label",
    "thread_config",
]

Kind = Literal["memory", "sqlite"]
DEFAULT_LOCAL_MODEL = "BAAI/bge-small-en-v1.5"  # 384 dimensions, English, ~70 MB (fastembed default).


# --------------------------------------------------------------------------- paths and config
def memory_dir(root: str | Path | None = None) -> Path:
    """Folder for SQLite memory files: ``<repo>/data/outputs/memory`` (created if missing).

    ``data/outputs/`` and ``*.sqlite`` are in ``.gitignore``, so memories never get committed.

    Args:
        root: Repository root. Default: found with ``mastery.config.find_repo_root()``.

    Returns:
        The folder path (it exists after the call).
    """
    if root is None:
        from mastery.config import find_repo_root

        root = find_repo_root()
    folder = Path(root) / "data" / "outputs" / "memory"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _resolve(path: str | Path | None, default_name: str) -> Path:
    if path is None:
        return memory_dir() / default_name
    path = Path(path)
    if path.suffix == "":
        path = path.with_suffix(".sqlite")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def thread_config(thread_id: str, **extra: Any) -> dict[str, Any]:
    """The run config that selects a conversation: ``{"configurable": {"thread_id": ...}}``.

    Args:
        thread_id: Conversation id. Generate it on the server in real apps (e.g. ``uuid4``).
        **extra: More ``configurable`` keys.

    Returns:
        A config dict for ``invoke`` / ``stream`` / ``get_state``.

    Raises:
        ValueError: If ``thread_id`` is empty.
    """
    if not str(thread_id).strip():
        raise ValueError("thread_id must be a non-empty string")
    return {"configurable": {"thread_id": str(thread_id), **extra}}


# --------------------------------------------------------------------------- factories
def make_checkpointer(kind: Kind = "memory", path: str | Path | None = None) -> Any:
    """Return a checkpointer (short-term memory).

    Args:
        kind: ``"memory"`` -> ``InMemorySaver`` (lost when the process ends);
            ``"sqlite"`` -> ``SqliteSaver`` on a file (survives restarts).
        path: SQLite file. Default ``data/outputs/memory/checkpoints.sqlite``.
            A bare name like ``"study"`` becomes ``study.sqlite``.

    Returns:
        A LangGraph checkpointer (``setup()`` already called for SQLite).

    Raises:
        ValueError: If ``kind`` is not supported.
    """
    if kind == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()
    if kind == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver

        file = _resolve(path, "checkpoints.sqlite")
        # check_same_thread=False: Jupyter and LangGraph may use the connection from another
        # thread; SqliteSaver guards it with its own lock (documented in its docstring).
        saver = SqliteSaver(sqlite3.connect(str(file), check_same_thread=False))
        saver.setup()
        return saver
    raise ValueError(f"kind must be 'memory' or 'sqlite', got {kind!r}")


def make_store(
    kind: Kind = "memory",
    path: str | Path | None = None,
    *,
    embed: Embeddings | Any | None = None,
    dims: int | None = None,
    fields: Sequence[str] | None = None,
    ttl: dict[str, Any] | None = None,
) -> Any:
    """Return a store (long-term memory), optionally with semantic search.

    Args:
        kind: ``"memory"`` -> ``InMemoryStore``; ``"sqlite"`` -> ``SqliteStore`` on a file.
        path: SQLite file. Default ``data/outputs/memory/store.sqlite``.
        embed: Embeddings object (or ``f(texts) -> vectors``). Enables ``store.search(query=...)``.
        dims: Vector size of ``embed``. Required with ``embed`` (read from ``embed.dims`` if present).
        fields: JSON fields of each value to embed. Default ``["$"]`` (the whole value).
        ttl: SQLite only. A ``TTLConfig`` dict, e.g. ``{"default_ttl": 60 * 24 * 90}``
            (minutes; items expire 90 days after their last write). Expired items are
            removed by ``store.sweep_ttl()``.

    Returns:
        A LangGraph ``BaseStore`` (``setup()`` already called for SQLite).

    Raises:
        ValueError: Unsupported ``kind``, ``embed`` without a vector size, or ``ttl`` with ``kind="memory"``.
    """
    index: dict[str, Any] | None = None
    if embed is not None:
        dims = dims or getattr(embed, "dims", None)
        if not dims:
            raise ValueError("pass dims= with embed= (the embedding vector size)")
        index = {"embed": embed, "dims": int(dims), "fields": list(fields or ["$"])}
    if kind == "memory":
        from langgraph.store.memory import InMemoryStore

        if ttl is not None:
            raise ValueError("ttl= is supported for kind='sqlite' only (InMemoryStore has no TTL)")
        return InMemoryStore(index=index)  # type: ignore[arg-type]
    if kind == "sqlite":
        from langgraph.store.sqlite import SqliteStore

        file = _resolve(path, "store.sqlite")
        # Same settings as SqliteStore.from_conn_string: autocommit, shareable across threads.
        conn = sqlite3.connect(str(file), check_same_thread=False, isolation_level=None)
        store = SqliteStore(conn, index=index, ttl=ttl)  # type: ignore[arg-type]
        store.setup()  # creates tables; with an index it also loads the sqlite-vec extension
        return store
    raise ValueError(f"kind must be 'memory' or 'sqlite', got {kind!r}")


def close(*objects: Any) -> None:
    """Close the SQLite connection of savers/stores made by this module (no-op for in-memory ones)."""
    for obj in objects:
        conn = getattr(obj, "conn", None)
        if isinstance(conn, sqlite3.Connection):
            conn.close()


# --------------------------------------------------------------------------- namespaces
_LABEL_OK = re.compile(r"^[A-Za-z0-9_\-@:+ ]{1,128}$")


def safe_label(value: str) -> str:
    """Validate one namespace label (e.g. a user id) before it reaches the store.

    LangGraph already rejects empty labels and labels with ``.``; this also rejects
    anything outside a small allow-list, so ids like ``"ana/../bob"`` or ``"*"`` fail loudly.

    Args:
        value: The label, e.g. a user id.

    Returns:
        The label without surrounding spaces.

    Raises:
        ValueError: If the label is empty, too long, or has characters outside the allow-list.
    """
    text = str(value).strip()
    if not _LABEL_OK.fullmatch(text):
        raise ValueError(f"invalid namespace label {value!r}: use letters, digits, space and _-@:+ (max 128)")
    return text


def learner_namespace(user_id: str, *sub: str) -> tuple[str, ...]:
    """``("learners", user_id, *sub)``: the course's namespace layout for per-user memories.

    Args:
        user_id: The learner id, from ``runtime.context`` (never from a tool argument).
        *sub: Optional sub-namespaces, e.g. ``"facts"`` or ``"episodes"``.

    Returns:
        The namespace tuple.

    Raises:
        ValueError: If any label fails :func:`safe_label`.
    """
    return ("learners", safe_label(user_id), *(safe_label(s) for s in sub))


# --------------------------------------------------------------------------- tokens
def count_tokens(messages: Iterable[Any]) -> int:
    """Approximate token count (``count_tokens_approximately``: ~4 chars per token + overhead).

    The same counter ``SummarizationMiddleware`` uses by default, so budgets you check with it
    match what the middleware sees. It is an estimate; Groq's ``usage_metadata`` is the truth.
    """
    from langchain_core.messages.utils import count_tokens_approximately

    return count_tokens_approximately(list(messages))


# --------------------------------------------------------------------------- embeddings
_WORD = re.compile(r"[a-záéíóúñü0-9]+")
_STOP = frozenset(
    "a an and are as at be but by do does for from has have i in is it its me my of on or our "
    "so that the their them they this to was we what when where which who why with you your".split()
)


def _stem(word: str) -> str:
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ers", "er", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


class HashingEmbeddings(Embeddings):
    """Offline bag-of-words embeddings (the "hashing trick"). Deterministic, no download, no key.

    Each word (lower-cased, stop words removed, crudely stemmed) is hashed with BLAKE2b into one of
    ``dims`` buckets with a +/- sign; the vector is L2-normalised, so the dot product is a
    cosine similarity of shared words. It finds "fractions" for "I struggle with fraction
    problems" but **not** "pizza" for "Italian food": no meaning, only words. Use
    :func:`local_embeddings` for meaning.

    (Python's built-in ``hash()`` is randomised per process, which would break vectors saved
    in SQLite; BLAKE2b is stable.)
    """

    def __init__(self, dims: int = 512) -> None:
        if dims < 8:
            raise ValueError("dims must be >= 8")
        self.dims = dims

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        for word in _WORD.findall(text.lower()):
            if word in _STOP:
                continue
            digest = hashlib.blake2b(_stem(word).encode(), digest_size=8).digest()
            number = int.from_bytes(digest, "little")
            vec[number % self.dims] += 1.0 if (number >> 63) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class LocalEmbeddings(Embeddings):
    """LangChain ``Embeddings`` around a ``fastembed.TextEmbedding`` model (runs on CPU, offline after download)."""

    def __init__(self, model_name: str = DEFAULT_LOCAL_MODEL, cache_dir: str | Path | None = None) -> None:
        try:
            from fastembed import TextEmbedding
        except ModuleNotFoundError as error:  # pragma: no cover - depends on the optional extra
            raise ModuleNotFoundError(
                'fastembed is not installed. In Git Bash, at the repo root: python -m pip install -e ".[embeddings]"'
            ) from error
        cache = Path(cache_dir or os.environ.get("FASTEMBED_CACHE_PATH") or Path.home() / ".cache" / "fastembed")
        cache.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        # fastembed's default cache is the OS temp folder, which Windows cleans up; a fixed folder
        # avoids silent re-downloads.
        self._model = TextEmbedding(model_name=model_name, cache_dir=str(cache))
        self.dims = len(next(iter(self._model.embed(["probe"]))))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def local_embeddings(model_name: str = DEFAULT_LOCAL_MODEL, cache_dir: str | Path | None = None) -> LocalEmbeddings:
    """A real local embedding model (``fastembed``). Its ``.dims`` attribute feeds :func:`make_store`."""
    return LocalEmbeddings(model_name, cache_dir)
