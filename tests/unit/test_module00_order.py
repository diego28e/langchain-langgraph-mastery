"""Module 00 lesson order stays consistent everywhere: numbers, file names, titles, and links.

Module 00 makes the first model call (00.05) before the research (00.06) and provider (00.07)
lessons. Renumbering lessons touches many files, so these checks catch a half-done job:

* the README lesson table, the notebook file names, the notebook titles and COURSE_OUTLINE.md agree;
* each lesson's closing "What's next" cell opens the next lesson in the table (the last one, the project);
* every link or path to a Module 00 notebook, in any Markdown file or notebook Markdown cell, exists.

No network, no kernel: files are read, never executed.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import nbformat
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "modules" / "00-foundations"
GENERATORS = REPO_ROOT / "_maintainer" / "tools" / "m00"   # Private maintainer tools; absent in learner clones.

# A row of the README's Lessons table: | 00.05 | Title | [`00-05-slug.ipynb`](00-05-slug.ipynb) ... |
TABLE_ROW = re.compile(r"^\|\s*(00\.\d\d)\s*\|\s*([^|]+?)\s*\|.*?\]\(([^)]+\.ipynb)\)", re.M)
# Markdown link targets: [text](target) or [text](<target>).
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)")
# Module 00 notebooks named anywhere, with or without a path: 00-05-first-groq-call.ipynb
BARE_NAME = re.compile(r"\b00-\d\d-[a-z0-9-]+\.ipynb\b")
# Folders that are not course content (private notes, git internals, generated data, editor copies).
SKIP_DIRS = {".git", "_maintainer", ".ipynb_checkpoints", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules"}
SKIP_PATHS = {REPO_ROOT / "data" / name for name in ("outputs", "raw", "vectorstores")}


def _lessons() -> list[tuple[str, str, str]]:
    """(number, title, file name) for each row of the README's Lessons table, in table order."""
    text = (MODULE_DIR / "README.md").read_text(encoding="utf-8")
    return [(num, title, Path(target).name) for num, title, target in TABLE_ROW.findall(text)]


LESSONS = _lessons()


def _first_cell(path: Path) -> str:
    return nbformat.read(path, as_version=4).cells[0].source


def test_readme_table_lists_lessons_in_order() -> None:
    numbers = [num for num, _, _ in LESSONS]
    assert numbers == [f"00.{n:02d}" for n in range(1, len(LESSONS) + 1)], numbers
    assert len(LESSONS) >= 7


def test_readme_table_lists_every_lesson_notebook() -> None:
    on_disk = sorted(p.name for p in MODULE_DIR.glob("00-[0-9][0-9]-*.ipynb"))
    assert sorted(name for _, _, name in LESSONS) == on_disk


@pytest.mark.parametrize(("num", "title", "name"), LESSONS, ids=[num for num, _, _ in LESSONS])
def test_file_name_and_title_cell_match_the_table(num: str, title: str, name: str) -> None:
    lesson = num.split(".")[1]
    assert name.startswith(f"00-{lesson}-"), f"{name} should start with 00-{lesson}-"
    path = MODULE_DIR / name
    assert path.is_file(), f"{name} is in the README table but does not exist"
    assert _first_cell(path).startswith(f"# {num} · {title}\n"), f"title cell of {name} should be '# {num} · {title}'"


@pytest.mark.parametrize(("num", "title", "name"), LESSONS, ids=[num for num, _, _ in LESSONS])
def test_generator_matches_the_table(num: str, title: str, name: str) -> None:
    if not GENERATORS.is_dir():
        pytest.skip("maintainer generators are not part of learner clones")
    lesson = num.split(".")[1]
    generator = GENERATORS / f"l{lesson}.py"
    assert generator.is_file(), f"expected generator {generator.name} for {name}"
    source = generator.read_text(encoding="utf-8")
    assert f'title("{num}"' in source, f"{generator.name} should build the title cell for {num}"
    assert f'"{name}"' in source, f"{generator.name} should save {name}"


def test_course_outline_lists_the_same_lessons_in_the_same_order() -> None:
    outline = (REPO_ROOT / "COURSE_OUTLINE.md").read_text(encoding="utf-8")
    headings = re.findall(r"^### Lesson (00\.\d\d) — (.+)$", outline, re.M)
    assert headings == [(num, title) for num, title, _ in LESSONS]
    for num, _, name in LESSONS:
        section = outline.split(f"### Lesson {num} — ", 1)[1].split("\n### ", 1)[0]
        assert f"modules/00-foundations/{name}" in section, f"COURSE_OUTLINE.md, Lesson {num}: notebook should be {name}"


@pytest.mark.parametrize("index", range(len(LESSONS)), ids=[num for num, _, _ in LESSONS])
def test_whats_next_cell_opens_the_next_lesson(index: int) -> None:
    _, _, name = LESSONS[index]
    expected = LESSONS[index + 1][2] if index + 1 < len(LESSONS) else "project/README.md"
    last = nbformat.read(MODULE_DIR / name, as_version=4).cells[-1]
    assert last.cell_type == "markdown" and "What's next" in last.source
    assert f"]({expected})" in last.source, f"{name} should end by pointing to {expected}"


def _course_texts() -> list[tuple[Path, str]]:
    """Every Markdown file, and the Markdown cells of every notebook, outside the skipped folders."""
    texts = []
    for folder, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and Path(folder, d) not in SKIP_PATHS]
        for file in files:
            path = Path(folder, file)
            if path.suffix == ".md":
                texts.append((path, path.read_text(encoding="utf-8")))
            elif path.suffix == ".ipynb":
                cells = nbformat.read(path, as_version=4).cells
                texts.append((path, "\n".join(c.source for c in cells if c.cell_type == "markdown")))
    return texts


def test_every_reference_to_a_module00_notebook_exists() -> None:
    broken = []
    for path, text in _course_texts():
        where = path.relative_to(REPO_ROOT).as_posix()
        # 1. Relative links that land in modules/00-foundations/.
        for target in LINK.findall(text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue   # A URL, mailto: or an anchor on the same page.
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            if resolved.suffix == ".ipynb" and MODULE_DIR in resolved.parents and not resolved.is_file():
                broken.append(f"{where}: link {target}")
        # 2. Notebook names written as text, e.g. `modules/00-foundations/00-05-first-groq-call.ipynb`.
        for name in set(BARE_NAME.findall(text)):
            if not (MODULE_DIR / name).is_file():
                broken.append(f"{where}: mentions {name}")
    assert not broken, "References to Module 00 notebooks that do not exist:\n" + "\n".join(sorted(broken))
