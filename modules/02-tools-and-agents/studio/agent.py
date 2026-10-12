"""Tiny agent app for Lesson 02.07 (LangSmith Studio, first look).

Run from this folder, in the course environment:

    langgraph dev

`langgraph dev` imports this file and serves the graph named in
langgraph.json ("finance_agent"). It reads keys from the repo's .env
(see "env" in langgraph.json). The `mastery` package must be installed
in the same environment (`pip install -e ".[dev]"` from the repo root).
"""

from __future__ import annotations

from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware

from mastery.config import find_repo_root
from mastery.models import get_model
from mastery.tools import CsvTable, add_days, calculator, days_between, get_today, make_csv_lookup_tool

REPO_ROOT = find_repo_root(Path(__file__).resolve().parent)
EXPENSES = CsvTable.from_path(REPO_ROOT / "data" / "samples" / "expenses" / "expenses-2026.csv")

find_expenses = make_csv_lookup_tool(
    EXPENSES,
    name="find_expenses",
    description=(
        "Find rows in MY expense log (Jul-Sep 2026, amounts in COP). Filter one column, e.g. "
        "column='category', value='groceries', or column='date', value='2026-09', contains=true."
    ),
    max_results=20,
)

SYSTEM_PROMPT = (
    "You are a personal-finance assistant for the user's own expense log. "
    "Use find_expenses to look up rows and the calculator for ALL arithmetic; never compute in your head. "
    "Use the date tools for dates. If a question is not about the user's expenses, say so briefly. "
    "Answer in at most three sentences and mention the numbers you used."
)

agent = create_agent(
    get_model("fast", temperature=0, reasoning_effort="low"),
    tools=[find_expenses, calculator, days_between, add_days, get_today],
    system_prompt=SYSTEM_PROMPT,
    middleware=[ModelCallLimitMiddleware(run_limit=8, exit_behavior="end")],
    name="finance_agent",
)
