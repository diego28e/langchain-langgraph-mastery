"""Unit tests for mastery.evals.meta (offline; git is optional)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel

from mastery.evals import meta
from mastery.evals.meta import (
    content_hash,
    file_hash,
    format_metadata,
    git_info,
    model_fingerprint,
    package_versions,
    run_metadata,
)


def _triage(system: str = "You triage support tickets. Labels: billing, bug, other.") -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [("system", system), MessagesPlaceholder("examples", optional=True), ("human", "{ticket}")]
    )


class Ticket(BaseModel):
    label: str


# ---------------------------------------------------------------------------
# content_hash / file_hash
# ---------------------------------------------------------------------------


def test_content_hash_is_canonical_json_sha256() -> None:
    expected = hashlib.sha256(b'{"a":"x","b":[1,2]}').hexdigest()[:12]
    assert content_hash({"b": [1, 2], "a": "x"}) == expected
    assert content_hash({"a": "x", "b": [1, 2]}) == expected  # key order does not matter
    assert len(content_hash("hello", length=8)) == 8


def test_prompt_hash_is_stable_and_sensitive() -> None:
    assert content_hash(_triage()) == content_hash(_triage())
    changed = _triage("You triage support tickets. Labels: billing, bug, other!")
    assert content_hash(changed) != content_hash(_triage())


def test_message_hash_ignores_ids() -> None:
    first = [SystemMessage("Be brief.", id="1"), HumanMessage("Hi", id="2")]
    second = [SystemMessage("Be brief.", id="x"), HumanMessage("Hi", id="y")]
    assert content_hash(first) == content_hash(second)
    assert content_hash(first) != content_hash([SystemMessage("Be brief!"), HumanMessage("Hi")])


def test_schema_and_dataclass_hashes() -> None:
    class TicketV2(BaseModel):
        label: str
        urgent: bool

    assert content_hash(Ticket) != content_hash(TicketV2)

    @dataclass
    class Config:
        method: str
        strict: bool

    assert content_hash(Config("json_schema", True)) == content_hash({"method": "json_schema", "strict": True})
    assert content_hash({3, 1, 2}) == content_hash({2, 3, 1})


def test_content_hash_refuses_unreproducible_objects(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="file_hash"):
        content_hash(tmp_path)
    with pytest.raises(TypeError, match="reproducibly"):
        content_hash(lambda x: x)
    with pytest.raises(ValueError):
        content_hash("x", length=0)


def test_file_hash_ignores_line_endings_and_sees_changes(tmp_path: Path) -> None:
    unix, windows = tmp_path / "unix.jsonl", tmp_path / "windows.jsonl"
    unix.write_bytes(b'{"id": 1}\n{"id": 2}\n')
    windows.write_bytes(b'{"id": 1}\r\n{"id": 2}\r\n')
    assert file_hash(unix) == file_hash(windows)
    assert file_hash(unix, normalize_newlines=False) != file_hash(windows, normalize_newlines=False)
    before = file_hash(unix)
    unix.write_bytes(b'{"id": 1}\n{"id": 3}\n')
    assert file_hash(unix) != before


def test_file_hash_of_a_folder_includes_names(tmp_path: Path) -> None:
    folder = tmp_path / "data"
    folder.mkdir()
    (folder / "a.txt").write_text("same")
    first = file_hash(folder)
    (folder / "a.txt").rename(folder / "b.txt")
    assert file_hash(folder) != first
    with pytest.raises(FileNotFoundError):
        file_hash(tmp_path / "missing.txt")


# ---------------------------------------------------------------------------
# model_fingerprint
# ---------------------------------------------------------------------------


def test_model_fingerprint_never_contains_secrets() -> None:
    chat_groq = pytest.importorskip("langchain_groq").ChatGroq
    model = chat_groq(
        model="openai/gpt-oss-20b",
        api_key="gsk_secret",
        reasoning_effort="low",
        default_headers={"Authorization": "Bearer gsk_header_secret"},
        model_kwargs={"user_token": "gsk_kwarg_secret", "user": "course"},
    )
    fingerprint = model_fingerprint(model)
    dumped = json.dumps(fingerprint)
    assert "gsk_" not in dumped
    assert fingerprint["model"] == "openai/gpt-oss-20b"
    assert fingerprint["reasoning_effort"] == "low"
    assert fingerprint["model_kwargs"] == {"user": "course"}


def test_model_fingerprint_looks_inside_bindings_and_chains() -> None:
    chat_groq = pytest.importorskip("langchain_groq").ChatGroq
    model = chat_groq(model="openai/gpt-oss-20b", api_key="gsk_secret", temperature=0)
    structured = model_fingerprint(model.with_structured_output(Ticket))
    assert structured["model"] == "openai/gpt-oss-20b"
    assert structured["bound"]["tools"] == ["Ticket"]
    assert model_fingerprint(model.bind(tool_choice="auto"))["bound"] == {"tool_choice": "auto"}
    assert content_hash(model) != content_hash(chat_groq(model="openai/gpt-oss-20b", api_key="k", temperature=1))
    with pytest.raises(TypeError, match="no chat model"):
        content_hash(_triage() | (lambda x: x))  # a chain without a model has no reproducible form


# ---------------------------------------------------------------------------
# git, packages, run_metadata
# ---------------------------------------------------------------------------


def test_git_info_never_fails_without_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(meta.shutil, "which", lambda _: None)
    for variable in meta.CI_SHA_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    assert git_info() == {"git_sha": None, "git_dirty": None}
    monkeypatch.setenv("GITHUB_SHA", "0123456789abcdef0123456789abcdef01234567")
    assert git_info() == {"git_sha": "0123456789ab", "git_dirty": None}


def test_git_info_outside_a_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in meta.CI_SHA_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    info = git_info(tmp_path)
    assert info == {"git_sha": None, "git_dirty": None}


def test_package_versions_reports_missing_as_none() -> None:
    versions = package_versions(["pytest", "surely-not-an-installed-package-xyz"])
    assert versions["pytest"] and versions["surely-not-an-installed-package-xyz"] is None


def test_run_metadata_convention(tmp_path: Path) -> None:
    dataset = tmp_path / "tickets.jsonl"
    dataset.write_text('{"id": "T01"}\n')
    prompt = _triage()
    result = run_metadata(
        prompt_version="tickets-v2",
        prompt=prompt,
        model="groq:openai/gpt-oss-20b",
        config={"method": "json_schema", "api_key": "never-recorded"},
        dataset=dataset,
        dataset_version="2026-10-14.1",
        packages=["pytest"],
        include_git=False,
        config_name="fast",
        run=2,
    )
    assert result["prompt_version"] == "tickets-v2"
    assert result["prompt_hash"] == content_hash(prompt)
    assert result["model"] == "groq:openai/gpt-oss-20b"
    assert result["dataset_hash"] == file_hash(dataset)
    assert result["git_sha"] is None and result["git_dirty"] is None
    assert result["pkg_pytest"] and result["config_name"] == "fast" and result["run"] == 2
    assert "never-recorded" not in json.dumps(result)
    same_config = run_metadata(model="groq:openai/gpt-oss-20b", config={"method": "json_schema"}, include_git=False)
    assert result["config_hash"] == same_config["config_hash"]  # secrets are not part of the hash
    other = run_metadata(model="groq:openai/gpt-oss-20b", config={"method": "function_calling"}, include_git=False)
    assert other["config_hash"] != result["config_hash"]


@pytest.mark.parametrize("key", ["api_key", "GROQ_API_KEY", "user_token", "x-api-key", "Authorization",
                                 "default_headers", "password", "accessToken", "client_secret"])
def test_credential_like_keys_are_dropped(key: str) -> None:
    assert meta._SECRET_KEY.search(key)


@pytest.mark.parametrize("key", ["max_tokens", "max_completion_tokens", "keywords", "author", "monkey", "top_k"])
def test_ordinary_settings_are_kept(key: str) -> None:
    assert not meta._SECRET_KEY.search(key)
    one = run_metadata(config={key: 1}, include_git=False, packages=())
    two = run_metadata(config={key: 2}, include_git=False, packages=())
    assert one["config_hash"] != two["config_hash"]  # the setting is part of the hash


def test_run_metadata_has_the_same_keys_every_time() -> None:
    empty = run_metadata(include_git=False, packages=())
    assert list(empty) == [
        "prompt_version", "prompt_hash", "model", "config_hash", "dataset_version",
        "dataset_hash", "git_sha", "git_dirty", "python", "created_at",
    ]
    assert empty["config_hash"] is None and empty["dataset_hash"] is None


def test_run_metadata_hashes_in_memory_datasets() -> None:
    rows = [{"id": "T01", "label": "bug"}]
    assert run_metadata(dataset=rows, include_git=False, packages=())["dataset_hash"] == content_hash(rows)


def test_run_metadata_guards_extra_keys() -> None:
    with pytest.raises(ValueError, match="overwrite"):
        run_metadata(include_git=False, packages=(), model_name="x", prompt_hash="mine")
    with pytest.raises(TypeError, match="JSON"):
        run_metadata(include_git=False, packages=(), when=object())


def test_format_metadata_aligns_keys() -> None:
    text = format_metadata({"prompt_version": "v1", "git_sha": None, "run": 3})
    assert text.splitlines() == ["prompt_version : v1", "run            : 3"]
    assert "git_sha" in format_metadata({"git_sha": None}, skip_none=False)
    assert format_metadata({}) == ""
