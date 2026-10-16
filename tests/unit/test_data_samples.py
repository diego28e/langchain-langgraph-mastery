"""The Project 01 answer key follows its own labelling rules (the prompt and the scorer rely on them)."""

from __future__ import annotations

import json
from pathlib import Path

POSTINGS = Path(__file__).resolve().parents[2] / "data" / "samples" / "job-postings"
KEY = json.loads((POSTINGS / "answer-key.json").read_text(encoding="utf-8"))
FIELDS = {"title", "company", "seniority", "work_mode", "skills", "salary"}


def test_answer_key_is_versioned_and_covers_every_posting() -> None:
    assert KEY["_version"]
    assert {p.stem.upper() for p in POSTINGS.glob("jp-*.txt")} == set(KEY["answers"])


def test_every_answer_uses_the_allowed_labels_and_canonical_skills() -> None:
    aliases = KEY["_aliases"]
    for pid, answer in KEY["answers"].items():
        assert set(answer) == FIELDS, pid
        assert answer["seniority"] in {"intern", "junior", "mid", "senior", "lead", "unknown"}, pid
        assert answer["work_mode"] in {"remote", "hybrid", "onsite", "unknown"}, pid
        for skill in answer["skills"]:
            assert skill == skill.strip().lower(), (pid, skill)
            assert skill not in aliases, f"{pid}: {skill!r} should be its canonical name {aliases[skill]!r}"


def test_alias_targets_are_canonical_names() -> None:
    gold = {skill for answer in KEY["answers"].values() for skill in answer["skills"]}
    for alias, target in KEY["_aliases"].items():
        assert target not in KEY["_aliases"], alias
        assert target == target.lower() and alias == alias.lower()
    assert {"apache spark", "airflow", "kubernetes"} <= gold & set(KEY["_aliases"].values())
