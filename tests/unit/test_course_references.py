"""Course-wide reference checks: links, anchors, lesson/project/lab numbers, and Part labels.

Renumbering lessons or modules touches dozens of files (READMEs, the outline, docs, notebooks),
so these checks catch a half-done job:

1. every relative link and ``#anchor`` in a Markdown file or a notebook Markdown cell resolves
   (anchors use GitHub's heading slugs, so they also work on github.com);
2. every "Lesson NN.LL", "Project NN", "Lab NNX", "Module NN" and ``NN-LL-slug.ipynb`` mentioned in
   a Markdown file or a notebook exists in COURSE_OUTLINE.md (built or planned);
3. every notebook title cell names its own module and the right part: "Part 1 (Core)" for
   Modules 00-08, "Part 2 (Pro)" from Module 09.

No network, no kernel: files are read, never executed. URLs (``https:``, ``mailto:`` ...) are not
checked here. Private (``_*``) and hidden (``.*``) folders and generated data are skipped.
"""

from __future__ import annotations

import os
import re
import unicodedata
from collections import Counter
from functools import cache
from pathlib import Path
from urllib.parse import unquote

import nbformat
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTLINE = REPO_ROOT / "COURSE_OUTLINE.md"

# Folders that are not course content: private notes (_maintainer), hidden folders (.git, .venv ...),
# caches, and generated or downloaded data.
SKIP_DIR_NAMES = {"__pycache__", "node_modules", "venv"}
SKIP_PATHS = {REPO_ROOT / "data" / name for name in ("outputs", "raw", "vectorstores")}
# Text files whose lesson/module references are checked (2) in addition to Markdown and notebooks.
EXTRA_REFERENCE_FILES = (".py", ".txt", ".toml", ".example")

