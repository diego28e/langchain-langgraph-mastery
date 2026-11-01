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


def reset_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh kernel: no secret asked yet, no notebook list, Colab UI present."""
    monkeypatch.setattr(config, "_colab_asked", set())
    monkeypatch.setattr(config, "_colab_wanted", None)
    monkeypatch.setattr(config, "_colab_no_ui", False)


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
    reset_secrets(monkeypatch)
    for name in config.COLAB_SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)
    return types.SimpleNamespace(secrets=secrets, calls=calls)


def test_not_colab_is_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "google.colab", raising=False)
    monkeypatch.delenv("COLAB_RELEASE_TAG", raising=False)
    reset_secrets(monkeypatch)
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
    reset_secrets(monkeypatch)
    monkeypatch.setattr(colab, "_outdated_imports", list)
    monkeypatch.setattr(colab, "notebook_source", lambda timeout=1.0: "")  # no local server in tests
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


def _start_here() -> list[dict]:
    import json

    return json.loads((REPO / "colab" / "START_HERE.ipynb").read_text(encoding="utf-8"))["cells"]


def test_start_here_explains_the_drive_permissions() -> None:
    text = "".join("".join(cell["source"]) for cell in _start_here() if cell["cell_type"] == "markdown")
    for phrase in ("Select all", "same Google account", "Continue", "colab.research.google.com"):
        assert phrase in text, phrase


@pytest.mark.skipif(Path("/content/drive/MyDrive").is_dir(), reason="a real Drive is mounted here")
def test_start_here_drive_mount_failure_prints_the_fix(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class MessageError(Exception):
        pass

    def mount(path: str) -> None:
        raise MessageError("Error: credential propagation was unsuccessful")

    google = types.ModuleType("google")
    google_colab = types.ModuleType("google.colab")
    google_colab.drive = types.SimpleNamespace(mount=mount)
    google.colab = google_colab
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.colab", google_colab)
    code = [cell for cell in _start_here() if cell["cell_type"] == "code"]
    namespace: dict[str, object] = {}
    exec("".join(code[0]["source"]), namespace)  # Step 1: settings
    assert namespace["USE_DRIVE"] is True
    with pytest.raises(RuntimeError, match="Drive did not mount") as caught:
        exec("".join(code[1]["source"]), namespace)  # Step 2: mount and clone
    assert caught.value.__suppress_context__  # `from None`: no long MessageError traceback
    out = capsys.readouterr().out
    for phrase in ("credential propagation", "Disconnect and delete runtime", "Select all",
                   "myaccount.google.com/connections", "USE_DRIVE = False"):
        assert phrase in out, phrase


def _cell(notebook: str, marker: str) -> str:
    import json

    path = next(REPO.glob(f"modules/*/{notebook}.ipynb"))
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    return next("".join(c["source"]) for c in cells if c["cell_type"] == "code" and marker in "".join(c["source"]))


KERNEL_CHECKS = [
    ("00-02-verify-environment", "def describe_environment("),
    ("00-03-jupyter-fundamentals", "Kernel Python:"),
    ("00-05-first-groq-call", "Kernel Python:"),
    ("02-01-defining-tools", "course env?"),
]


@pytest.mark.parametrize(("notebook", "marker"), KERNEL_CHECKS)
def test_kernel_checks_accept_colab_python(
    notebook: str, marker: str, fake_colab, capsys: pytest.CaptureFixture[str]
) -> None:
    """On Colab, /usr/bin/python3 is correct: no ⚠️/❌ and no "Change Kernel" advice."""
    import os

    exec(_cell(notebook, marker), {"sys": sys, "os": os, "Path": Path})
    out = capsys.readouterr().out
    assert "Colab" in out
    for bad in ("⚠️", "❌", "Change Kernel", "not managed by conda"):
        assert bad not in out, bad


@pytest.mark.parametrize(("notebook", "marker"), KERNEL_CHECKS)
def test_kernel_checks_unchanged_off_colab(
    notebook: str, marker: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import os

    monkeypatch.delitem(sys.modules, "google.colab", raising=False)
    monkeypatch.delenv("COLAB_RELEASE_TAG", raising=False)
    exec(_cell(notebook, marker), {"sys": sys, "os": os, "Path": Path})
    assert "Colab" not in capsys.readouterr().out


def test_verify_environment_kernelspec_list_on_colab(fake_colab, capsys: pytest.CaptureFixture[str]) -> None:
    pytest.importorskip("jupyter_client")
    import os

    exec(_cell("00-02-verify-environment", "find_kernel_specs()"), {"sys": sys, "os": os, "Path": Path})
    out = capsys.readouterr().out
    assert "none is needed" in out and "You will create it" not in out


def test_prepare_runtime_explains_the_runtime_notice(
    colab_runtime, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(colab, "_versions", lambda: {"langchain": "1.4.6"})
    colab.prepare_runtime(REPO, runner=lambda cmd: 0, load_secrets=False)
    assert "Unrecognized runtime lc-mastery" in capsys.readouterr().out


# --- Only the keys a lesson uses are read (each Colab Secrets read can show an access prompt) ---------------


def test_prepare_runtime_reads_only_the_notebooks_secrets(colab_runtime, fake_colab, monkeypatch) -> None:
    monkeypatch.setattr(colab, "_versions", lambda: {})
    fake_colab.secrets.update(GROQ_API_KEY="gsk_x", TAVILY_API_KEY="tvly-x", HF_TOKEN="hf_x")
    assert colab.prepare_runtime(REPO, runner=lambda cmd: 0, secrets=("GROQ_API_KEY",)) == ["GROQ_API_KEY"]
    assert fake_colab.calls == ["GROQ_API_KEY"]
    config.load_env()  # reads the same list again: nothing new is asked
    assert fake_colab.calls == ["GROQ_API_KEY"]  # TAVILY_API_KEY and HF_TOKEN were never read from Colab Secrets


def test_require_env_reads_a_secret_lazily_once(fake_colab, monkeypatch) -> None:
    import os

    config.use_colab_secrets(())
    fake_colab.secrets["TAVILY_API_KEY"] = "tvly-x"
    assert config.load_colab_secrets() == [] and fake_colab.calls == []
    config.require_env("TAVILY_API_KEY")  # needed now: read from Colab Secrets on demand
    assert os.environ["TAVILY_API_KEY"] == "tvly-x"
    assert fake_colab.calls == ["TAVILY_API_KEY"]
    with pytest.raises(config.MissingSettingError):
        config.require_env("DAYTONA_API_KEY")  # missing secret: a clear error, no prompt
    with pytest.raises(config.MissingSettingError):
        config.require_env("DAYTONA_API_KEY")
    assert fake_colab.calls == ["TAVILY_API_KEY", "DAYTONA_API_KEY"]  # each name is looked up once per kernel


def test_optional_keys_are_never_looked_up(fake_colab) -> None:
    config.use_colab_secrets(("GROQ_API_KEY",))
    fake_colab.secrets["LANGSMITH_API_KEY"] = "lsv2_x"
    config.load_colab_secrets()
    assert config.is_set("LANGSMITH_API_KEY") is False  # is_set never reads Colab Secrets
    assert fake_colab.calls == ["GROQ_API_KEY"]


def test_model_key_is_read_lazily(fake_colab) -> None:
    from mastery import models

    config.use_colab_secrets(())
    fake_colab.secrets["GROQ_API_KEY"] = "gsk_x"
    models._require_provider_key("groq")  # no MissingSettingError: read from Colab Secrets on demand
    assert fake_colab.calls == ["GROQ_API_KEY"]


def test_setup_cells_list_their_secrets() -> None:
    """colab_patch writes each lesson's own key list into its setup cell, and only names it uses."""
    import json

    pattern = re.compile(r'prepare_runtime\(REPO_ROOT, secrets=\(([^)]*)\),\s*notebook="([^"]+)"\)')
    checked = 0
    for path in sorted(p for p in (REPO / "modules").glob("**/*.ipynb") if ".ipynb_checkpoints" not in p.parts):
        cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
        setup = [c for c in cells if "prepare_runtime(REPO_ROOT" in "".join(c["source"])]
        if not setup:
            continue
        match = pattern.search("".join(setup[0]["source"]))
        assert match, f"{path.name}: setup cell has no secrets=(...) list (run colab_patch.py)"
        assert match.group(2) == path.name, f"{path.name}: setup cell names another notebook"
        rest = "".join("".join(c["source"]) for c in cells if c is not setup[0])
        for name in re.findall(r'"([A-Z_]+)"', match.group(1)):
            assert name in config.COLAB_SECRET_NAMES and re.search(rf"\b{name}\b", rest), (path.name, name)
        checked += 1
    assert checked > 100


