"""Tests for mastery.tools (Module 02). Offline: no model, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.tools import ToolException

from mastery.tools import (
    CalculatorError, CsvTable, add_days, calculator, days_between, get_today, make_csv_lookup_tool,
    month_bounds, safe_eval, set_today,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPENSES = REPO_ROOT / "data" / "samples" / "expenses" / "expenses-2026.csv"


# --- calculator ---------------------------------------------------------------
@pytest.mark.parametrize(("expression", "expected"), [
    ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20), ("10 / 4", 2.5), ("7 // 2", 3), ("7 % 3", 1),
    ("2 ** 10", 1024), ("2 ^ 3", 8), ("-5 + +2", -3), ("1250.5 * 0.19", 237.595),
])
def test_safe_eval_does_arithmetic(expression: str, expected: float) -> None:
    assert safe_eval(expression) == pytest.approx(expected)


@pytest.mark.parametrize("expression", [
    "__import__('os').getcwd()", "open('x')", "a + 1", "'1' + '2'", "[1, 2]", "1 if True else 2",
    "(lambda: 1)()", "x.y",
])
def test_safe_eval_rejects_anything_but_arithmetic(expression: str) -> None:
    with pytest.raises(CalculatorError):
        safe_eval(expression)


@pytest.mark.parametrize("expression", ["", "1/0", "10 ** 1000", "9" * 300, "1e300 * 1e10",
                                        "1e300 ** 2", "1e200 ** 1.6", "(-8) ** 0.5"])
def test_safe_eval_rejects_bad_or_huge_input(expression: str) -> None:
    with pytest.raises(CalculatorError):
        safe_eval(expression)


def test_calculator_tool_returns_text_and_reports_errors_as_tool_messages() -> None:
    assert calculator.invoke({"expression": "0.1 + 0.2"}) == "0.3"
    message = calculator.invoke({"name": "calculator", "args": {"expression": "os.system('x')"}, "id": "c1",
                                 "type": "tool_call"})
    assert message.status == "error" and "Only numbers" in message.content


def test_calculator_overflow_is_a_tool_error_not_a_crash() -> None:
    message = calculator.invoke({"name": "calculator", "args": {"expression": "1e300 ** 2"}, "id": "c2",
                                 "type": "tool_call"})
    assert message.status == "error" and "safe range" in message.content


def test_calculator_schema_describes_the_argument_for_the_model() -> None:
    props = calculator.tool_call_schema.model_json_schema()["properties"]
    assert "description" in props["expression"]


# --- dates --------------------------------------------------------------------
def test_dates_with_a_frozen_today() -> None:
    set_today("2026-10-12")
    try:
        assert get_today.invoke({}) == "2026-10-12 (Monday)"
    finally:
        set_today(None)
    assert days_between.invoke({"start": "2026-10-12", "end": "2026-12-25"}) == 74
    assert days_between.invoke({"start": "2026-12-25", "end": "2026-10-12"}) == -74
    assert add_days.invoke({"start": "2026-02-27", "days": 2}) == "2026-03-01 (Sunday)"


def test_month_bounds_handles_short_months() -> None:
    first, last = month_bounds("2028-02")
    assert (first.isoformat(), last.isoformat()) == ("2028-02-01", "2028-02-29")
    with pytest.raises(ToolException):
        month_bounds("2026-13")


def test_bad_dates_become_error_messages_with_the_format() -> None:
    message = days_between.invoke({"name": "days_between", "args": {"start": "12/10/2026", "end": "2026-12-25"},
                                   "id": "d1", "type": "tool_call"})
    assert message.status == "error" and "YYYY-MM-DD" in message.content


# --- CSV lookup ---------------------------------------------------------------
def test_csv_table_loads_the_sample_and_filters(tmp_path: Path) -> None:
    table = CsvTable.from_path(EXPENSES)
    assert table.columns[:4] == ("date", "merchant", "category", "amount")
    assert len(table.rows) == 128
    assert {r["category"] for r in table.where("category", "HOUSING")} == {"housing"}
    assert table.where("merchant", "uber", contains=True)


def test_csv_table_reads_excel_files_with_a_bom(tmp_path: Path) -> None:
    path = tmp_path / "bom.csv"
    path.write_bytes("\ufeffname,city\nAna,Bogotá\n".encode())
    table = CsvTable.from_path(path)
    assert table.columns == ("name", "city") and table.rows[0]["city"] == "Bogotá"


def test_lookup_tool_limits_columns_and_rows() -> None:
    tool = make_csv_lookup_tool(CsvTable.from_path(EXPENSES), name="find_expenses", max_results=3)
    schema = tool.tool_call_schema.model_json_schema()
    assert "merchant" in json.dumps(schema)            # The column enum is visible to the model.
    message = tool.invoke({"name": "find_expenses", "args": {"column": "category", "value": "groceries"},
                           "id": "x1", "type": "tool_call"})
    payload = json.loads(message.content)
    assert payload["shown"] == 3 and payload["matches"] > 3 and "note" in payload
    assert len(message.artifact) == payload["matches"]   # Full result stays out of the context window.


def test_lookup_tool_rejects_unknown_columns_before_running() -> None:
    tool = make_csv_lookup_tool(CsvTable.from_path(EXPENSES))
    with pytest.raises(Exception, match="column"):
        tool.invoke({"column": "password", "value": "x"})
