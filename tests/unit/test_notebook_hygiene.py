"""Repository hygiene checks for every committed notebook (CONVENTIONS.md §3 and §6).

Fails if a notebook is not valid nbformat JSON, still contains outputs or
execution counts, or contains something that looks like a real API key.
No network, no kernel: notebooks are read as files, never executed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = sorted(
    p for p in REPO_ROOT.glob("modules/**/*.ipynb") if ".ipynb_checkpoints" not in p.parts
)

# Shapes of real provider keys. Fake keys in the course always contain "FAKE".
SECRET_PATTERNS = [
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),  # Groq
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),  # OpenAI
    re.compile(r"lsv2_[A-Za-z0-9_]{20,}"),  # LangSmith
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),  # Google
    re.compile(r"tvly-[A-Za-z0-9]{20,}"),  # Tavily
    re.compile(r"hf_[A-Za-z0-9]{30,}"),  # Hugging Face
]


def _ids(paths: list[Path]) -> list[str]:
    return [str(p.relative_to(REPO_ROOT)) for p in paths]


def test_there_are_notebooks_to_check() -> None:
    assert NOTEBOOKS, "No notebooks found under modules/"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=_ids(NOTEBOOKS))
def test_notebook_is_valid_nbformat(path: Path) -> None:
    nbformat = pytest.importorskip("nbformat")
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=_ids(NOTEBOOKS))
def test_notebook_outputs_are_cleared(path: Path) -> None:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    dirty = [
        index
        for index, cell in enumerate(notebook["cells"])
        if cell["cell_type"] == "code" and (cell.get("outputs") or cell.get("execution_count") is not None)
    ]
    assert not dirty, f"Clear outputs before committing (cells {dirty}). See CONVENTIONS.md §6."


@pytest.mark.parametrize("path", NOTEBOOKS, ids=_ids(NOTEBOOKS))
def test_notebook_contains_no_real_secrets(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            assert "FAKE" in match.group(0).upper(), f"Possible real secret in {path.name}: {match.group(0)[:8]}…"


_HELP_LINE = re.compile(r"^\s*[\w.]+\?\??\s*$")
_ALLOWED = {"display", "get_ipython", "__file__"}


def _bound_and_loaded(source: str) -> tuple[set[str], set[str]]:
    import ast

    lines = [ln for ln in source.splitlines() if not ln.lstrip().startswith(("%", "!")) and not _HELP_LINE.match(ln)]
    tree = compile("\n".join(lines), "<cell>", "exec", ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    bound, loaded = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            (loaded if isinstance(node.ctx, ast.Load) else bound).add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bound.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
    return bound, loaded


@pytest.mark.parametrize("path", NOTEBOOKS, ids=_ids(NOTEBOOKS))
def test_notebook_has_no_undefined_names(path: Path) -> None:
    """Every name a code cell reads is defined in that cell or an earlier one (Run All would hit a NameError)."""
    import builtins

    known = set(dir(builtins)) | _ALLOWED
    problems = []
    for index, cell in enumerate(json.loads(path.read_text(encoding="utf-8"))["cells"]):
        if cell["cell_type"] != "code":
            continue
        bound, loaded = _bound_and_loaded("".join(cell["source"]))
        known |= bound
        problems += [f"cell {index}: {name}" for name in sorted(loaded - known)]
    assert not problems, problems
