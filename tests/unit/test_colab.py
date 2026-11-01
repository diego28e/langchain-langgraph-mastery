"""Offline tests for Google Colab support (mastery.colab and config.load_colab_secrets).

google.colab is faked with a module in sys.modules: nothing here needs Colab, the network or a real install.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest

from mastery import colab, config

REPO = Path(__file__).resolve().parents[2]


class SecretNotFoundError(Exception):
    pass


class NotebookAccessError(Exception):
    pass


class TimeoutException(Exception):
    pass


@pytest.fixture
def fake_colab(monkeypatch: pytest.MonkeyPatch):
    """A fake google.colab with userdata.get backed by a dict (or by exceptions)."""
    secrets: dict[str, object] = {}
    calls: list[str] = []

    def get(name: str) -> str:
        calls.append(name)
        value = secrets.get(name, SecretNotFoundError(name))
        if isinstance(value, Exception):
            raise value
        return value  # type: ignore[return-value]

    userdata = types.SimpleNamespace(get=get)
    google_colab = types.ModuleType("google.colab")
    google_colab.userdata = userdata  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google.colab", google_colab)
    monkeypatch.setattr(config, "_colab_secrets_done", False)
    for name in config.COLAB_SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)
    return types.SimpleNamespace(secrets=secrets, calls=calls)


def test_not_colab_is_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "google.colab", raising=False)
    monkeypatch.delenv("COLAB_RELEASE_TAG", raising=False)
    monkeypatch.setattr(config, "_colab_secrets_done", False)
    assert colab.in_colab() is False
    assert config.load_colab_secrets() == []
    ran: list[object] = []
    assert colab.prepare_runtime(REPO, runner=lambda cmd: ran.append(cmd) or 0) == []
    assert ran == []


def test_colab_env_var_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "google.colab", raising=False)
    monkeypatch.setenv("COLAB_RELEASE_TAG", "release-colab-test")
    assert colab.in_colab() is True


def test_secrets_are_loaded_without_overwriting(fake_colab, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    fake_colab.secrets.update(GROQ_API_KEY=" gsk_from_colab ", GOOGLE_API_KEY="from-colab", HF_TOKEN="")
    monkeypatch.setenv("GOOGLE_API_KEY", "already-set")
    loaded = config.load_colab_secrets()
    assert loaded == ["GROQ_API_KEY"]  # names only, never values
    assert os.environ["GROQ_API_KEY"] == "gsk_from_colab"
    assert os.environ["GOOGLE_API_KEY"] == "already-set"  # the real environment wins
    assert "HF_TOKEN" not in os.environ  # empty secret = not set
    assert "GOOGLE_API_KEY" not in fake_colab.calls  # set variables are not even looked up


def test_missing_and_unauthorized_secrets_are_skipped(fake_colab) -> None:
    import os

    fake_colab.secrets.update(GROQ_API_KEY=NotebookAccessError("no access"), TAVILY_API_KEY="tvly-x")
    assert config.load_colab_secrets() == ["TAVILY_API_KEY"]
    assert "GROQ_API_KEY" not in os.environ
    assert len(fake_colab.calls) == len(config.COLAB_SECRET_NAMES)


def test_timeout_stops_asking(fake_colab) -> None:
    fake_colab.secrets["GROQ_API_KEY"] = TimeoutException("not in the Colab UI")
    assert config.load_colab_secrets() == []
    assert fake_colab.calls == ["GROQ_API_KEY"]


def test_runs_once_per_kernel_unless_forced(fake_colab) -> None:
    config.load_colab_secrets()
    first = len(fake_colab.calls)
    assert config.load_colab_secrets() == []
    assert len(fake_colab.calls) == first
    fake_colab.secrets["HF_TOKEN"] = "hf_x"
    assert config.load_colab_secrets(["HF_TOKEN"], force=True) == ["HF_TOKEN"]


def test_load_env_reads_colab_secrets(fake_colab, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    fake_colab.secrets["GROQ_API_KEY"] = "gsk_colab"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(colab, "COLAB_REPO_DIRS", (tmp_path / "nope",))
    assert config.load_env() is None
    assert os.environ["GROQ_API_KEY"] == "gsk_colab"


def test_load_env_and_find_repo_root_use_the_colab_clone(
    fake_colab, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = tmp_path / "MyDrive" / colab.REPO_NAME
    (clone / "src" / "mastery").mkdir(parents=True)
    for name in ("pyproject.toml", "COURSE_OUTLINE.md"):
        (clone / name).write_text("", encoding="utf-8")
    (clone / ".env").write_text("MASTERY_TEST_COLAB_ENV=from-drive\n", encoding="utf-8")
    elsewhere = tmp_path / "content"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delenv(config.REPO_ROOT_ENV, raising=False)
    monkeypatch.delenv("MASTERY_TEST_COLAB_ENV", raising=False)
    monkeypatch.setattr(colab, "COLAB_REPO_DIRS", (clone, elsewhere / colab.REPO_NAME))
    assert colab.colab_repo_root() == clone
    assert config.find_repo_root() == clone
    assert config.load_env() == (clone / ".env").resolve()
    import os

    assert os.environ["MASTERY_TEST_COLAB_ENV"] == "from-drive"


def test_secret_names_cover_env_example() -> None:
    """Every key in .env.example (set or commented out) can come from Colab Secrets."""
    text = (REPO / ".env.example").read_text(encoding="utf-8")
    names = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]*(?:_API_KEY|_TOKEN))=", text, flags=re.M))
    names |= set(re.findall(r"^#?\s*(LANGSMITH_[A-Z_]+)=", text, flags=re.M))
    assert names, "no keys found in .env.example"
    assert names <= set(config.COLAB_SECRET_NAMES), sorted(names - set(config.COLAB_SECRET_NAMES))


def test_install_command_uses_constraints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(colab.shutil, "which", lambda _: None)
    cmd = colab.install_command("/content/repo")
    assert cmd[:4] == [sys.executable, "-m", "pip", "install"]
    assert f"{Path('/content/repo')}[colab]" in cmd  # Path() so it also passes on Windows
    assert cmd[cmd.index("-c") + 1] == str(Path("/content/repo") / colab.COLAB_CONSTRAINTS)
    monkeypatch.setattr(colab.shutil, "which", lambda _: "/usr/local/bin/uv")
    assert colab.install_command("/content/repo")[:5] == ["/usr/local/bin/uv", "pip", "install", "--python", sys.executable]
    assert colab.install_command("/content/repo", use_uv=False)[0] == sys.executable


def test_constraints_file_exists_and_pins_the_course_libraries() -> None:
    pins = (REPO / colab.COLAB_CONSTRAINTS).read_text(encoding="utf-8")
    for name in ("langchain", "langchain-core", "langgraph", "langsmith"):
        assert re.search(rf"^{name}==\d", pins, flags=re.M), name
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"^colab = \[", pyproject, flags=re.M)


@pytest.fixture
def colab_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("COLAB_RELEASE_TAG", "release-colab-test")
    monkeypatch.setattr(colab, "_STAMP_DIR", tmp_path)
    monkeypatch.setattr(colab.shutil, "which", lambda _: None)
    monkeypatch.setattr(config, "_colab_secrets_done", False)
    monkeypatch.setattr(colab, "_outdated_imports", list)
    return tmp_path


def test_prepare_runtime_installs_once(colab_runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(colab, "_versions", lambda: {"langchain": "1.4.6"})
    ran: list[list[str]] = []
    colab.prepare_runtime(REPO, runner=lambda cmd: ran.append(list(cmd)) or 0, load_secrets=False)
    colab.prepare_runtime(REPO, runner=lambda cmd: ran.append(list(cmd)) or 0, load_secrets=False)
    assert len(ran) == 1 and "-c" in ran[0]
    colab.prepare_runtime(REPO, runner=lambda cmd: ran.append(list(cmd)) or 0, load_secrets=False, force=True)
    assert len(ran) == 2


def test_prepare_runtime_asks_for_restart_when_an_imported_package_changed(
    colab_runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions = [{"pytest": "8.0.0", "brand-new": "1"}, {"pytest": "9.1.1", "brand-new": "1"}]
    monkeypatch.setattr(colab, "_versions", lambda: versions.pop(0) if len(versions) > 1 else versions[0])
    with pytest.raises(colab.RestartRequired, match="Restart session"):
        colab.prepare_runtime(REPO, runner=lambda cmd: 0, load_secrets=False)  # pytest is imported right now
    # The install is recorded, so the run after the restart skips it.
    colab.prepare_runtime(REPO, runner=lambda cmd: pytest.fail("installed twice"), load_secrets=False)


def test_prepare_runtime_no_restart_for_packages_not_imported(colab_runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    versions = iter([{"zzz-not-imported": "1"}, {"zzz-not-imported": "2"}])
    monkeypatch.setattr(colab, "_versions", lambda: next(versions))
    colab.prepare_runtime(REPO, runner=lambda cmd: 0, load_secrets=False)


def test_prepare_runtime_falls_back_to_pip_and_reports_failures(colab_runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(colab.shutil, "which", lambda _: "/usr/local/bin/uv")
    monkeypatch.setattr(colab, "_versions", dict)
    ran: list[str] = []
    colab.prepare_runtime(REPO, runner=lambda cmd: ran.append(cmd[0]) or (1 if cmd[0].endswith("uv") else 0),
                          load_secrets=False)
    assert ran == ["/usr/local/bin/uv", sys.executable]
    with pytest.raises(RuntimeError, match="failed"):
        colab.prepare_runtime(REPO, runner=lambda cmd: 2, load_secrets=False, force=True)


def test_prepare_runtime_loads_secrets(colab_runtime, fake_colab, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(colab, "_versions", dict)
    fake_colab.secrets["GROQ_API_KEY"] = "gsk_x"
    assert colab.prepare_runtime(REPO, runner=lambda cmd: 0) == ["GROQ_API_KEY"]


def test_colab_note_links_the_docs() -> None:
    note = colab.colab_note("Docker", "docker")
    assert note.endswith("/docs/COLAB.md#docker") and "Docker" in note
    docs = (REPO / "docs" / "COLAB.md").read_text(encoding="utf-8")
    for anchor in ("docker", "ollama", "studio", "postgres"):  # the anchors the lessons link to
        assert re.search(rf'<a id="{anchor}"></a>', docs), anchor


def test_prepare_runtime_adds_extras_step0_installed(colab_runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(colab, "_versions", lambda: {"langgraph-api": "0.17.0", "fastembed": "0.9.0"})
    ran: list[list[str]] = []
    colab.prepare_runtime(REPO, runner=lambda cmd: ran.append(list(cmd)) or 0, load_secrets=False)
    assert f"{REPO.resolve()}[colab,studio,embeddings]" in ran[0]


def test_prepare_runtime_asks_once_when_step0_upgraded_an_imported_package(
    colab_runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(colab, "_versions", dict)
    monkeypatch.setattr(colab, "_outdated_imports", lambda: ["pandas 2.2.3 (installed: 3.0.6)"])
    with pytest.raises(colab.RestartRequired, match="pandas 2.2.3"):
        colab.prepare_runtime(REPO, runner=lambda cmd: 0, load_secrets=False)
    colab.prepare_runtime(REPO, runner=lambda cmd: 0, load_secrets=False)  # warns, never loops


def test_outdated_imports_finds_a_version_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("pytest")
    fake.__version__ = "0.0.1"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pytest", fake)
    assert any(item.startswith("pytest 0.0.1") for item in colab._outdated_imports())
