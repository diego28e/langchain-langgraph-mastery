"""Embedding cache and vector-store construction (in-memory or Chroma persisted outside git)."""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import struct
import warnings
from pathlib import Path
from typing import Any, Literal

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from mastery.config import find_repo_root
from mastery.memory import HashingEmbeddings


def embedding_label(embeddings: Any) -> str:
    """A short name for an embeddings object (used for cache namespaces and reports)."""
    inner = getattr(embeddings, "base", embeddings)
    name = getattr(inner, "model_name", None) or getattr(inner, "model", None) or type(inner).__name__
    dims = getattr(inner, "dims", None)
    return f"{name}" + (f"-{dims}" if dims and type(inner).__name__ == "HashingEmbeddings" else "")


class CachedEmbeddings(Embeddings):
    """Wrap any ``Embeddings`` with a SQLite cache keyed by ``sha256(model + text)``.

    Re-running a notebook re-embeds nothing that was embedded before; changing the model changes
    the key, so vectors of different models never mix. ``hits`` / ``misses`` count cache use.
    The cache lives in ``data/cache/embeddings/`` (gitignored); delete the folder to clear it.
    """

    def __init__(self, base: Embeddings, cache_dir: str | Path | None = None, namespace: str | None = None) -> None:
        self.base = base
        self.namespace = namespace or embedding_label(base)
        folder = Path(cache_dir) if cache_dir else Path(find_repo_root()) / "data" / "cache" / "embeddings"
        folder.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in self.namespace)
        self.path = folder / f"{safe}.sqlite"
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vector BLOB)")
        self.hits = 0
        self.misses = 0

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.namespace}\x00{text}".encode()).hexdigest()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        keys = [self._key(t) for t in texts]
        found: dict[str, list[float]] = {}
        for start in range(0, len(keys), 500):
            batch = keys[start:start + 500]
            rows = self._db.execute(f"SELECT key, vector FROM vectors WHERE key IN ({','.join('?' * len(batch))})",
                                    batch).fetchall()
            for key, blob in rows:
                found[key] = list(struct.unpack(f"{len(blob) // 4}f", blob))
        missing = [i for i, k in enumerate(keys) if k not in found]
        self.hits += len(texts) - len(missing)
        self.misses += len(missing)
        if missing:
            vectors = self.base.embed_documents([texts[i] for i in missing])
            with self._db:
                for i, vector in zip(missing, vectors):
                    found[keys[i]] = list(vector)
                    self._db.execute("INSERT OR REPLACE INTO vectors VALUES (?, ?)",
                                     (keys[i], struct.pack(f"{len(vector)}f", *vector)))
        return [found[k] for k in keys]

    def embed_query(self, text: str) -> list[float]:
        return self.base.embed_query(text)   # queries are cheap and rarely repeat: not cached

    def close(self) -> None:
        self._db.close()


def default_embeddings(prefer: Literal["local", "hashing"] = "local") -> Embeddings:
    """fastembed ``BAAI/bge-small-en-v1.5`` when available (first use downloads ~67 MB), else ``HashingEmbeddings``."""
    if prefer == "local":
        try:
            from mastery.memory import local_embeddings

            return local_embeddings()
        except Exception as error:  # noqa: BLE001 - extra missing, offline, SSL proxy...
            warnings.warn(f"Local embeddings unavailable ({type(error).__name__}: {str(error)[:120]}); "
                          "falling back to offline HashingEmbeddings.", stacklevel=2)
    return HashingEmbeddings(dims=1024)


def vectorstore_dir(name: str) -> Path:
    """``data/vectorstores/<name>``: the gitignored home of persisted indexes."""
    return Path(find_repo_root()) / "data" / "vectorstores" / name


def _clean(metadata: dict) -> dict:
    """Chroma accepts only str/int/float/bool metadata values: drop ``None`` and stringify the rest."""
    return {k: (v if isinstance(v, (str, int, float, bool)) else str(v)) for k, v in metadata.items() if v is not None}


def build_index(chunks: list[Document], embeddings: Embeddings, kind: Literal["memory", "chroma"] = "memory",
                collection: str = "course-docs", persist_dir: str | Path | None = None, batch_size: int = 256) -> Any:
    """Embed ``chunks`` into a vector store and return it.

    Ids are the chunks' ``chunk_id``, so re-running is an *upsert*, not a duplicate. Chroma uses
    cosine distance and persists to ``persist_dir`` (default ``data/vectorstores/<collection>``).
    """
    ids = [c.metadata.get("chunk_id") or hashlib.sha1(c.page_content.encode()).hexdigest() for c in chunks]
    docs = [Document(page_content=c.page_content, metadata=_clean(c.metadata)) for c in chunks]
    if kind == "memory":
        store: Any = InMemoryVectorStore(embeddings)
    elif kind == "chroma":
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
        import chromadb
        from langchain_chroma import Chroma

        folder = Path(persist_dir) if persist_dir else vectorstore_dir(collection)
        folder.mkdir(parents=True, exist_ok=True)
        store = Chroma(collection_name=collection, embedding_function=embeddings, persist_directory=str(folder),
                       client_settings=chromadb.config.Settings(anonymized_telemetry=False, is_persistent=True,
                                                                persist_directory=str(folder)),
                       collection_configuration={"hnsw": {"space": "cosine"}})
    else:
        raise ValueError(f"kind must be 'memory' or 'chroma', got {kind!r}")
    for start in range(0, len(docs), batch_size):
        store.add_documents(docs[start:start + batch_size], ids=ids[start:start + batch_size])
    return store


def open_chroma(collection: str, embeddings: Embeddings, persist_dir: str | Path | None = None) -> Any:
    """Re-open a persisted Chroma collection (no re-embedding). Use the *same* embeddings model."""
    return build_index([], embeddings, kind="chroma", collection=collection, persist_dir=persist_dir)


def reset_chroma(target: Any) -> None:
    """Delete a Chroma collection (pass the store) or a whole persist folder (pass a path).

    On Windows an open Chroma client keeps its files locked (``PermissionError: [WinError 32]``):
    delete the *collection* through the store, or restart the kernel before removing the folder.
    """
    if hasattr(target, "delete_collection"):
        target.delete_collection()
        return
    path = Path(target)
    if path.exists():
        try:
            shutil.rmtree(path)
        except PermissionError as error:  # pragma: no cover - Windows file locks
            raise PermissionError(f"{path} is locked (an open Chroma client?). Restart the kernel, then retry.") from error


def folder_size(path: str | Path) -> str:
    """Human-readable size of a folder (how big did the index get?)."""
    total = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file()) if Path(path).exists() else 0
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024 or unit == "GB":
            return f"{total:.0f} {unit}" if unit == "B" else f"{total:.1f} {unit}"
        total /= 1024
    return ""
