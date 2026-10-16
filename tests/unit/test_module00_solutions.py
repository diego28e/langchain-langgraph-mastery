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


def _project_namespace(fail_model: str | None = None) -> dict:
    """Run the Project 00 solution's config, grader, run, loop, summary and decision cells offline."""
    import pandas as pd
    from langchain_core.messages import AIMessage

    answers = {
        "factual": "LangGraph provides a framework for stateful agent workflows.",
        "reasoning": "Yes, 6,000 is under 8,000.",
        "creative": "Read the docs,\nsave the day.",
    }

    class FakeModel:
        def __init__(self, model_id: str) -> None:
            self.model_id = model_id

        def invoke(self, prompt: str) -> AIMessage:
            if self.model_id == fail_model:
                raise RuntimeError("model_decommissioned")
            __import__("time").sleep(0.02)   # client latency > server completion_time
            task = next(t for t, p in ns["PROMPTS"].items() if p == prompt)
            return AIMessage(
                content=answers[task],
                usage_metadata={"input_tokens": 40, "output_tokens": 20, "total_tokens": 60},
                response_metadata={"finish_reason": "stop",
                                   "token_usage": {"completion_time": 0.01, "queue_time": None}},
            )

    class Settings:
        model_fast, model_reasoning = "A", "B"

    nb = nbformat.read(MODULE_DIR / "project" / "solutions" / "00-project-groq-model-explorer-solution.ipynb", as_version=4)
    ns: dict = {
        "re": re, "pd": pd, "time": __import__("time"), "settings": Settings(), "HAVE_GROQ_KEY": True,
        "display": lambda *a, **k: None, "Markdown": str,
        "init_chat_model": lambda model, **kwargs: FakeModel(model.split(":", 1)[1]),
    }
    for marker in ("MODELS_TO_COMPARE =", "CANNED = [", "def run_prompt", "def wait_for_token_budget",
                   "Per-model summary", "best_line ="):
        exec(_code_cell_containing(nb, marker), ns)  # noqa: S102 - our own notebook code
        ns["TPM_BUDGET"] = 10**9   # no pacing sleeps in a unit test
    return ns


def test_project00_graders_and_repeats_offline(capsys) -> None:
    ns = _project_namespace()
    out = capsys.readouterr().out
    assert "❌" not in out
    df = ns["results_df"]
    assert len(df) == 2 * 3 * ns["REPEATS"] and df["passed"].all()
    assert {"server_completion_s", "queue_s"} <= set(df.columns)
    assert (ns["summary"]["p50_server_tokens_per_s"] > ns["summary"]["p50_e2e_tokens_per_s"]).all()


def test_project00_decision_never_names_a_model_that_always_failed(capsys) -> None:
    ns = _project_namespace(fail_model="B")
    out = capsys.readouterr().out
    assert "B: 9/9 calls failed -> not a candidate" in out
    assert "A had the lowest median latency" in ns["best_line"]
