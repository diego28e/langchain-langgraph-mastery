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
    programs = {  # Only prepare_runtime's arguments differ: each lesson's own keys and file name (colab_patch.py).
        ast.dump(ast.parse(re.sub(r", secrets=\([^)]*\),\s*notebook=\"[^\"]*\"", "", source)))
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


# --- Google Colab (docs/COLAB.md) ---------------------------------------------------------------
# A fake ``google.colab`` records drive.mount(); a fake ``mastery.colab`` records prepare_runtime(),
# so nothing is mounted or installed. COLAB_RELEASE_TAG is how the setup cell detects Colab.
FAKE_COLAB = '''
import sys, types
_google = sys.modules.setdefault("google", types.ModuleType("google"))
_colab = types.ModuleType("google.colab")
_colab.drive = types.SimpleNamespace(mount=lambda path: print("MOUNTED", path))
sys.modules["google.colab"] = _google.colab = _colab
_fake = types.ModuleType("mastery.colab")
_fake.prepare_runtime = lambda root, **kwargs: print("PREPARED", root)
_fake.API_LEVEL = 99  # as new as any setup cell asks for
sys.modules["mastery.colab"] = _fake
import time
time.sleep = lambda seconds: print("WAITED", seconds)  # The Drive-lag retry: no real waiting in tests.
'''
COLAB_CLONES = [Path(d) / "langchain-langgraph-mastery" for d in ("/content/drive/MyDrive", "/content")]


def _run_on_fake_colab(source: str, cwd: Path, tmp_path: Path, **env: str) -> subprocess.CompletedProcess[str]:
    script = tmp_path / "colab_setup_cell.py"
    script.write_text(FAKE_COLAB + source, encoding="utf-8")
    run_env = {k: v for k, v in os.environ.items() if k != "LC_MASTERY_ROOT"}
    run_env.update(PYTHONPATH=str(SRC_DIR), PYTHONIOENCODING="utf-8", COLAB_RELEASE_TAG="test", **env)
    return subprocess.run(
        [sys.executable, str(script)], cwd=cwd, env=run_env,
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )


@pytest.mark.parametrize(("notebook", "source"), SAMPLES, ids=_sample_ids())
def test_on_colab_without_a_clone_it_mounts_drive_and_points_to_start_here(
    notebook: Path, source: str, tmp_path: Path
) -> None:
    if any(p.is_dir() for p in COLAB_CLONES):
        pytest.skip("a real Colab clone exists on this machine")
    result = _run_on_fake_colab(source, cwd=tmp_path, tmp_path=tmp_path)

    assert result.returncode != 0
    assert "MOUNTED /content/drive" in result.stdout
    assert result.stdout.count("WAITED") == 30  # gave Drive ~30 s to show the clone before giving up
    assert "FileNotFoundError" in result.stderr and "colab/START_HERE.ipynb" in result.stderr
    assert "wait a minute" in result.stderr


@pytest.mark.parametrize(("notebook", "source"), SAMPLES[:3], ids=_sample_ids()[:3])
def test_on_colab_it_waits_for_a_clone_drive_shows_late(notebook: Path, source: str, tmp_path: Path) -> None:
    """Drive lag: the clone appears in MyDrive only after a few seconds; the setup cell waits for it."""
    drive = tmp_path / "MyDrive"
    drive.mkdir()
    late = f"""
_sleeps = []
def _sleep(seconds):
    _sleeps.append(seconds)
    if len(_sleeps) == 3:
        import os
        os.symlink({str(REPO_ROOT)!r}, {str(drive / "langchain-langgraph-mastery")!r}, target_is_directory=True)
time.sleep = _sleep
"""
    work = tmp_path / "work"
    work.mkdir()
    try:
        (tmp_path / "probe").symlink_to(REPO_ROOT, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not allowed here (Windows without developer mode)")
    result = _run_on_fake_colab(late + source.replace('"/content/drive/MyDrive"', repr(str(drive)).replace("'", '"')),
                                cwd=work, tmp_path=tmp_path)

    assert result.returncode == 0, result.stderr
    assert f"PREPARED {drive / 'langchain-langgraph-mastery'}" in result.stdout


@pytest.mark.parametrize(("notebook", "source"), SAMPLES, ids=_sample_ids())
def test_on_colab_with_a_clone_it_prepares_the_runtime(notebook: Path, source: str, tmp_path: Path) -> None:
    result = _run_on_fake_colab(source, cwd=notebook.parent, tmp_path=tmp_path)

    assert result.returncode == 0, result.stderr
    assert f"PREPARED {REPO_ROOT}" in result.stdout
    assert "⚠️" not in result.stdout


@pytest.mark.parametrize(("notebook", "source"), SAMPLES, ids=_sample_ids())
def test_off_colab_the_setup_cell_never_touches_colab(notebook: Path, source: str, tmp_path: Path) -> None:
    script = tmp_path / "local_setup_cell.py"
    script.write_text(FAKE_COLAB.replace('sys.modules["google.colab"] = _google.colab = _colab', "") + source, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("COLAB_RELEASE_TAG", "LC_MASTERY_ROOT")}
    env.update(PYTHONPATH=str(SRC_DIR), PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, str(script)], cwd=notebook.parent, env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=120)

    assert result.returncode == 0, result.stderr
    assert "MOUNTED" not in result.stdout and "PREPARED" not in result.stdout


# --- An older mastery on Colab ("prepare_runtime() got an unexpected keyword argument 'secrets'") --------
# No fake mastery.colab here: the setup cell imports a tiny fake clone's own src/mastery/colab.py.
COLAB_ONLY = FAKE_COLAB.split("_fake = ")[0] + FAKE_COLAB[FAKE_COLAB.index("import time"):]
NEW_COLAB = 'API_LEVEL = 99\ndef prepare_runtime(repo_root, **options):\n    print("NEW PREPARED", sorted(options))\n'
OLD_COLAB = 'def prepare_runtime(repo_root):\n    print("OLD PREPARED", repo_root)\n'


def _fake_clone(folder: Path, colab_py: str) -> Path:
    (folder / "src" / "mastery").mkdir(parents=True)
    (folder / "pyproject.toml").write_text("[project]\nname = 'mastery'\n", encoding="utf-8")
    (folder / "src" / "mastery" / "__init__.py").write_text('__version__ = "0.0.1"\n', encoding="utf-8")
    (folder / "src" / "mastery" / "colab.py").write_text(colab_py, encoding="utf-8")
    return folder


def _run_with_clone(source: str, clone: Path, tmp_path: Path, before: str = "") -> subprocess.CompletedProcess[str]:
    script = tmp_path / "colab_old_mastery.py"
    script.write_text(COLAB_ONLY + before + source, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "LC_MASTERY_ROOT")}
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", COLAB_RELEASE_TAG="test", LC_MASTERY_ROOT=str(clone))
    return subprocess.run([sys.executable, str(script)], cwd=tmp_path, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=120)


