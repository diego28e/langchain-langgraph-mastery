"""Markdown cells must render as Markdown, never as an indented code block.

In Markdown, a line indented 4+ spaces (after a blank line, outside a list) is an *indented
code block*: a heading in it drops out of Jupyter's table of contents and a table shows as
raw pipes. The course writes every code sample as a ``` fence, so an indented code block in a
Markdown cell is always a mistake (typically leftover indentation from a text template).

Applies to every notebook, Module 00 included. Notebooks are read as files, never executed.
"""

from __future__ import annotations

from pathlib import Path

import nbformat
import pytest

markdown_it = pytest.importorskip("markdown_it", reason="markdown-it-py comes with the [dev] extra")

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = sorted(
    path
    for pattern in ("modules/**/*.ipynb", "apps/**/*.ipynb", "capstones/**/*.ipynb")
    for path in REPO_ROOT.glob(pattern)
    if ".ipynb_checkpoints" not in path.parts
)
# CommonMark plus GFM tables, close to what JupyterLab renders. With tables on, an indented
# row right after a table is reported too (plain CommonMark would read it as paragraph text).
PARSER = markdown_it.MarkdownIt("commonmark").enable("table")


def _ids(paths: list[Path]) -> list[str]:
    return [str(p.relative_to(REPO_ROOT)) for p in paths]


def indented_code_blocks(source: str) -> list[int]:
    """1-based line numbers where an indented code block starts in ``source``."""
    return [token.map[0] + 1 for token in PARSER.parse(source) if token.type == "code_block" and token.map]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("    ## Step 2 · The tools\n\n    Four tools from the spec.", [1]),  # the whole cell indented
        ("---\n## Part 7 · Live\n\n    > 💸 Calls a model.", [4]),  # one indented paragraph
        ("| a | b |\n|---|---|\n| 1 | 2 |\n    | 3 | 4 |", [4]),  # an indented table row
        ("```python\nif ok:\n    print(1)\n```", []),  # fenced code is fine
        ("1. Run the cell.\n\n    Then read the output.", []),  # a list item's continuation is fine
        ("A long sentence\n    wrapped onto an indented line.", []),  # a paragraph's continuation is fine
    ],
)
def test_checker_finds_only_indented_code_blocks(source: str, expected: list[int]) -> None:
    assert indented_code_blocks(source) == expected


def test_there_are_notebooks_to_check() -> None:
    assert any(p.name.startswith("00-") for p in NOTEBOOKS), "Module 00 notebooks must be checked too"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=_ids(NOTEBOOKS))
def test_markdown_cells_have_no_indented_code_blocks(path: Path) -> None:
    notebook = nbformat.read(path, as_version=4)
    bad = {}
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type == "markdown" and (starts := indented_code_blocks(cell.source)):
            bad[index] = cell.source.splitlines()[starts[0] - 1].strip()[:60]
    assert not bad, (
        f"Markdown cells that render (partly) as a code block, with their first indented line: {bad}. "
        "Remove the 4+ leading spaces, and write code as a ``` fence."
    )
