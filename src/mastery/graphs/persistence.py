"""Checkpointer helpers for Module 08 (Lessons 08.01, 08.02, 08.04; Project 08).

- :func:`course_serde` / :func:`sqlite_checkpointer`: a ``SqliteSaver`` that, like
  ``memory_checkpointer``, allows the course's Pydantic state types (D-028).
- :func:`checkpoint_rows`: a thread's history as small dicts (step, source, next, id, parent).
- :func:`count_checkpoints`, :func:`file_size`: watch a database grow; ``saver.delete_thread(id)``
  removes a thread and :func:`trim_thread` keeps only its newest checkpoint. (``saver.prune`` is in the
  base API but ``SqliteSaver`` 3.1.1 raises ``NotImplementedError``, measured 2026-10-12.)

Close a SQLite saver with ``mastery.memory.close(saver)`` before deleting its file (Windows).
Verified 2026-10-12 with langgraph-checkpoint 4.2.0 and langgraph-checkpoint-sqlite 3.1.1.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from mastery.graphs.state import CHECKPOINT_TYPES

__all__ = ["acheckpoint_rows", "async_sqlite_checkpointer", "checkpoint_rows", "count_checkpoints", "course_serde",
           "file_size", "sqlite_checkpointer", "trim_thread"]


def course_serde(extra: Iterable[tuple[str, str]] = ()) -> Any:
    """``JsonPlusSerializer`` allowing ``CHECKPOINT_TYPES`` (+ ``extra`` ``(module, class)`` pairs)."""
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    return JsonPlusSerializer(allowed_msgpack_modules=[*CHECKPOINT_TYPES, *extra])


def sqlite_checkpointer(path: str | Path, *, extra_types: Iterable[tuple[str, str]] = ()) -> Any:
    """A ``SqliteSaver`` on ``path`` (parent folders created, ``setup()`` called) with :func:`course_serde`."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: LangGraph may use the connection from worker threads; SqliteSaver locks it.
    saver = SqliteSaver(sqlite3.connect(str(file), check_same_thread=False), serde=course_serde(extra_types))
    saver.setup()
    return saver


async def async_sqlite_checkpointer(path: str | Path, *, extra_types: Iterable[tuple[str, str]] = ()) -> Any:
    """An ``AsyncSqliteSaver`` for graphs with **async** nodes (``ainvoke``/``astream``).

    ``SqliteSaver`` raises ``NotImplementedError`` on async calls. Create this one inside the event
    loop that will use it (in Jupyter: ``saver = await async_sqlite_checkpointer(path)``) and close it
    with ``await saver.conn.close()``.
    """
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    saver = AsyncSqliteSaver(await aiosqlite.connect(str(file)), serde=course_serde(extra_types))
    await saver.setup()
    return saver


def _row(snap: Any) -> dict[str, Any]:
    parent = (snap.parent_config or {}).get("configurable", {}).get("checkpoint_id")
    return {"step": snap.metadata.get("step"), "source": snap.metadata.get("source"), "next": tuple(snap.next),
            "checkpoint_id": snap.config["configurable"]["checkpoint_id"], "parent_id": parent,
            "interrupts": len(snap.interrupts)}


async def acheckpoint_rows(graph: Any, config: dict, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Async :func:`checkpoint_rows` (for ``AsyncSqliteSaver``)."""
    return [_row(snap) async for snap in graph.aget_state_history(config, limit=limit)]


def checkpoint_rows(graph: Any, config: dict, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Newest-first rows: ``step``, ``source`` (input/loop/update/fork), ``next``, ``checkpoint_id``, ``parent_id``."""
    return [_row(snap) for snap in graph.get_state_history(config, limit=limit)]


def count_checkpoints(saver: Any, thread_id: str | None = None) -> int:
    """Number of checkpoints (all threads, or one)."""
    config = {"configurable": {"thread_id": thread_id}} if thread_id else None
    return sum(1 for _ in saver.list(config))


def file_size(path: str | Path) -> str:
    """Size of a SQLite file plus its ``-wal`` file, human readable."""
    total = sum(p.stat().st_size for p in (Path(path), Path(f"{path}-wal")) if p.exists())
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024 or unit == "GB":
            return f"{total:.0f} {unit}" if unit == "B" else f"{total:.1f} {unit}"
        total /= 1024
    return f"{total:.1f} GB"


def trim_thread(saver: Any, thread_id: str) -> int:
    """``SqliteSaver`` only: keep the newest checkpoint of ``thread_id`` (root namespace), delete the rest.

    History (time travel) for that thread is gone afterwards; the current state and pending
    interrupts stay. Returns the number of checkpoints deleted. Run ``VACUUM`` to shrink the file.
    """
    latest = saver.get_tuple({"configurable": {"thread_id": thread_id}})
    if latest is None:
        return 0
    keep = latest.config["configurable"]["checkpoint_id"]
    with saver.lock, saver.conn:
        cur = saver.conn.execute(
            "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = '' AND checkpoint_id != ?", (thread_id, keep))
        saver.conn.execute(
            "DELETE FROM writes WHERE thread_id = ? AND checkpoint_ns = '' AND checkpoint_id != ?", (thread_id, keep))
        return cur.rowcount
