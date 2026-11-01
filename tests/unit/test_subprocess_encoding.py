"""Every text-mode subprocess call names its encoding: src/, apps/, tests/ and every notebook.

``text=True`` alone decodes with the locale's encoding, which is cp1252 on Windows. A child that prints UTF-8
(✅, é, Docker's progress output) then kills subprocess's reader thread with ``UnicodeDecodeError`` and
``stdout`` comes back ``None``. Linux CI can't see it (its locale is UTF-8), so this check reads the code.
Fix: add ``encoding="utf-8"`` (plus ``errors="replace"`` for tools you don't control); a Python child also
needs ``-X utf8`` so it *writes* UTF-8 on Windows.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES = sorted(p for folder in ("src", "apps", "tests") for p in (REPO_ROOT / folder).rglob("*.py"))
NOTEBOOKS = sorted(p for p in REPO_ROOT.glob("modules/**/*.ipynb") if ".ipynb_checkpoints" not in p.parts)
_IPYTHON_ONLY = re.compile(r"^\s*([%!]|[\w.]+\?\??\s*$)")   # magics, shell escapes, `name?` help


def _text_calls_without_encoding(source: str) -> list[int]:
    """Line numbers of calls that pass text=True (or universal_newlines=True) and no encoding=."""
    lines = [ln[: len(ln) - len(ln.lstrip())] + "pass" if _IPYTHON_ONLY.match(ln) else ln for ln in source.splitlines()]
    tree = compile("\n".join(lines), "<code>", "exec", ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            keywords = {k.arg: k.value for k in node.keywords if k.arg}
            text_mode = any(isinstance(keywords.get(name), ast.Constant) and keywords[name].value is True
                            for name in ("text", "universal_newlines"))
            if text_mode and "encoding" not in keywords:
                found.append(node.lineno)
    return found


def test_there_is_code_to_check() -> None:
    assert SOURCES and NOTEBOOKS


def test_python_sources_name_the_encoding() -> None:
    problems = [f"{path.relative_to(REPO_ROOT).as_posix()}:{line}"
                for path in SOURCES for line in _text_calls_without_encoding(path.read_text(encoding="utf-8"))]
    assert not problems, f"text=True without encoding= (add encoding=\"utf-8\"): {problems}"


def test_notebooks_name_the_encoding() -> None:
    problems = []
    for path in NOTEBOOKS:
        for index, cell in enumerate(json.loads(path.read_text(encoding="utf-8"))["cells"]):
            if cell["cell_type"] == "code":
                problems += [f"{path.relative_to(REPO_ROOT).as_posix()} cell {index} line {line}"
                             for line in _text_calls_without_encoding("".join(cell["source"]))]
    assert not problems, f"text=True without encoding= (add encoding=\"utf-8\"): {problems}"


def test_the_check_catches_the_windows_bug() -> None:
    assert _text_calls_without_encoding('subprocess.run(["docker", "ps"], capture_output=True, text=True)') == [1]
    assert _text_calls_without_encoding('subprocess.run(cmd, text=True, encoding="utf-8")') == []
    assert _text_calls_without_encoding('%pip install x\nsorted?\nif x:\n    !ls\nrun(c, universal_newlines=True)') == [5]
