"""Read-only lookups in ONE CSV file the developer chose.

The security idea (Lesson 02.01 and 02.04): the *developer* decides which file
a tool may read when the tool is built; the *model* only chooses a column and a
value. A tool like ``read_file(path)`` would let a prompt injection read any
file on your disk.

>>> table = CsvTable.from_path("data/samples/expenses/expenses-2026.csv")  # doctest: +SKIP
>>> lookup = make_csv_lookup_tool(table, name="find_expenses",
...     description="Find expense rows by column value.")                    # doctest: +SKIP

Uses only the standard library (no pandas needed). Files are read as
``utf-8-sig`` so CSVs saved by Excel on Windows (with a BOM) work too.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from pydantic import BaseModel, Field, create_model

__all__ = ["CsvTable", "make_csv_lookup_tool"]


@dataclass(frozen=True)
class CsvTable:
    """An in-memory, read-only CSV table."""

    name: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, str], ...]

    @classmethod
    def from_path(cls, path: str | Path, *, max_rows: int = 50_000) -> CsvTable:
        """Load a CSV with a header row.

        Raises:
            FileNotFoundError: The file does not exist (checked by the developer, not the model).
            ValueError: No header, or more than ``max_rows`` rows.
        """
        path = Path(path)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError(f"{path.name} has no header row.")
            rows = []
            for row in reader:
                rows.append({k.strip(): (v or "").strip() for k, v in row.items() if k})
                if len(rows) > max_rows:
                    raise ValueError(f"{path.name} has more than {max_rows} rows.")
        return cls(name=path.name, columns=tuple(c.strip() for c in reader.fieldnames), rows=tuple(rows))

    def where(self, column: str, value: str, *, contains: bool = False) -> list[dict[str, str]]:
        """Rows where ``column`` equals ``value`` (case-insensitive), or contains it."""
        if column not in self.columns:
            raise ToolException(f"Unknown column {column!r}. Valid columns: {', '.join(self.columns)}.")
        needle = value.strip().lower()
        if contains:
            return [r for r in self.rows if needle in r.get(column, "").lower()]
        return [r for r in self.rows if r.get(column, "").lower() == needle]


def make_csv_lookup_tool(
    table: CsvTable,
    *,
    name: str = "lookup_rows",
    description: str | None = None,
    max_results: int = 20,
) -> BaseTool:
    """Build a tool that finds rows in ``table`` (and nothing else).

    The model sees ``column`` as an *enum* of the real column names, so it
    cannot invent columns, and results are capped at ``max_results`` rows to
    protect the context window. The full match list is attached as the tool
    message ``artifact`` (your code can use it; the model never sees it).
    """
    column_type = Literal[table.columns]  # type: ignore[valid-type]
    args_schema: type[BaseModel] = create_model(
        f"{name}_args",
        column=(column_type, Field(description="Column to search.")),
        value=(str, Field(description="Value to look for (case-insensitive).")),
        contains=(bool, Field(default=False, description="True = substring match, False = exact match.")),
    )

    def _lookup(column: str, value: str, contains: bool = False) -> tuple[str, list[dict[str, Any]]]:
        matches = table.where(column, value, contains=contains)
        shown = matches[:max_results]
        summary = {"file": table.name, "matches": len(matches), "shown": len(shown), "rows": shown}
        if len(matches) > max_results:
            summary["note"] = f"Only the first {max_results} rows are shown. Narrow the search."
        return json.dumps(summary, ensure_ascii=False), matches

    tool = StructuredTool.from_function(
        func=_lookup,
        name=name,
        description=description or (
            f"Find rows in {table.name} where a column matches a value. Columns: {', '.join(table.columns)}."
        ),
        args_schema=args_schema,
        response_format="content_and_artifact",
    )
    tool.handle_tool_error = True
    return tool
