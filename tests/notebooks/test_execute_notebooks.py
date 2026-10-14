"""Run every course notebook top to bottom with no API keys ("Restart & Run All", headless).

Slow (several minutes), so it is opt-in: ``python -m pytest -m notebooks`` (CI runs it on every
push). Notebooks are executed in memory with nbclient: outputs are never written back. Live (💸)
cells must skip themselves when keys are missing (CONVENTIONS.md §3), and offline 🧪 cells must run.

Needs the ``ci`` extra: ``python -m pip install -e ".[ci]"`` (nbclient, ipykernel and the packages
the notebooks' ``%pip`` cells would otherwise install).
"""

from __future__ import annotations

from pathlib import Path

import nbformat
import pytest

nbclient = pytest.importorskip("nbclient")

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = sorted(p for p in (REPO_ROOT / "modules").rglob("*.ipynb") if ".ipynb_checkpoints" not in p.parts)
# Present but EMPTY: python-dotenv never overrides a set variable, so a local .env can't leak keys in.
KEYS = ("GROQ_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "LANGSMITH_API_KEY",
        "TAVILY_API_KEY", "HF_TOKEN")

pytestmark = pytest.mark.notebooks


@pytest.mark.parametrize("path", NOTEBOOKS, ids=[p.relative_to(REPO_ROOT).as_posix() for p in NOTEBOOKS])
def test_notebook_runs_without_keys(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in KEYS:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("MPLBACKEND", "Agg")                          # charts render without a display
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT / "src"))          # this clone's mastery, like pytest
    nb = nbformat.read(path, as_version=4)
    client = nbclient.NotebookClient(nb, timeout=600, kernel_name="python3",
                                     resources={"metadata": {"path": str(path.parent)}})
    client.execute()
