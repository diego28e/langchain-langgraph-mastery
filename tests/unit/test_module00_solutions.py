"""Run Module 00 exercise solutions and teaching helpers straight from the notebooks.

The notebooks are the source of truth learners see, so these tests extract the code
from them (no copies that could drift) and execute it offline.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import nbformat

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "modules" / "00-foundations"


def _notebook(name: str) -> nbformat.NotebookNode:
    return nbformat.read(MODULE_DIR / name, as_version=4)


def _code_cell_containing(nb: nbformat.NotebookNode, marker: str) -> str:
    for cell in nb.cells:
        if cell.cell_type == "code" and marker in cell.source:
            return cell.source
    raise AssertionError(f"no code cell contains {marker!r}")


def test_jupyter_exercise_4_solution_counts_code_lines_from_the_raw_json() -> None:
    nb = _notebook("00-03-jupyter-fundamentals.ipynb")
    solutions = "\n".join(c.source for c in nb.cells if c.cell_type == "markdown" and "**4.**" in c.source)
    match = re.search(r"\*\*4\.\*\*.*?```python\n(.*?)```", solutions, re.S)
    assert match, "Exercise 4 solution block not found"
    # Same input the exercise uses: the raw JSON on disk, where `source` is a list of lines.
    raw = json.loads((MODULE_DIR / "00-03-jupyter-fundamentals.ipynb").read_text(encoding="utf-8"))
    result = eval(match.group(1).strip(), {"nb": raw})  # noqa: S307 - our own notebook text
    assert isinstance(result, int) and result > 0


def test_choose_provider_checks_data_terms_before_quality() -> None:
    nb = _notebook("00-07-provider-decision-framework.ipynb")
    source = _code_cell_containing(nb, "def choose_provider")
    namespace: dict = {}
    exec(source.split("\n\nprint(")[0], namespace)  # noqa: S102 - define the function only
    choose = namespace["choose_provider"]

    public = choose(sensitive_data=False, must_run_offline=False, needs_top_quality=False, monthly_budget_usd=0)
    assert "Groq free tier" in public
    no_budget = choose(sensitive_data=True, must_run_offline=False, needs_top_quality=False, monthly_budget_usd=0)
    assert "Ollama" in no_budget
    quality = choose(sensitive_data=False, must_run_offline=False, needs_top_quality=True, monthly_budget_usd=20)
    assert "frontier" in quality
    # The case that used to skip the data-terms branch: sensitive AND top quality AND a budget.
    both = choose(sensitive_data=True, must_run_offline=False, needs_top_quality=True, monthly_budget_usd=20)
    assert "frontier" in both and "exclude training" in both and "ZDR" in both
