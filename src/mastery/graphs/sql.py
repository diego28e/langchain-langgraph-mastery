"""Small, safe SQLite helpers for the Lesson 07.07 SQL agent graph (no ``langchain-community``).

The model writes SQL; this module makes sure that SQL can only **read**: connections are opened
read-only (``mode=ro``), an authorizer denies every write/DDL/PRAGMA action, only one ``SELECT``/``WITH``
statement is accepted, and results are capped.
"""

from __future__ import annotations

import csv
import re
import sqlite3
import time
from pathlib import Path

__all__ = ["check_sql", "list_tables", "run_readonly_query", "sqlite_from_csv", "table_schema"]

_ALLOWED = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}


def sqlite_from_csv(csv_path: Path, db_path: Path, table: str) -> Path:
    """(Re)create ``db_path`` with one table loaded from a UTF-8 CSV. Numeric-looking columns become REAL."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError(f"bad table name: {table!r}")
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"{csv_path} has no rows")
    cols = list(rows[0])

    def numeric(col: str) -> bool:
        try:
            [float(r[col]) for r in rows]
            return True
        except ValueError:
            return False

    types = {c: "REAL" if numeric(c) else "TEXT" for c in cols}
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute(f"CREATE TABLE {table} (" + ", ".join(f'"{c}" {types[c]}' for c in cols) + ")")
        con.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' * len(cols))})",
                        [[float(r[c]) if types[c] == "REAL" else r[c] for c in cols] for r in rows])
    con.close()
    return db_path


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
    con.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in _ALLOWED else sqlite3.SQLITE_DENY)
    return con


def list_tables(db_path: Path) -> list[str]:
    con = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
    try:
        return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    finally:
        con.close()


def table_schema(db_path: Path, tables: list[str], sample_rows: int = 3) -> str:
    """``CREATE TABLE`` statements plus a few sample rows: what the model needs to write a query."""
    known = set(list_tables(db_path))
    con = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
    out = []
    try:
        for name in tables:
            if name not in known:
                out.append(f"-- unknown table: {name}")
                continue
            (ddl,) = con.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
            rows = con.execute(f'SELECT * FROM "{name}" LIMIT ?', (sample_rows,)).fetchall()
            out.append(ddl + ";\n/* sample rows:\n" + "\n".join(map(str, rows)) + "\n*/")
    finally:
        con.close()
    return "\n\n".join(out)


def check_sql(sql: str, max_rows: int = 50) -> tuple[bool, str]:
    """Static checks before running model-written SQL. Returns ``(ok, sql_or_reason)``.

    One statement, starting with SELECT or WITH; adds ``LIMIT max_rows`` when missing. A query that
    already ends in ``LIMIT n``, or has another LIMIT form (``LIMIT a OFFSET b``, ``LIMIT a, b``) or a
    ``--`` comment, is wrapped as ``SELECT * FROM (<query>) LIMIT max_rows`` instead of appended to.
    """
    text = sql.strip().rstrip(";").strip()
    text = re.sub(r"^```(?:sql)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    if not text:
        return False, "empty query"
    if ";" in text:
        return False, "only one statement is allowed"
    if not re.match(r"(?is)^(select|with)\b", text):
        return False, "only SELECT queries are allowed"
    if re.search(r"(?i)\blimit\s+\d+\s*$", text):
        return True, text
    if re.search(r"(?i)\blimit\b", text) or "--" in text:
        return True, f"SELECT * FROM (\n{text}\n) LIMIT {max_rows}"
    return True, text + f" LIMIT {max_rows}"


def run_readonly_query(db_path: Path, sql: str, max_rows: int = 50, timeout_s: float = 5.0) -> str:
    """Run one checked query on a read-only connection. Errors come back as text for the model to fix.

    A query running longer than ``timeout_s`` is interrupted (``Error: interrupted``), so a runaway
    join can't block the graph.
    """
    ok, checked = check_sql(sql, max_rows)
    if not ok:
        return f"Error: {checked}"
    con = _connect(db_path)
    deadline = time.monotonic() + timeout_s
    con.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
    try:
        cur = con.execute(checked)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(max_rows)
    except sqlite3.Error as exc:
        return f"Error: {exc}"
    finally:
        con.close()
    return " | ".join(cols) + "\n" + "\n".join(" | ".join(map(str, r)) for r in rows)