# --- Opened from GitHub or from Drive -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("fileId=1AbCdEfGhIjKlMnOpQrStUvWxYz012345", "drive"),
        ("fileId=https%3A%2F%2Fgithub.com%2Fdiego28e%2Frepo%2Fblob%2Fmain%2Fx.ipynb", "github"),
        ("fileId=/v2/external/notebooks/intro.ipynb", "other"),
    ],
)
def test_notebook_source(monkeypatch, path: str, expected: str) -> None:
    import io
    import json
    import urllib.request

    body = json.dumps([{"path": path}]).encode()
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=1.0: io.BytesIO(body))
    monkeypatch.setattr("socket.gethostbyname", lambda host: "127.0.0.1")
    assert colab.notebook_source() == expected


def test_notebook_source_unknown_on_error(monkeypatch) -> None:
    import urllib.request

    def boom(*args, **kwargs):
        raise OSError("no server")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert colab.notebook_source() == ""


@pytest.mark.parametrize(("source", "tip"), [("github", True), ("other", True), ("drive", False), ("", False)])
def test_prepare_runtime_github_tip(colab_runtime, monkeypatch, capsys, source: str, tip: bool) -> None:
    monkeypatch.setattr(colab, "_versions", lambda: {})
    monkeypatch.setattr(colab, "notebook_source", lambda timeout=1.0: source)
    colab.prepare_runtime(REPO, runner=lambda cmd: 0, load_secrets=False)
    out = capsys.readouterr().out
    assert ("Opened from GitHub: your edits won't be saved; open it from Drive" in out) is tip