# [text](target), ![alt](target), [text](<target with spaces>) and HTML href/src attributes.
LINK = re.compile(r"\[[^\]]*\]\(\s*(<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\s*\)|(?:href|src)=\"([^\"]+)\"")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`+[^`]*`+")
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HTML_ANCHOR = re.compile(r"<a\s+(?:name|id)=\"([^\"]+)\"")

# (2) References. A list after the noun is checked item by item: "Lessons 06.02–06.03",
# "Lessons 01.06 and 12.02", "Modules 02, 07, 11, 12", "Labs 11A–11C".
SEP = r"\s*(?:[–—-]|,|\band\b|\bor\b|\by\b|&|/)\s*"
LESSON_REF = re.compile(rf"\b(?:Lessons?|Lecci[óo]n(?:es)?)\s+(\d\d\.\d\d(?:{SEP}\d\d\.\d\d)*)")
PROJECT_REF = re.compile(rf"\b(?:Projects?|Proyectos?)\s+(\d\d(?:{SEP}\d\d)*)\b(?![.\d])")
LAB_REF = re.compile(rf"\bLabs?\s+(\d\d[A-Z](?:{SEP}\d\d[A-Z])*)\b")
MODULE_REF = re.compile(rf"\b(?:Modules?|M[óo]dulos?)\s+(\d\d(?:{SEP}\d\d)*)\b(?![.\d])")
NOTEBOOK_NAME = re.compile(r"(?<![\w-])(\d\d-\d\d-[a-z0-9-]+\.ipynb)\b")
# Notebook names that are conventions or examples, not lessons (CONVENTIONS.md §2: exercise solutions).
NOTEBOOK_NAME_EXCEPTIONS = re.compile(r"-solutions?\.ipynb$")

TITLE_PART = re.compile(r"\*\*Module (\d\d) · [^*]+\*\* · (Part [12] \([^)]+\))")


# --- helpers ----------------------------------------------------------------------------------


def _course_files(suffixes: tuple[str, ...]) -> list[Path]:
    files = []
    for folder, dirs, names in os.walk(REPO_ROOT):
        dirs[:] = sorted(
            d for d in dirs
            if not d.startswith((".", "_")) and d not in SKIP_DIR_NAMES
            and not d.endswith(".egg-info") and Path(folder, d) not in SKIP_PATHS
        )
        files += [Path(folder, n) for n in sorted(names) if n.endswith(suffixes)]
    return files


@cache
def _notebook(path: Path) -> nbformat.NotebookNode:
    return nbformat.read(path, as_version=4)


def _markdown(path: Path) -> str:
    """Markdown of a .md file, or the Markdown cells of a notebook."""
    if path.suffix == ".ipynb":
        return "\n\n".join(c.source for c in _notebook(path).cells if c.cell_type == "markdown")
    return path.read_text(encoding="utf-8")


def _all_text(path: Path) -> str:
    """Every cell of a notebook (comments in code cells cite lessons too), or the whole file."""
    if path.suffix == ".ipynb":
        return "\n\n".join(c.source for c in _notebook(path).cells)
    return path.read_text(encoding="utf-8")


def _prose_lines(text: str):
    """(line number, line) outside fenced code blocks, with inline code removed."""
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield number, INLINE_CODE.sub("", line)


def github_slug(heading: str) -> str:
    """GitHub's heading anchor (github-slugger): lowercase, keep letters, marks, numbers, '_', ' ', '-'."""
    text = re.sub(r"<[^>]+>", "", heading)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)   # links and images keep their text
    text = text.strip().lower()
    kept = "".join(
        ch for ch in text
        if ch in " -" or unicodedata.category(ch)[0] in "LMN" or unicodedata.category(ch) == "Pc"
    )
    return kept.replace(" ", "-")


@cache
def _anchors(path: Path) -> frozenset[str]:
    """Every anchor a page offers: heading slugs (with GitHub's -1, -2 suffixes) and <a id/name>."""
    seen: Counter[str] = Counter()
    anchors: set[str] = set()
    in_fence = False
    for line in _markdown(path).splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        anchors.update(HTML_ANCHOR.findall(line))
        match = HEADING.match(line)
        if match:
            slug = github_slug(match.group(2))
            anchors.add(slug if seen[slug] == 0 else f"{slug}-{seen[slug]}")
            # Renderers differ on emoji variation selectors (U+FE0F); accept the stripped form too.
            anchors.add("".join(ch for ch in slug if unicodedata.category(ch) != "Mn"))
            seen[slug] += 1
    return frozenset(anchors)


def _exists_exact_case(path: Path) -> bool:
    """Like Path.exists(), but case-sensitive on every OS (GitHub and Linux are case-sensitive)."""
    try:
        relative = path.relative_to(REPO_ROOT)
    except ValueError:
        return False   # Outside the repository.
    current = REPO_ROOT
    for part in relative.parts:
        if not current.is_dir() or part not in os.listdir(current):
            return False
        current = current / part
    return True


@cache
def _outline() -> dict[str, set[str]]:
    text = OUTLINE.read_text(encoding="utf-8")
    return {
        "module": set(re.findall(r"^## Module (\d\d) — ", text, re.M)),
        "lesson": set(re.findall(r"^### Lesson (\d\d\.\d\d) — ", text, re.M)),
        "project": set(re.findall(r"^### Project (\d\d) — ", text, re.M)),
        "lab": set(re.findall(r"^### Lab (\d\d[A-Z]) — ", text, re.M)),
        "notebook": set(re.findall(r"\*\*Notebook:\*\* `modules/[^/`]+/(\d\d-\d\d-[a-z0-9-]+\.ipynb)`", text)),
    }


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


DOC_FILES = _course_files((".md", ".ipynb"))
# Test files are left out: they hold made-up names on purpose (e.g. "00-05-slug.ipynb").
REFERENCE_FILES = [
    p for p in _course_files((".md", ".ipynb", *EXTRA_REFERENCE_FILES))
    if p.suffix in (".md", ".ipynb") or REPO_ROOT / "tests" not in p.parents
]
TITLED_NOTEBOOKS = sorted(p for p in REPO_ROOT.glob("modules/[0-9][0-9]-*/**/*.ipynb") if ".ipynb_checkpoints" not in p.parts)


# --- 1. links and anchors ---------------------------------------------------------------------


