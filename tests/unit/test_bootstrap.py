"""Notebook setup cells import `mastery` from THIS clone's src/, exactly like pytest does.

Every lesson that uses the course package starts with a setup cell that finds the repo root and
imports `mastery`. If the environment was installed (``pip install -e``) from another copy of
the repo, a plain ``import mastery`` would quietly run that other copy's code in the notebooks,
while ``pytest`` (``pythonpath = ["src"]`` in pyproject.toml) tests this one. So the setup cell
puts this clone's ``src/`` first, prints where `mastery` came from, and warns, with the exact
fix, when the environment's own install points somewhere else.

These tests run the real setup cell, taken from the generated notebooks, in a separate Python
process. The "other clone" is a tiny fake package in a temporary folder: no network, no keys.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = (REPO_ROOT / "src").resolve()
MARKER = "Find the repository root"  # First comment line of every setup cell.
FIX = 'python -m pip install -e ".[dev]"'
USES_MASTERY = re.compile(r"^\s*(from|import) mastery\b", re.MULTILINE)

NOTEBOOKS = sorted(
    p for p in REPO_ROOT.glob("modules/[0-9][0-9]-*/**/*.ipynb") if ".ipynb_checkpoints" not in p.parts
)


def _code_cells(path: Path) -> list[str]:
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    return ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]


def _setup_cell_index(codes: list[str]) -> int | None:
    return next((i for i, source in enumerate(codes) if MARKER in source), None)


SETUP_CELLS = {
    path: codes[index]
    for path in NOTEBOOKS
    if (index := _setup_cell_index(codes := _code_cells(path))) is not None
}
# One sample notebook per distinct setup-cell program (comments and layout ignored): Module 00
# has its own, more commented version; Modules 01+ share one. Each version is run below.
_by_program: dict[str, tuple[Path, str]] = {}
for _path, _source in SETUP_CELLS.items():
    _by_program.setdefault(ast.dump(ast.parse(_source)), (_path, _source))
SAMPLES = list(_by_program.values())


def _sample_ids() -> list[str]:
    return [str(path.relative_to(REPO_ROOT)) for path, _ in SAMPLES]


@pytest.fixture
def other_clone(tmp_path: Path) -> Path:
    """A fake second copy of the course: <tmp>/other-clone/src/mastery with version 9.9.9."""
    package = tmp_path / "other-clone" / "src" / "mastery"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('__version__ = "9.9.9"\n', encoding="utf-8")
    return package.parent


def _run_setup_cell(notebook: Path, source: str, pythonpath: Path, tmp_path: Path, before: str = "") -> str:
    """Run ``before`` + the setup cell as a script, from the notebook's folder (like Jupyter does)."""
    probe = "\nprint('LOADED=' + str(Path(mastery.__file__).resolve()))\n"
    script = tmp_path / "setup_cell.py"
    script.write_text(before + source + probe, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(pythonpath), "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, str(script)], cwd=notebook.parent, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _loaded_from(output: str) -> Path:
    line = next(line for line in output.splitlines() if line.startswith("LOADED="))
    return Path(line.removeprefix("LOADED="))


def test_setup_cells_were_found() -> None:
    modules = {path.relative_to(REPO_ROOT / "modules").parts[0][:2] for path in SETUP_CELLS}
    assert {"00", "01"} <= modules, f"setup cells found only in modules {sorted(modules)}"
    assert SAMPLES


@pytest.mark.parametrize("path", NOTEBOOKS, ids=[str(p.relative_to(REPO_ROOT)) for p in NOTEBOOKS])
def test_setup_cell_runs_before_the_first_mastery_import(path: Path) -> None:
    codes = _code_cells(path)
    setup = _setup_cell_index(codes)
    first_use = next((i for i, source in enumerate(codes) if i != setup and USES_MASTERY.search(source)), None)
    if first_use is not None:
        assert setup is not None and setup < first_use, f"code cell {first_use} imports mastery before the setup cell"


def test_modules_01_onward_share_one_setup_cell() -> None:
    programs = {
        ast.dump(ast.parse(source))
        for path, source in SETUP_CELLS.items()
        if not path.relative_to(REPO_ROOT / "modules").parts[0].startswith("00-")
    }
    assert len(programs) == 1, "keep one setup cell for Modules 01+ (each module's common.py BOOTSTRAP)"


@pytest.mark.parametrize(("notebook", "source"), SAMPLES, ids=_sample_ids())
def test_setup_cell_uses_this_clone_and_warns_about_another_install(
    notebook: Path, source: str, other_clone: Path, tmp_path: Path
) -> None:
    output = _run_setup_cell(notebook, source, pythonpath=other_clone, tmp_path=tmp_path)

    assert _loaded_from(output).is_relative_to(SRC_DIR)  # This clone's code, not the other copy.
    assert "9.9.9" not in output
    assert "⚠️" in output
    assert str(other_clone / "mastery") in output  # The warning names where the install points.
    assert FIX in output


@pytest.mark.parametrize(("notebook", "source"), SAMPLES, ids=_sample_ids())
def test_setup_cell_is_quiet_when_the_install_is_this_clone(notebook: Path, source: str, tmp_path: Path) -> None:
    output = _run_setup_cell(notebook, source, pythonpath=SRC_DIR, tmp_path=tmp_path)

    assert _loaded_from(output).is_relative_to(SRC_DIR)
    assert "⚠️" not in output
    assert str(SRC_DIR / "mastery" / "__init__.py") in output  # It always shows where mastery came from.


@pytest.mark.parametrize(("notebook", "source"), SAMPLES, ids=_sample_ids())
def test_setup_cell_asks_for_a_restart_when_another_mastery_is_already_loaded(
    notebook: Path, source: str, other_clone: Path, tmp_path: Path
) -> None:
    # Simulates a kernel that imported the other copy before the setup cell ran.
    before = f"import sys\nsys.path.insert(0, {str(other_clone)!r})\nimport mastery\nsys.path.pop(0)\n"
    output = _run_setup_cell(notebook, source, pythonpath=SRC_DIR, tmp_path=tmp_path, before=before)

    assert "already imported" in output
    assert "restart" in output.lower()