def test_drive_folder_url_falls_back_to_my_drive(tmp_path: Path) -> None:
    assert colab.drive_folder_url(tmp_path).startswith("https://drive.google.com/drive/")


# --- Links between notebooks: relative links open as a Drive file id on Colab ("file missing") -----------
LESSON = "01-02-messages-and-content-blocks.ipynb"


def fake_xattr(monkeypatch: pytest.MonkeyPatch, ids: dict[str, str] | None = None) -> None:
    """os.getxattr as Colab's Drive mount answers it: an id per file name (``ids``), else ENODATA."""

    def getxattr(path: str, attribute: str) -> bytes:
        assert attribute == "user.drive.id"
        name = Path(path).name
        if ids is None or name not in ids:
            raise OSError(61, "No data available")
        return ids[name].encode()

    monkeypatch.setattr(colab.os, "getxattr", getxattr, raising=False)
    monkeypatch.setattr(colab.shutil, "which", lambda _: None)


def test_drive_file_id_reads_the_drive_xattr(monkeypatch, tmp_path: Path) -> None:
    fake_xattr(monkeypatch, {"a.ipynb": "1AbCdEfGhIjKlMnOp_-x"})
    assert colab.drive_file_id(tmp_path / "a.ipynb") == "1AbCdEfGhIjKlMnOp_-x"
    assert colab.drive_file_id(tmp_path / "b.ipynb") is None  # not on Drive: no id, no error
    assert colab.drive_folder_url(tmp_path / "a.ipynb").endswith("/folders/1AbCdEfGhIjKlMnOp_-x")


def test_drive_file_id_falls_back_to_the_xattr_tool(monkeypatch, tmp_path: Path) -> None:
    def no_getxattr(path: str, attribute: str) -> bytes:
        raise OSError(95, "Operation not supported")

    monkeypatch.setattr(colab.os, "getxattr", no_getxattr, raising=False)
    monkeypatch.setattr(colab.shutil, "which", lambda tool: "/usr/bin/xattr" if tool == "xattr" else None)
    ran: list[list[str]] = []

    def run(cmd, **kwargs):
        ran.append(cmd)
        return types.SimpleNamespace(stdout=b"1ZyXwVuTsRqPoNmLk\n")

    monkeypatch.setattr(colab.subprocess, "run", run)
    assert colab.drive_file_id(tmp_path / "x.ipynb") == "1ZyXwVuTsRqPoNmLk"
    assert ran[0][:3] == ["/usr/bin/xattr", "-p", "user.drive.id"]

    def fails(cmd, **kwargs):
        raise colab.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(colab.subprocess, "run", fails)
    assert colab.drive_file_id(tmp_path / "x.ipynb") is None


def test_lesson_links_open_the_drive_copies(monkeypatch) -> None:
    ids = {"01-01-chat-models.ipynb": "1PrevPrevPrevPrevPrev", "01-03-prompting-fundamentals.ipynb": "1NextNextNextNext",
           "README.md": "1ReadmeReadmeReadme"}
    fake_xattr(monkeypatch, ids)
    links = colab.lesson_links(REPO, LESSON)
    urls = [url for _, url, _ in links]
    assert links[0][0].startswith("Previous lesson: 01-01")
    assert urls[0] == "https://colab.research.google.com/drive/1PrevPrevPrevPrevPrev"
    nxt = "https://colab.research.google.com/drive/1NextNextNextNext"
    assert ("Next lesson: 01-03-prompting-fundamentals.ipynb", nxt, True) in links
    assert "https://drive.google.com/file/d/1ReadmeReadmeReadme/view" in urls  # the module README, in Drive's viewer
    assert not any("file/u/0/d/" in url or url.endswith((".ipynb/edit", "/edit")) for url in urls)
    assert len(urls) == len(set(urls))