def _broken_links(path: Path) -> list[str]:
    broken = []
    for number, line in _prose_lines(_markdown(path)):
        for match in LINK.finditer(line):
            target = (match.group(1) or match.group(2)).strip("<>")
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
                continue   # A URL (https:, mailto: ...): not checked offline.
            raw_path, _, fragment = target.partition("#")
            resolved = Path(os.path.normpath(path.parent / unquote(raw_path))) if raw_path else path
            where = f"{_rel(path)}:{number}: ({target})"
            if not _exists_exact_case(resolved):
                broken.append(f"{where} -> no such file or folder")
                continue
            if resolved.is_dir():
                resolved = resolved / "README.md"   # GitHub shows the folder's README.
            if fragment and resolved.suffix in (".md", ".ipynb") and resolved.is_file():
                if unquote(fragment) not in _anchors(resolved):
                    broken.append(f"{where} -> no heading or anchor '#{fragment}' in {_rel(resolved)}")
    return broken


def test_scan_finds_course_documents() -> None:
    names = {_rel(p) for p in DOC_FILES}
    assert {"README.md", "COURSE_OUTLINE.md", "CONVENTIONS.md"} <= names
    assert sum(name.endswith(".ipynb") for name in names) >= 80
    assert not any(name.startswith("_maintainer/") for name in names)


def test_github_slug_matches_github() -> None:
    assert github_slug("Module 10 — Testing, Evaluation & Observability") == "module-10--testing-evaluation--observability"
    assert github_slug("Part 2 — Pro (Modules 09–14)") == "part-2--pro-modules-0914"
    assert github_slug("Step 4b — Windows + Git Bash: check `SSL_CERT_FILE`") == "step-4b--windows--git-bash-check-ssl_cert_file"
    assert github_slug("Default model stack (verified October 11, 2026)") == "default-model-stack-verified-october-11-2026"


@pytest.mark.parametrize("path", DOC_FILES, ids=[_rel(p) for p in DOC_FILES])
def test_relative_links_and_anchors_resolve(path: Path) -> None:
    broken = _broken_links(path)
    assert not broken, "Broken links:\n" + "\n".join(broken)


# --- 2. lesson, project, lab, module and notebook references ------------------------------------


def _unknown_references(path: Path) -> list[str]:
    known = _outline()
    unknown = []
    for number, line in enumerate(_all_text(path).splitlines(), 1):
        found = [
            *(("lesson", x) for m in LESSON_REF.finditer(line) for x in re.findall(r"\d\d\.\d\d", m.group(1))),
            *(("project", x) for m in PROJECT_REF.finditer(line) for x in re.findall(r"\d\d", m.group(1))),
            *(("lab", x) for m in LAB_REF.finditer(line) for x in re.findall(r"\d\d[A-Z]", m.group(1))),
            *(("module", x) for m in MODULE_REF.finditer(line) for x in re.findall(r"\d\d", m.group(1))),
            *(("notebook", x) for x in NOTEBOOK_NAME.findall(line) if not NOTEBOOK_NAME_EXCEPTIONS.search(x)),
        ]
        unknown += [f"{_rel(path)}:{number}: {kind} {value}" for kind, value in found if value not in known[kind]]
    return unknown


def test_outline_defines_the_course() -> None:
    known = _outline()
    assert known["module"] == {f"{n:02d}" for n in range(15)}
    assert len(known["lesson"]) >= 100 and len(known["notebook"]) == len(known["lesson"])
    assert known["project"] == known["module"]
    assert {"11A", "11B", "11C"} <= known["lab"]   # The Deep Agents use-case labs.


@pytest.mark.parametrize("path", REFERENCE_FILES, ids=[_rel(p) for p in REFERENCE_FILES])
def test_lesson_project_lab_and_module_references_exist(path: Path) -> None:
    unknown = _unknown_references(path)
    assert not unknown, "References that COURSE_OUTLINE.md does not define:\n" + "\n".join(unknown)


# --- 3. Part labels in notebook title cells ----------------------------------------------------


@pytest.mark.parametrize("path", TITLED_NOTEBOOKS, ids=[_rel(p) for p in TITLED_NOTEBOOKS])
def test_title_cell_names_its_module_and_part(path: Path) -> None:
    folder_module = path.relative_to(REPO_ROOT / "modules").parts[0][:2]
    match = TITLE_PART.search(_notebook(path).cells[0].source)
    assert match, "title cell needs '**Module NN · Title** · Part N (...)'"
    module, part = match.groups()
    assert module == folder_module, f"title says Module {module}, folder is Module {folder_module}"
    expected = "Part 1 (Core)" if int(module) <= 8 else "Part 2 (Pro)"
    assert part == expected, f"Module {module} belongs to {expected}, title says {part}"
