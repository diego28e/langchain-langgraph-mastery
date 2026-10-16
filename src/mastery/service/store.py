"""Durable service state: threads and their owners, runs, run events, idempotency keys, spend (Lesson 12.05).

The agent's own conversation state lives in the LangGraph **checkpointer**. Everything the service
adds around it lives here, so a restart (or a second worker) sees the same threads, owners,
finished runs, replayable streams and idempotency keys:

- :class:`MemoryStore`: dicts in this process (tests, notebooks, the 12.04 behaviour);
- :class:`SQLStore`: SQLite (``sqlite:///path/to/file.db``, one process) or Postgres
  (``postgresql://user:pass@host:5432/db``, many workers), same tables and SQL.

All methods are async. Use :func:`open_store` with a URL (or ``None`` for memory).
"""
from __future__ import annotations

import asyncio

import json
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mastery.service.runs import Event

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS svc_threads (
        thread_id TEXT PRIMARY KEY, owner TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS svc_threads_owner ON svc_threads (owner)",
    """CREATE TABLE IF NOT EXISTS svc_runs (
        run_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, user_id TEXT NOT NULL, status TEXT NOT NULL,
        data TEXT NOT NULL, updated_at DOUBLE PRECISION NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS svc_runs_thread ON svc_runs (thread_id)",
    """CREATE TABLE IF NOT EXISTS svc_events (
        run_id TEXT NOT NULL, seq INTEGER NOT NULL, event TEXT NOT NULL, data TEXT NOT NULL,
        PRIMARY KEY (run_id, seq))""",
    """CREATE TABLE IF NOT EXISTS svc_idempotency (
        user_id TEXT NOT NULL, key TEXT NOT NULL, run_id TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL,
        PRIMARY KEY (user_id, key))""",
    """CREATE TABLE IF NOT EXISTS svc_spend (
        day TEXT NOT NULL, user_id TEXT NOT NULL, usd DOUBLE PRECISION NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS svc_spend_day ON svc_spend (day)",
]


class MemoryStore:
    """In-process store: same interface as :class:`SQLStore`, gone when the process ends."""

    kind = "memory"

    def __init__(self) -> None:
        self.threads: dict[str, tuple[str, float]] = {}
        self.runs: dict[str, dict[str, Any]] = {}
        self.events: dict[str, list[Event]] = defaultdict(list)
        self.keys: dict[tuple[str, str], str] = {}
        self.spend: list[tuple[str, str, float]] = []

    async def setup(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def add_thread(self, thread_id: str, owner: str) -> None:
        self.threads[thread_id] = (owner, time.time())

    async def thread_owner(self, thread_id: str) -> str | None:
        found = self.threads.get(thread_id)
        return found[0] if found else None

    async def list_threads(self, owner: str) -> list[str]:
        return [t for t, (o, _) in sorted(self.threads.items(), key=lambda kv: kv[1][1]) if o == owner]

    async def delete_thread(self, thread_id: str) -> list[str]:
        self.threads.pop(thread_id, None)
        gone = [r for r, d in self.runs.items() if d["thread_id"] == thread_id]
        for run_id in gone:
            self.runs.pop(run_id, None)
            self.events.pop(run_id, None)
        self.keys = {k: v for k, v in self.keys.items() if v not in gone}
        return gone

    async def save_run(self, data: dict[str, Any]) -> None:
        self.runs[data["run_id"]] = dict(data)

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.runs.get(run_id)

    async def add_events(self, run_id: str, events: list[Event]) -> None:
        known = {e.id for e in self.events[run_id]}
        self.events[run_id].extend(e for e in events if e.id not in known)

    async def get_events(self, run_id: str, after: int = -1) -> list[Event]:
        return [e for e in self.events.get(run_id, []) if e.id > after]

    async def remember_key(self, user_id: str, key: str, run_id: str) -> None:
        self.keys.setdefault((user_id, key), run_id)

    async def run_for_key(self, user_id: str, key: str) -> str | None:
        return self.keys.get((user_id, key))

    async def add_spend(self, day: str, user_id: str, usd: float) -> None:
        self.spend.append((day, user_id, usd))

    async def spend_totals(self, day: str) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for d, user, usd in self.spend:
            if d == day:
                totals[user] += usd
        return dict(totals)

    async def orphans(self) -> list[dict[str, Any]]:
        return [d for d in self.runs.values() if d["status"] in {"queued", "running"}]

    async def ping(self) -> None:
        """Raise if the database can't answer (readiness checks, Lesson 12.06). Memory always answers."""


class SQLStore(MemoryStore):
    """SQLite or Postgres behind one set of queries (``?`` placeholders, converted for Postgres)."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.kind = "postgres" if url.startswith(("postgresql://", "postgres://")) else "sqlite"
        self._db: Any = None
        self._pool: Any = None

    async def setup(self) -> None:
        if self.kind == "sqlite":
            import aiosqlite

            # Autocommit + a busy timeout: the checkpointer writes to the same file on its own
            # connection, and a deferred transaction that has to upgrade to a write fails at once
            # ("database is locked") instead of waiting its turn.
            self._db = await aiosqlite.connect(self.url.removeprefix("sqlite:///"), timeout=30,
                                               isolation_level=None)
            await self._db.execute("PRAGMA journal_mode=WAL")     # readers don't block the writer
            await self._db.execute("PRAGMA busy_timeout=30000")
        else:
            from psycopg_pool import AsyncConnectionPool

            # autocommit: each statement is its own transaction, as the LangGraph Postgres saver expects.
            self._pool = AsyncConnectionPool(self.url, min_size=1, max_size=5, open=False,
                                             kwargs={"autocommit": True})
            await self._pool.open(wait=True, timeout=10)
        for statement in SCHEMA:
            await self._exec(statement)

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
        if self._pool is not None:
            await self._pool.close()

    async def _sqlite_write(self, call: Any) -> None:
        # SQLite allows one writer per file and can answer "database is locked" at once (even with a
        # busy timeout) when the checkpointer's connection holds the lock; back off and retry.
        import sqlite3

        for attempt in range(40):
            try:
                await call()
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc) or attempt == 39:
                    raise
                await asyncio.sleep(0.005 * (attempt + 1))

    async def _exec(self, sql: str, params: tuple = ()) -> None:
        if self.kind == "sqlite":
            await self._sqlite_write(lambda: self._db.execute(sql, params))
        else:
            async with self._pool.connection() as conn:
                await conn.execute(sql.replace("?", "%s"), params)

    async def _many(self, sql: str, rows: list[tuple]) -> None:
        if not rows:
            return
        if self.kind == "sqlite":
            await self._sqlite_write(lambda: self._db.executemany(sql, rows))
        else:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.executemany(sql.replace("?", "%s"), rows)

    async def _all(self, sql: str, params: tuple = ()) -> list[tuple]:
        if self.kind == "sqlite":
            async with self._db.execute(sql, params) as cur:
                return list(await cur.fetchall())
        async with self._pool.connection() as conn:
            cur = await conn.execute(sql.replace("?", "%s"), params)
            return list(await cur.fetchall())

    async def ping(self) -> None:
        await self._all("SELECT 1")

    async def add_thread(self, thread_id: str, owner: str) -> None:
        await self._exec("INSERT INTO svc_threads (thread_id, owner, created_at) VALUES (?, ?, ?)",
                         (thread_id, owner, time.time()))

    async def thread_owner(self, thread_id: str) -> str | None:
        rows = await self._all("SELECT owner FROM svc_threads WHERE thread_id = ?", (thread_id,))
        return rows[0][0] if rows else None

    async def list_threads(self, owner: str) -> list[str]:
        rows = await self._all("SELECT thread_id FROM svc_threads WHERE owner = ? ORDER BY created_at", (owner,))
        return [r[0] for r in rows]

    async def delete_thread(self, thread_id: str) -> list[str]:
        gone = [r[0] for r in await self._all("SELECT run_id FROM svc_runs WHERE thread_id = ?", (thread_id,))]
        for run_id in gone:
            await self._exec("DELETE FROM svc_events WHERE run_id = ?", (run_id,))
            await self._exec("DELETE FROM svc_idempotency WHERE run_id = ?", (run_id,))
        await self._exec("DELETE FROM svc_runs WHERE thread_id = ?", (thread_id,))
        await self._exec("DELETE FROM svc_threads WHERE thread_id = ?", (thread_id,))
        return gone

    async def save_run(self, data: dict[str, Any]) -> None:
        await self._exec(
            "INSERT INTO svc_runs (run_id, thread_id, user_id, status, data, updated_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (run_id) DO UPDATE SET status = excluded.status, data = excluded.data, updated_at = excluded.updated_at",
            (data["run_id"], data["thread_id"], data["user_id"], data["status"], json.dumps(data, default=str), time.time()))

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        rows = await self._all("SELECT data FROM svc_runs WHERE run_id = ?", (run_id,))
        return json.loads(rows[0][0]) if rows else None

    async def add_events(self, run_id: str, events: list[Event]) -> None:
        await self._many("INSERT INTO svc_events (run_id, seq, event, data) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                         [(run_id, e.id, e.event, json.dumps(e.data, default=str)) for e in events])

    async def get_events(self, run_id: str, after: int = -1) -> list[Event]:
        rows = await self._all("SELECT seq, event, data FROM svc_events WHERE run_id = ? AND seq > ? ORDER BY seq",
                               (run_id, after))
        return [Event(seq, event, json.loads(data)) for seq, event, data in rows]

    async def remember_key(self, user_id: str, key: str, run_id: str) -> None:
        await self._exec("INSERT INTO svc_idempotency (user_id, key, run_id, created_at) VALUES (?, ?, ?, ?) "
                         "ON CONFLICT DO NOTHING", (user_id, key, run_id, time.time()))

    async def run_for_key(self, user_id: str, key: str) -> str | None:
        rows = await self._all("SELECT run_id FROM svc_idempotency WHERE user_id = ? AND key = ?", (user_id, key))
        return rows[0][0] if rows else None

    async def add_spend(self, day: str, user_id: str, usd: float) -> None:
        await self._exec("INSERT INTO svc_spend (day, user_id, usd) VALUES (?, ?, ?)", (day, user_id, usd))

    async def spend_totals(self, day: str) -> dict[str, float]:
        rows = await self._all("SELECT user_id, SUM(usd) FROM svc_spend WHERE day = ? GROUP BY user_id", (day,))
        return {user: float(total) for user, total in rows}

    async def orphans(self) -> list[dict[str, Any]]:
        rows = await self._all("SELECT data FROM svc_runs WHERE status IN ('queued', 'running')")
        return [json.loads(r[0]) for r in rows]


@asynccontextmanager
async def open_store(url: str | None) -> AsyncIterator[MemoryStore]:
    """``None`` → :class:`MemoryStore`; ``sqlite:///…`` or ``postgresql://…`` → :class:`SQLStore`."""
    store = MemoryStore() if not url else SQLStore(url)
    await store.setup()
    try:
        yield store
    finally:
        await store.close()


@asynccontextmanager
async def open_checkpointer(url: str | None) -> AsyncIterator[Any]:
    """The LangGraph checkpointer that matches ``url``: in memory, SQLite or Postgres (tables created)."""
    if not url:
        from langgraph.checkpoint.memory import InMemorySaver

        yield InMemorySaver()
    elif url.startswith("sqlite:///"):
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with AsyncSqliteSaver.from_conn_string(url.removeprefix("sqlite:///")) as saver:
            await saver.conn.execute("PRAGMA busy_timeout=30000")    # share the file with the service store
            await saver.setup()
            yield saver
    else:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(url) as saver:
            await saver.setup()          # creates or migrates its tables; safe to call on every start
            yield saver
