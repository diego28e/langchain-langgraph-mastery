"""Offline tests for Google Colab support (mastery.colab and config.load_colab_secrets).

google.colab is faked with a module in sys.modules: nothing here needs Colab, the network or a real install.
"""

from __future__ import annotations

import json
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
    monkeypatch.setattr(colab, "installed_root", lambda: None)  # not this test env's own install
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


# --- Drive lag: a folder git (or another runtime) just wrote can take seconds to show on the Drive mount ---------
class FakeGit:
    """Fakes subprocess.run for START_HERE's Step 2: `git clone` "succeeds" but Drive shows the folder only after
    `show_after` one-second waits (never if None). `git -C <missing folder>` fails like real git, no traceback."""

    def __init__(self, show_after: int | None) -> None:
        self.show_after, self.calls, self.sleeps, self.target = show_after, [], 0, None

    def run(self, command, **kwargs):
        import subprocess

        assert "cwd" not in kwargs or kwargs["cwd"] is None  # git -C instead: a missing cwd is a traceback
        self.calls.append(command[1:])
        if command[1] == "clone":
            self.target = Path(command[-1])
        if command[1] == "-C" and not Path(command[2]).is_dir():
            return subprocess.CompletedProcess(command, 128, "", f"fatal: cannot change to '{command[2]}'")
        empty = "" if kwargs.get("text") else b""
        return subprocess.CompletedProcess(command, 0, empty, empty)

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        if self.target is not None and self.sleeps == self.show_after:
            (self.target / ".git").mkdir(parents=True)


def _run_step2(monkeypatch: pytest.MonkeyPatch, drive: Path, fake: FakeGit) -> dict:
    import subprocess
    import time

    monkeypatch.setenv("COLAB_RELEASE_TAG", "test")
    monkeypatch.setattr(subprocess, "run", fake.run)
    monkeypatch.setattr(time, "sleep", fake.sleep)
    code = [cell for cell in _start_here() if cell["cell_type"] == "code"]
    namespace: dict[str, object] = {}
    exec("".join(code[0]["source"]), namespace)  # Step 1: settings
    exec("".join(code[1]["source"]).replace('"/content/drive/MyDrive"', repr(str(drive))), namespace)
    return namespace