def test_lesson_links_fall_back_to_github_and_say_it_does_not_save(monkeypatch, capsys) -> None:
    fake_xattr(monkeypatch)  # clone not on Drive (or no id exposed)
    links = colab.lesson_links(REPO, f"modules/01-models-messages-prompts/{LESSON}")
    nxt = next(link for link in links if link[0].startswith("Next lesson"))
    assert nxt[1].startswith("https://colab.research.google.com/github/")
    assert nxt[1].endswith("/blob/main/modules/01-models-messages-prompts/01-03-prompting-fundamentals.ipynb")
    assert nxt[2] is False
    monkeypatch.setitem(sys.modules, "IPython.display", None)  # no IPython: plain text
    assert colab.show_lesson_links(REPO, LESSON) == len(links)
    out = capsys.readouterr().out
    assert "On Colab, open other lessons with these links" in out and "GitHub copy: edits won't be saved" in out


def test_show_lesson_links_renders_html_and_never_raises(monkeypatch) -> None:
    fake_xattr(monkeypatch, {"01-03-prompting-fundamentals.ipynb": "1NextNextNextNextNext"})
    shown: list[str] = []
    display_module = types.ModuleType("IPython.display")
    display_module.HTML = lambda html: html  # type: ignore[attr-defined]
    display_module.display = shown.append  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "IPython.display", display_module)
    assert colab.show_lesson_links(REPO, LESSON) > 0
    assert '<a href="https://colab.research.google.com/drive/1NextNextNextNextNext" target="_blank">' in shown[0]
    assert colab.show_lesson_links(REPO, "no-such-notebook.ipynb") == 0
    monkeypatch.setattr(colab, "lesson_links", lambda *a: 1 / 0)
    assert colab.show_lesson_links(REPO, LESSON) == 0


def test_prepare_runtime_shows_the_links_for_its_notebook(colab_runtime, monkeypatch) -> None:
    monkeypatch.setattr(colab, "_versions", lambda: {})
    shown: list[tuple] = []
    monkeypatch.setattr(colab, "show_lesson_links", lambda root, notebook: shown.append((root, notebook)) or 1)
    colab.prepare_runtime(REPO, runner=lambda cmd: 0, load_secrets=False, notebook=LESSON)
    assert shown == [(REPO, LESSON)]


def test_notebook_names_are_unique_so_the_setup_cell_can_pass_just_the_name() -> None:
    names = [p.name for p in (REPO / "modules").rglob("*.ipynb") if ".ipynb_checkpoints" not in p.parts]
    assert len(names) == len(set(names))


def test_whats_next_cells_point_colab_learners_to_the_printed_links() -> None:
    import json

    checked = 0
    for path in sorted(p for p in (REPO / "modules").glob("**/*.ipynb") if ".ipynb_checkpoints" not in p.parts):
        cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
        has_setup = any("prepare_runtime(REPO_ROOT" in "".join(c["source"]) for c in cells)
        for cell in cells:
            src = "".join(cell["source"])
            if cell["cell_type"] == "markdown" and "## ➡️ What's next" in src:
                notes = [line for line in src.splitlines() if line.endswith("the links below work on PC/GitHub.")]
                assert len(notes) == 1, path.name
                assert ("links the setup cell printed" in notes[0]) is has_setup, path.name
                checked += 1
    assert checked > 100


def test_start_here_says_nothing_to_upload_and_how_to_open_lessons() -> None:
    text = (REPO / "colab" / "START_HERE.ipynb").read_text(encoding="utf-8")
    for phrase in (
        "You do NOT upload anything",
        "My Drive/langchain-langgraph-mastery",
        "Open with",
        "Google Colaboratory",
        "Save in GitHub",
        "File → Open notebook → Recent",
        "only lists notebooks you opened recently",
        "drive_folder_url",
        "drive_file_id",
    ):
        assert phrase in text, phrase


def test_header_rows_carry_the_github_tip() -> None:
    import json

    rows = 0
    for path in sorted(p for p in (REPO / "modules").glob("**/*.ipynb") if ".ipynb_checkpoints" not in p.parts):
        first = "".join(json.loads(path.read_text(encoding="utf-8"))["cells"][0]["source"])
        for line in first.splitlines():
            if line.startswith("| ☁️ Google Colab |") and "colab-badge" in line:
                assert "Save in GitHub" in line and "#open-lessons" in line, path.name
                rows += 1
    assert rows > 100
