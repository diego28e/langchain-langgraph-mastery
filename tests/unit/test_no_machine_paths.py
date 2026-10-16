"""No tracked file may contain a path that only exists on one person's computer.

The course must run from any clone on Windows, macOS or Linux. Teaching examples
use placeholders (``C:\\Users\\<you>``) or the sample names below; anything else
under a user's home folder is a leaked machine-specific path.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Example user names the lessons use on purpose. Placeholders like <you> are always fine.
ALLOWED_USERS = {"ana", "ana maria", "you", "learner", "<you>", "...", "<user>", "username", "me"}
TEXT_SUFFIXES = {".py", ".md", ".ipynb", ".json", ".toml", ".yml", ".yaml", ".txt", ".cfg", ".ini", ".example", ".sh", ".ps1"}
SKIP_PREFIXES = ("_maintainer/", "data/outputs/", "data/vectorstores/")

_SEP = r"(?:\\\\|\\|/)"  # one or two backslashes (JSON escapes them) or a slash
HOME_PATH = re.compile(
    rf"(?:\b[A-Za-z]:{_SEP}Users{_SEP}|/c/Users/|(?<![\w.])/Users/|(?<![\w.])/home/)"
    r"(?P<user><[^>]+>|\.\.\.|[A-Za-z][\w.\- ]*?)(?=\\|/|\"|`|'|\)|\s|$)",
    re.MULTILINE,
)


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
        names = out.splitlines()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git is not available")
    me = Path(__file__).resolve()
    return [REPO_ROOT / n for n in names if not n.startswith(SKIP_PREFIXES) and (REPO_ROOT / n).resolve() != me]


# Folder names from the authors' own machines that once leaked into lessons (split so this file doesn't match).
KNOWN_LEAKS = ("My-langchain" + "-course", "taking-my-own" + "-langchain-course", "Documents/AI " + "courses")


def offending_paths(text: str) -> list[str]:
    hits = [m.group(0) for m in HOME_PATH.finditer(text) if m.group("user").strip().lower() not in ALLOWED_USERS]
    return hits + [leak for leak in KNOWN_LEAKS if leak in text]


@pytest.mark.parametrize(
    ("text", "bad"),
    [
        ("cd /c/Users/jdoe/Documents", True),
        ('"C:\\\\Users\\\\jdoe\\\\anaconda3"', True),
        ("C:\\Users\\jdoe\\repo", True),
        ("/home/maria/projects/x", True),
        ("/Users/sam/code", True),
        ("C:\\Users\\<you>\\anaconda3", False),
        ("/c/Users/Ana/Documents", False),
        ("C:/Users/learner/anaconda3/envs", False),
        ("see /c/Users/... for details", False),
        ('cd "/c/Users/<you>/Documents/AI ' + 'courses/x"', True),
    ],
)
def test_detector(text: str, bad: bool) -> None:
    assert bool(offending_paths(text)) is bad


def test_tracked_files_have_no_machine_specific_paths() -> None:
    hits = []
    for path in tracked_files():
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".env.example", "Makefile"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        hits += [f"{path.relative_to(REPO_ROOT).as_posix()}: {p}" for p in offending_paths(text)]
    assert not hits, "Machine-specific paths found (use <you> or a relative path):\n" + "\n".join(hits)


def test_find_repo_root_honours_override(tmp_path, monkeypatch) -> None:
    from mastery.config import REPO_ROOT_ENV, find_repo_root, package_repo_root

    monkeypatch.setenv(REPO_ROOT_ENV, str(REPO_ROOT))
    monkeypatch.chdir(tmp_path)  # outside the clone: the override still finds it
    assert find_repo_root() == REPO_ROOT.resolve()
    assert package_repo_root() == REPO_ROOT.resolve()
    monkeypatch.setenv(REPO_ROOT_ENV, str(tmp_path))
    with pytest.raises(FileNotFoundError, match=REPO_ROOT_ENV):
        find_repo_root()
    monkeypatch.delenv(REPO_ROOT_ENV)
    assert package_repo_root() == REPO_ROOT.resolve()  # editable install: two folders above the package