def test_start_here_waits_for_a_clone_drive_shows_late(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGit(show_after=3)
    namespace = _run_step2(monkeypatch, tmp_path, fake)
    root = tmp_path / "langchain-langgraph-mastery"
    assert namespace["REPO_ROOT"] == root
    assert fake.calls[0][:3] == ["clone", "--branch", "main"] and fake.calls[0][-1] == str(root)  # the exact REPO_ROOT
    assert fake.calls[1] == ["-C", str(root), "config", "core.fileMode", "false"]  # only once .git exists
    assert fake.sleeps == 3
    out = capsys.readouterr().out
    assert "✅ Course cloned" in out and "⚠️" not in out


def test_start_here_explains_a_clone_drive_never_shows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGit(show_after=None)
    with pytest.raises(RuntimeError, match="not visible") as caught:
        _run_step2(monkeypatch, tmp_path, fake)
    assert caught.value.__suppress_context__
    assert [call[0] for call in fake.calls] == ["clone"]  # git config never ran without .git
    assert fake.sleeps == 30
    out = capsys.readouterr().out
    assert "✅ Course cloned" not in out
    for phrase in (str(tmp_path / "langchain-langgraph-mastery" / ".git"), "Wait a minute", "drive.google.com",
                   "Disconnect and delete runtime"):
        assert phrase in out, phrase


def test_start_here_updates_an_existing_clone_with_git_c(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "langchain-langgraph-mastery"
    (root / ".git").mkdir(parents=True)
    fake = FakeGit(show_after=None)
    _run_step2(monkeypatch, tmp_path, fake)
    assert fake.calls == [["-C", str(root), "config", "core.fileMode", "false"],
                          ["-C", str(root), "fetch", "origin", "main"],
                          ["-C", str(root), "rev-parse", "HEAD"],
                          ["-C", str(root), "rev-parse", "FETCH_HEAD"],  # nothing fetched: nothing touched
                          ["-C", str(root), "config", "core.fileMode", "false"]]
    assert fake.sleeps == 0


# --- Updating a clone Colab (or the learner) changed: a real git repo, no network -----------------------------
def _nb(*sources: str, outputs: bool = False) -> str:
    cells = []
    for source in sources:
        cell = {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source}
        if outputs:
            cell.update(execution_count=3, metadata={"colab": {"base_uri": "https://localhost:8080/"}},
                        outputs=[{"name": "stdout", "output_type": "stream", "text": ["hi\n"]}])
        cells.append(cell)
    metadata = {"colab": {"provenance": []}, "kernelspec": {"name": "python3"}} if outputs else {}
    return json.dumps({"cells": cells, "metadata": metadata, "nbformat": 4, "nbformat_minor": 5}, indent=1)


def _git(repo: Path, *args: str) -> str:
    import subprocess

    result = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip()


@pytest.fixture
def drive_clone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    """origin (a local repo standing in for GitHub), a clone in a fake My Drive, and the fake My Drive."""
    import os
    import shutil

    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    for name, value in {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                        "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@example.com"}.items():
        monkeypatch.setenv(name, value)
    origin, drive = tmp_path / "origin", tmp_path / "My Drive"
    (origin / "modules" / "project").mkdir(parents=True)
    _git(origin, "init", "-q")
    _git(origin, "checkout", "-q", "-b", "main")
    (origin / "modules" / "lesson.ipynb").write_text(_nb("print('v1')"), encoding="utf-8")
    (origin / "modules" / "project" / "exercise.ipynb").write_text(_nb("# TODO: your code"), encoding="utf-8")
    (origin / "notes.md").write_text("course notes\n", encoding="utf-8")
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "v1")
    drive.mkdir()
    _git(drive, "clone", "-q", str(origin), "langchain-langgraph-mastery")
    (origin / "modules" / "lesson.ipynb").write_text(_nb("print('v2')"), encoding="utf-8")
    (origin / "notes.md").write_text("course notes v2\n", encoding="utf-8")
    _git(origin, "commit", "-q", "-am", "v2")
    return origin, drive / "langchain-langgraph-mastery", drive


def _run_update(monkeypatch: pytest.MonkeyPatch, drive: Path, **settings: object) -> None:
    monkeypatch.setenv("COLAB_RELEASE_TAG", "test")
    code = [cell for cell in _start_here() if cell["cell_type"] == "code"]
    namespace: dict[str, object] = {}
    exec("".join(code[0]["source"]), namespace)
    assert namespace["UPDATE_MY_EDITED_LESSONS"] is False  # default: your edited lessons are never replaced
    namespace.update(settings)
    exec("".join(code[1]["source"]).replace('"/content/drive/MyDrive"', repr(str(drive))), namespace)


def _backups(drive: Path) -> list[Path]:
    edits = drive / "langchain-langgraph-mastery-my-edits"
    return sorted(p.relative_to(edits) for p in edits.glob("*/**/*") if p.is_file()) if edits.exists() else []


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _same_head(clone: Path, origin: Path) -> bool:
    return _git(clone, "rev-parse", "HEAD") == _git(origin, "rev-parse", "HEAD")


def test_start_here_resets_notebooks_colab_only_saved_and_updates(
    monkeypatch: pytest.MonkeyPatch, drive_clone: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    origin, clone, drive = drive_clone
    (clone / "modules" / "lesson.ipynb").write_text(_nb("print('v1')", outputs=True), encoding="utf-8")  # Colab ran it
    _run_update(monkeypatch, drive)
    out = capsys.readouterr().out
    assert _same_head(clone, origin)
    assert "print('v2')" in _read(clone / "modules" / "lesson.ipynb")
    assert _git(clone, "status", "--porcelain") == ""
    assert _backups(drive) == []
    assert "✅ Course updated." in out and "Kept your work" not in out and "❌" not in out


def test_start_here_keeps_an_edited_lesson_in_place_while_the_rest_updates(
    monkeypatch: pytest.MonkeyPatch, drive_clone: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    origin, clone, drive = drive_clone
    exercise = clone / "modules" / "project" / "exercise.ipynb"
    mine = _nb("# TODO: your code", "answer = 42  # my new cell", outputs=True)
    exercise.write_text(mine, encoding="utf-8")
    _run_update(monkeypatch, drive)
    out = capsys.readouterr().out
    assert _same_head(clone, origin)
    assert _read(exercise) == mine  # in place, byte for byte
    assert "print('v2')" in _read(clone / "modules" / "lesson.ipynb") and _read(clone / "notes.md") == "course notes v2\n"
    assert _git(clone, "status", "--porcelain") == "M modules/project/exercise.ipynb"  # (stripped " M")
    [safety] = _backups(drive)  # the silent safety net
    assert Path(*safety.parts[1:]).as_posix() == "modules/project/exercise.ipynb" and safety.parts[0].endswith("_UTC")
    assert _read(drive / "langchain-langgraph-mastery-my-edits" / safety) == mine
    assert "✅ Course updated." in out and "📝 Kept your work in 1 lesson(s): modules/project/exercise.ipynb" in out
    assert "newer version" not in out and "my-edits" not in out


def test_start_here_keeps_an_edited_lesson_the_course_changed_and_says_so(
    monkeypatch: pytest.MonkeyPatch, drive_clone: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    origin, clone, drive = drive_clone
    lesson = clone / "modules" / "lesson.ipynb"
    mine = _nb("print('v1')", "print('my experiment')")
    lesson.write_text(mine, encoding="utf-8")
    _run_update(monkeypatch, drive)
    out = capsys.readouterr().out
    assert _same_head(clone, origin) and _read(lesson) == mine and _read(clone / "notes.md") == "course notes v2\n"
    assert "✅ Course updated." in out and "Kept your work in 1 lesson(s): modules/lesson.ipynb" in out
    assert "A newer version of modules/lesson.ipynb exists" in out and "UPDATE_MY_EDITED_LESSONS = True" in out
    # The next update is not blocked by the kept lesson, and keeps it again.
    (origin / "notes.md").write_text("course notes v3\n", encoding="utf-8")
    (origin / "modules" / "lesson.ipynb").write_text(_nb("print('v3')"), encoding="utf-8")
    _git(origin, "commit", "-q", "-am", "v3")
    _run_update(monkeypatch, drive)
    out = capsys.readouterr().out
    assert _same_head(clone, origin) and _read(lesson) == mine and _read(clone / "notes.md") == "course notes v3\n"
    assert "✅ Course updated." in out and "A newer version of modules/lesson.ipynb exists" in out


def test_start_here_can_replace_edited_lessons_when_asked(
    monkeypatch: pytest.MonkeyPatch, drive_clone: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    origin, clone, drive = drive_clone
    lesson, exercise = clone / "modules" / "lesson.ipynb", clone / "modules" / "project" / "exercise.ipynb"
    mine, my_exercise = _nb("print('v1')", "print('mine')"), _nb("answer = 1")
    lesson.write_text(mine, encoding="utf-8")
    exercise.write_text(my_exercise, encoding="utf-8")
    _run_update(monkeypatch, drive, UPDATE_MY_EDITED_LESSONS=True)
    out = capsys.readouterr().out
    assert _same_head(clone, origin) and "print('v2')" in _read(lesson)  # the course changed it: replaced
    assert _read(exercise) == my_exercise  # the course didn't change it: still kept
    [stamp] = {p.parts[0] for p in _backups(drive)}
    assert _read(drive / "langchain-langgraph-mastery-my-edits" / stamp / "modules" / "lesson.ipynb") == mine
    assert f"🔄 Updated modules/lesson.ipynb to the newer version. Your version: My Drive/langchain-langgraph-mastery-my-edits/{stamp}/modules/lesson.ipynb" in out
    assert "Kept your work in 1 lesson(s): modules/project/exercise.ipynb" in out


def test_start_here_treats_an_older_course_copy_colab_saved_back_as_not_an_edit(
    monkeypatch: pytest.MonkeyPatch, drive_clone: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    origin, clone, drive = drive_clone
    _run_update(monkeypatch, drive)  # updated to v2
    (clone / "modules" / "lesson.ipynb").write_text(_nb("print('v1')", outputs=True), encoding="utf-8")  # old tab saved
    (origin / "notes.md").write_text("course notes v3\n", encoding="utf-8")
    _git(origin, "commit", "-q", "-am", "v3")
    capsys.readouterr()
    _run_update(monkeypatch, drive)
    out = capsys.readouterr().out
    assert _backups(drive) == [] and "Kept your work" not in out and "✅ Course updated." in out
    assert _same_head(clone, origin) and "print('v2')" in _read(clone / "modules" / "lesson.ipynb")


def test_start_here_touches_nothing_when_already_up_to_date(
    monkeypatch: pytest.MonkeyPatch, drive_clone: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    origin, clone, drive = drive_clone
    _run_update(monkeypatch, drive)
    saved = _nb("print('v2')", outputs=True)
    (clone / "modules" / "lesson.ipynb").write_text(saved, encoding="utf-8")
    capsys.readouterr()
    _run_update(monkeypatch, drive)
    out = capsys.readouterr().out
    assert "✅ Course is up to date" in out and _read(clone / "modules" / "lesson.ipynb") == saved  # outputs stay
    assert _backups(drive) == []


def test_start_here_explains_a_diverged_clone_and_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, drive_clone: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    origin, clone, drive = drive_clone
    (clone / "notes.md").write_text("committed by me\n", encoding="utf-8")
    _git(clone, "commit", "-q", "-am", "mine")
    head = _git(clone, "rev-parse", "HEAD")
    exercise = clone / "modules" / "project" / "exercise.ipynb"
    exercise.write_text(_nb("answer = 1"), encoding="utf-8")
    _run_update(monkeypatch, drive)
    out = capsys.readouterr().out
    assert _git(clone, "rev-parse", "HEAD") == head and _read(exercise) == _nb("answer = 1")
    assert _backups(drive) == []
    for phrase in ("❌ Could not update the course", "commits of its own", "Nothing was changed",
                   "langchain-langgraph-mastery-old", "Run all"):
        assert phrase in out, phrase


def test_start_here_puts_your_work_back_when_the_update_fails(
    monkeypatch: pytest.MonkeyPatch, drive_clone: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    origin, clone, drive = drive_clone
    (origin / "modules" / "extra.ipynb").write_text(_nb("print('course')"), encoding="utf-8")
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "v3 adds extra")
    (clone / "modules" / "extra.ipynb").write_text(_nb("print('my own file')"), encoding="utf-8")  # same name
    exercise = clone / "modules" / "project" / "exercise.ipynb"
    exercise.write_text(_nb("answer = 1"), encoding="utf-8")
    head = _git(clone, "rev-parse", "HEAD")
    _run_update(monkeypatch, drive)
    out = capsys.readouterr().out
    assert _git(clone, "rev-parse", "HEAD") == head
    assert _read(exercise) == _nb("answer = 1") and "my own file" in _read(clone / "modules" / "extra.ipynb")
    assert "❌ Could not update the course" in out and "same names as new course files" in out
    assert "Kept your work in 1 lesson(s)" in out and "✅" not in out


def test_start_here_changes_nothing_when_the_safety_copy_fails(
    monkeypatch: pytest.MonkeyPatch, drive_clone: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    import shutil

    origin, clone, drive = drive_clone
    (clone / "notes.md").write_text("my notes\n", encoding="utf-8")
    before = _git(clone, "rev-parse", "HEAD")

    def broken_copy(*args: object, **kwargs: object) -> None:
        raise OSError("Drive is full")

    monkeypatch.setattr(shutil, "copy2", broken_copy)
    _run_update(monkeypatch, drive)
    out = capsys.readouterr().out
    assert _read(clone / "notes.md") == "my notes\n" and _git(clone, "rev-parse", "HEAD") == before
    assert "Drive is full" in out and "nothing was changed or updated" in out and "✅" not in out


def test_wait_for_path_waits_for_drive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target, sleeps = tmp_path / "late", []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            target.mkdir(exist_ok=True)

    monkeypatch.setattr(colab.time, "sleep", sleep)
    assert colab.wait_for_path(target) is True and len(sleeps) == 2
    sleeps.clear()
    assert colab.wait_for_path(tmp_path / "never", seconds=5) is False and len(sleeps) == 5  # never raises


def test_colab_repo_root_can_wait_for_a_late_clone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clone = tmp_path / colab.REPO_NAME

    def sleep(seconds: float) -> None:
        (clone / "src" / "mastery").mkdir(parents=True, exist_ok=True)
        (clone / "pyproject.toml").write_text("", encoding="utf-8")

    monkeypatch.setattr(colab, "COLAB_REPO_DIRS", (clone,))
    monkeypatch.setattr(colab.time, "sleep", sleep)
    assert colab.colab_repo_root() is None  # no wait by default
    assert colab.colab_repo_root(wait=10) == clone


def test_prepare_runtime_explains_a_clone_drive_does_not_show(
    fake_colab, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(colab.time, "sleep", lambda seconds: None)
    with pytest.raises(FileNotFoundError, match="wait a minute") as caught:
        colab.prepare_runtime(tmp_path, runner=lambda cmd: pytest.fail("pip must not run"), load_secrets=False)
    assert "pyproject.toml" in str(caught.value) and str(tmp_path) in str(caught.value)


# --- An older mastery in the runtime: "prepare_runtime() got an unexpected keyword argument 'secrets'" ---
def test_every_setup_cell_asks_for_the_current_api_level() -> None:
    notebooks = [p for p in REPO.glob("modules/**/*.ipynb") if ".ipynb_checkpoints" not in p.parts]
    import json

    for path in notebooks:
        cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
        setup = ["".join(c["source"]) for c in cells if "prepare_runtime(REPO_ROOT" in "".join(c["source"])]
        for source in setup:
            assert f'getattr(_course, "API_LEVEL", 1) >= {colab.API_LEVEL}' in source, path
            assert "sys.path.insert(0, str((REPO_ROOT" not in source, path  # the old loader is gone


def test_installed_root_reads_the_editable_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clone = tmp_path / "My Drive clone"
    dist = types.SimpleNamespace(read_text=lambda name: f'{{"url": "{clone.as_uri()}", "dir_info": {{"editable": true}}}}')
    monkeypatch.setattr(colab.metadata, "distribution", lambda name: dist)
    assert colab.installed_root() == clone.resolve()
    monkeypatch.setattr(colab.metadata, "distribution", lambda name: types.SimpleNamespace(read_text=lambda n: None))
    assert colab.installed_root() is None

    def missing(name: str) -> object:
        raise colab.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(colab.metadata, "distribution", missing)
    assert colab.installed_root() is None


def test_prepare_runtime_reinstalls_when_installed_from_another_folder(
    colab_runtime, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(colab, "_versions", lambda: {})
    ran: list[list[str]] = []
    run = lambda cmd: ran.append(list(cmd)) or 0  # noqa: E731
    monkeypatch.setattr(colab, "installed_root", lambda: REPO.resolve())
    colab.prepare_runtime(REPO, runner=run, load_secrets=False)
    colab.prepare_runtime(REPO, runner=run, load_secrets=False)
    assert len(ran) == 1  # installed from this clone: once per runtime
    monkeypatch.setattr(colab, "installed_root", lambda: Path("/content/langchain-langgraph-mastery"))
    colab.prepare_runtime(REPO, runner=run, load_secrets=False)
    assert len(ran) == 2 and str(REPO.resolve()) in " ".join(ran[1])
    assert "reinstalling it from" in capsys.readouterr().out


def test_prepare_runtime_puts_this_clone_first_on_sys_path(colab_runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(colab, "_versions", lambda: {})
    src = str(REPO.resolve() / "src")
    monkeypatch.setattr(sys, "path", ["/somewhere/else", src, *sys.path])
    colab.prepare_runtime(REPO, runner=lambda cmd: 0, load_secrets=False)
    assert sys.path[0] == src and sys.path.count(src) == 1


def test_start_here_step3_never_reuses_an_older_mastery(tmp_path: Path) -> None:
    """Step 3 after Step 2 updated the clone: an older mastery imported earlier must not be the one called."""
    import subprocess

    old = tmp_path / "old" / "mastery"
    old.mkdir(parents=True)
    (old / "__init__.py").write_text("", encoding="utf-8")
    (old / "colab.py").write_text("def prepare_runtime(repo_root):\n    print('OLD')\n", encoding="utf-8")
    step3 = next("".join(c["source"]) for c in _start_here()
                 if c["cell_type"] == "code" and "# Step 3" in "".join(c["source"]))
    script = tmp_path / "step3.py"
    script.write_text(
        f"import sys\nfrom pathlib import Path\nsys.path.insert(0, {str(old.parent)!r})\nimport mastery.colab\n"
        f"IN_COLAB = True\nREPO_ROOT = Path({str(REPO)!r})\n" + step3
        + "\nimport mastery.colab as now\nprint('LOADED', Path(now.__file__).resolve())\n",
        encoding="utf-8",
    )
    env = {k: v for k, v in __import__("os").environ.items() if k != "COLAB_RELEASE_TAG"}  # prepare_runtime: no-op
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, encoding="utf-8",
                            env={**env, "PYTHONIOENCODING": "utf-8"}, timeout=120)
    assert result.returncode == 0, result.stderr
    assert "OLD" not in result.stdout
    assert f"LOADED {(REPO / 'src' / 'mastery' / 'colab.py').resolve()}" in result.stdout

