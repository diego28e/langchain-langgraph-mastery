"""Date tools the model can trust more than its own guesses.

Models don't know today's date (their training data stops months before you
call them) and are unreliable at calendar arithmetic. These tools do it in
Python. All dates are ISO 8601 strings (``YYYY-MM-DD``): unambiguous for both
the model and your code ("03/04" is March 4 in the US and April 3 here).

``today`` can be injected (``set_today``) so tests and notebooks are reproducible.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from langchain_core.tools import ToolException, tool

__all__ = [
    "add_days", "days_between", "get_today", "month_bounds", "parse_date", "parse_month", "set_today",
    "DATE_TOOLS",
]

_FIXED_TODAY: date | None = None


def set_today(value: date | str | None) -> None:
    """Freeze "today" (for tests and reproducible notebooks); ``None`` = real clock."""
    global _FIXED_TODAY
    _FIXED_TODAY = parse_date(value) if isinstance(value, str) else value


def today() -> date:
    """The local date of this computer (or the frozen one)."""
    return _FIXED_TODAY or date.today()


def parse_date(value: str) -> date:
    """Parse ``YYYY-MM-DD`` or raise a ``ToolException`` that tells the model the format."""
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ToolException(f"Invalid date {value!r}. Use ISO format YYYY-MM-DD, e.g. 2026-10-12.") from exc


def parse_month(value: str) -> tuple[int, int]:
    """Parse ``YYYY-MM`` into ``(year, month)``."""
    text = str(value).strip()
    try:
        year, month = (int(part) for part in text.split("-"))
        if not 1 <= month <= 12 or len(text) != 7:
            raise ValueError
    except ValueError as exc:
        raise ToolException(f"Invalid month {value!r}. Use YYYY-MM, e.g. 2026-09.") from exc
    return year, month


def month_bounds(value: str) -> tuple[date, date]:
    """First and last day of a ``YYYY-MM`` month."""
    year, month = parse_month(value)
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


@tool
def get_today() -> str:
    """Return today's date (YYYY-MM-DD) and weekday. Call this before any question about 'today', 'this month' or 'last week'."""
    now = today()
    return f"{now.isoformat()} ({now.strftime('%A')})"


@tool(parse_docstring=True)
def days_between(start: str, end: str) -> int:
    """Count the days from start to end (negative if end is before start).

    Args:
        start: First date, YYYY-MM-DD.
        end: Second date, YYYY-MM-DD.
    """
    return (parse_date(end) - parse_date(start)).days


@tool(parse_docstring=True)
def add_days(start: str, days: int) -> str:
    """Return the date that is `days` days after start (use a negative number to go back).

    Args:
        start: Starting date, YYYY-MM-DD.
        days: Number of days to add, between -36500 and 36500.
    """
    if abs(days) > 36_500:
        raise ToolException("days must be between -36500 and 36500.")
    result = parse_date(start) + timedelta(days=days)
    return f"{result.isoformat()} ({result.strftime('%A')})"


for _t in (get_today, days_between, add_days):
    _t.handle_tool_error = True   # ToolException -> error ToolMessage (the model can fix its input).

DATE_TOOLS = [get_today, days_between, add_days]