@pytest.mark.parametrize(("notebook", "source"), SAMPLES, ids=_sample_ids())
def test_on_colab_an_older_clone_still_runs_and_says_how_to_update(notebook: Path, source: str, tmp_path: Path) -> None:
    """An old Drive clone + a newer notebook (opened from GitHub): no TypeError, a clear fix instead."""
    clone = _fake_clone(tmp_path / "clone", OLD_COLAB)
    result = _run_with_clone(source, clone, tmp_path)

    assert result.returncode == 0, result.stderr
    assert "TypeError" not in result.stderr
    assert f"OLD PREPARED {clone}" in result.stdout  # its prepare_runtime ran, without the newer arguments
    assert "older than this notebook" in result.stdout and "START_HERE" in result.stdout
    assert "Disconnect and delete runtime" in result.stdout
    assert result.stdout.count("WAITED") == 10  # gave Drive a few seconds to show a newer copy first


@pytest.mark.parametrize(("notebook", "source"), SAMPLES, ids=_sample_ids())
def test_on_colab_an_older_mastery_imported_earlier_is_replaced(notebook: Path, source: str, tmp_path: Path) -> None:
    """A stale mastery already in sys.modules (another folder) is dropped: this clone's code runs."""
    clone = _fake_clone(tmp_path / "clone", NEW_COLAB)
    stale = _fake_clone(tmp_path / "stale", OLD_COLAB)
    before = f"sys.path.insert(0, {str(stale / 'src')!r})\nimport mastery.colab\nsys.path.pop(0)\n"
    result = _run_with_clone(source, clone, tmp_path, before=before)

    assert result.returncode == 0, result.stderr
    assert "NEW PREPARED ['notebook', 'secrets']" in result.stdout  # the newer arguments reach the newer code
    assert "OLD PREPARED" not in result.stdout and "older than this notebook" not in result.stdout
    assert "WAITED" not in result.stdout
    assert f"from {clone / 'src' / 'mastery' / '__init__.py'}" in result.stdout


@pytest.mark.parametrize(("notebook", "source"), SAMPLES[:3], ids=_sample_ids()[:3])
def test_on_colab_it_reloads_a_clone_drive_updates_late(notebook: Path, source: str, tmp_path: Path) -> None:
    """The same clone, imported while Drive still showed the old colab.py: reloaded once Drive catches up."""
    clone = _fake_clone(tmp_path / "clone", OLD_COLAB)
    before = f"""sys.path.insert(0, {str(clone / 'src')!r})
import mastery.colab
def _sleep(seconds):
    print("WAITED", seconds)
    open({str(clone / 'src' / 'mastery' / 'colab.py')!r}, "w").write({NEW_COLAB!r})
time.sleep = _sleep
"""
    result = _run_with_clone(source, clone, tmp_path, before=before)

    assert result.returncode == 0, result.stderr
    assert "NEW PREPARED" in result.stdout and "OLD PREPARED" not in result.stdout
    assert result.stdout.count("WAITED") == 1
