"""Structure checks for lesson and project notebooks (CONVENTIONS.md §3).

Applies to Module 01 onwards (Module 00 predates some of these sections).
Notebooks are read as files, never executed: no kernel, no network.
"""

from __future__ import annotations

import re
from pathlib import Path

import nbformat
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIRST_CHECKED_MODULE = 1

# Lesson notebooks: modules/NN-*/NN-LL-*.ipynb
LESSONS = sorted(
    p for p in REPO_ROOT.glob("modules/*/[0-9][0-9]-[0-9][0-9]-*.ipynb")
    if int(p.name[:2]) >= FIRST_CHECKED_MODULE
)
# Project notebooks: starter and reference solution.
PROJECTS = sorted(
    p for p in REPO_ROOT.glob("modules/*/project/**/*.ipynb")
    if int(p.name[:2]) >= FIRST_CHECKED_MODULE and ".ipynb_checkpoints" not in p.parts
)

LESSON_SECTIONS = (
    "Learning objectives",
    "Official reading",
    "What just happened",
    "Pitfalls",
    "Production note",
    "Exercises",
    "Checkpoint",
    "Research checkpoint",
    "Summary",
)
# A model call in a code cell, e.g. llm.invoke(...), model.stream(...), chain.batch(...).
# Module 02 adds agents (agent.invoke, finance_agent.stream_events, bound.invoke ...).
MODEL_CALL = re.compile(
    r"\b(llm|model|chain|structured|streamer|thinker|primary|backup|agent|bound|searcher|\w+_agent)\w*"
    r"\.(a?invoke|a?stream|a?batch|a?stream_events)\("
)


def _ids(paths: list[Path]) -> list[str]:
    return [str(p.relative_to(REPO_ROOT)) for p in paths]


def _markdown(path: Path) -> str:
    nb = nbformat.read(path, as_version=4)
    return "\n".join(c.source for c in nb.cells if c.cell_type == "markdown")


def test_there_are_module_01_notebooks() -> None:
    assert len(LESSONS) >= 8
    assert len(PROJECTS) >= 2


@pytest.mark.parametrize("path", LESSONS, ids=_ids(LESSONS))
def test_lesson_has_every_template_section(path: Path) -> None:
    text = _markdown(path)
    missing = [section for section in LESSON_SECTIONS if section not in text]
    assert not missing, f"{path.name} is missing sections: {missing}"


@pytest.mark.parametrize("path", LESSONS + PROJECTS, ids=_ids(LESSONS + PROJECTS))
def test_title_cell_states_docs_verified_date(path: Path) -> None:
    first = nbformat.read(path, as_version=4).cells[0]
    assert first.cell_type == "markdown" and first.source.startswith("# ")
    assert re.search(r"Docs verified \| \d{4}-\d{2}-\d{2}", first.source), "title table needs 'Docs verified | YYYY-MM-DD'"


@pytest.mark.parametrize("path", LESSONS + PROJECTS, ids=_ids(LESSONS + PROJECTS))
def test_live_model_calls_are_guarded_by_a_key_flag(path: Path) -> None:
    """A code cell that calls a real model must check HAVE_*_KEY / LIVE, or be marked offline (🧪)."""
    nb = nbformat.read(path, as_version=4)
    for index, cell in enumerate(nb.cells):
        if cell.cell_type != "code" or not MODEL_CALL.search(cell.source):
            continue
        first_line = cell.source.lstrip().splitlines()[0]
        guarded = re.search(r"HAVE_\w+_KEY|\bLIVE\b|RUN_STRETCH", cell.source) is not None
        offline = first_line.startswith("# 🧪")
        assert guarded or offline, f"cell {index} calls a model without a key flag or a '# 🧪' marker"
