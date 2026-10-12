"""mastery.tools: reusable, tested tools for agents (Module 02).

| Tool / helper | Module | Why it is a tool |
|---|---|---|
| ``calculator`` / ``safe_eval`` | ``calculator.py`` | Models are bad at exact arithmetic; ``eval`` is unsafe |
| ``get_today``, ``days_between``, ``add_days`` | ``dates.py`` | Models don't know today's date and miscount days |
| ``CsvTable``, ``make_csv_lookup_tool`` | ``csv_lookup.py`` | Read-only lookups in ONE developer-chosen file |

Every tool has a docstring written for the model, typed arguments, and
``handle_tool_error=True`` so bad input becomes an error message the model can
fix, instead of a crash. Unit tests: ``tests/unit/test_tools.py``.
"""

from mastery.tools.calculator import CalculatorError, calculator, safe_eval
from mastery.tools.csv_lookup import CsvTable, make_csv_lookup_tool
from mastery.tools.dates import DATE_TOOLS, add_days, days_between, get_today, month_bounds, set_today

__all__ = [
    "DATE_TOOLS",
    "CalculatorError",
    "CsvTable",
    "add_days",
    "calculator",
    "days_between",
    "get_today",
    "make_csv_lookup_tool",
    "month_bounds",
    "safe_eval",
    "set_today",
]
