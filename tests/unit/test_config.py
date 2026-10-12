"""Unit tests for mastery.config (Lesson 00.04). No network, no real keys.

Every test uses pytest's ``monkeypatch`` (to set/unset env vars safely; changes
are undone after each test) and ``tmp_path`` (a fresh temporary folder), so
the tests never read or change your real ``.env``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mastery import config
from mastery.config import (
    DEFAULT_MODEL_FAST,
    MissingSettingError,
    env_status,
    find_repo_root,
    is_set,
    load_env,
    load_settings,
    mask_secret,
    require_env,
)

FAKE_KEY = "gsk_FAKE_test_value_1234567890abcdefghijklmnopqrstuvwxyz"  # Not a real key.


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove every variable these tests touch, so the real environment can't leak in."""
    for name in (
        "GROQ_API_KEY",
        "LANGSMITH_API_KEY",
        "LANGSMITH_TRACING",
        "LANGSMITH_PROJECT",
        "MASTERY_MODEL_FAST",
        "MASTERY_MODEL_REASONING",
        "DEMO_VALUE",
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_load_env_reads_file_and_returns_its_path(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"GROQ_API_KEY={FAKE_KEY}\n", encoding="utf-8")

    loaded = load_env(env_file)

    assert loaded == env_file.resolve()
    assert is_set("GROQ_API_KEY")


def test_load_env_searches_parent_folders_from_cwd(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> None:
    # Mimics a notebook in modules/00-foundations with .env at the repo root.
    (tmp_path / ".env").write_text("DEMO_VALUE=from-root\n", encoding="utf-8")
    notebook_dir = tmp_path / "modules" / "00-foundations"
    notebook_dir.mkdir(parents=True)
    clean_env.chdir(notebook_dir)

    loaded = load_env()

    assert loaded == (tmp_path / ".env").resolve()
    assert config.os.environ["DEMO_VALUE"] == "from-root"


def test_load_env_returns_none_when_no_file(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> None:
    assert load_env(tmp_path / "does-not-exist.env") is None


def test_real_environment_wins_unless_override(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DEMO_VALUE=from-file\n", encoding="utf-8")
    clean_env.setenv("DEMO_VALUE", "from-shell")

    load_env(env_file)  # override=False (default): shell value is kept.
    assert config.os.environ["DEMO_VALUE"] == "from-shell"

    load_env(env_file, override=True)  # Explicit override: file value replaces it.
    assert config.os.environ["DEMO_VALUE"] == "from-file"


@pytest.mark.parametrize("value", ["", "   ", "<your-api-key-here>", "your-groq-api-key", "changeme"])
def test_blank_and_placeholder_values_count_as_missing(value: str, clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("GROQ_API_KEY", value)
    assert not is_set("GROQ_API_KEY")


def test_require_env_passes_when_set(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("GROQ_API_KEY", FAKE_KEY)
    assert require_env("GROQ_API_KEY") is None  # Returns nothing on purpose.


def test_require_env_error_is_friendly_and_never_leaks(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("LANGSMITH_API_KEY", FAKE_KEY)  # Present, must not appear in the message.

    with pytest.raises(MissingSettingError) as excinfo:
        require_env("GROQ_API_KEY", "LANGSMITH_API_KEY")

    message = str(excinfo.value)
    assert excinfo.value.missing == ("GROQ_API_KEY",)
    assert "https://console.groq.com/keys" in message
    assert "cp .env.example .env" in message  # No .env path given -> Git Bash hint.
    assert FAKE_KEY not in message


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "<not set>"),
        ("", "<not set>"),
        ("short", "*** (5 chars)"),
        (FAKE_KEY, f"gsk_… ({len(FAKE_KEY)} chars)"),
    ],
)
def test_mask_secret(value: str | None, expected: str) -> None:
    assert mask_secret(value) == expected


def test_mask_secret_caps_visible_characters() -> None:
    masked = mask_secret(FAKE_KEY, visible=40)
    assert masked.startswith("gsk_…")
    assert FAKE_KEY[4:10] not in masked


def test_env_status_never_contains_the_secret(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("GROQ_API_KEY", FAKE_KEY)
    clean_env.setenv("LANGSMITH_API_KEY", "<your-key>")

    status = env_status("GROQ_API_KEY", "LANGSMITH_API_KEY", "OPENAI_API_KEY")

    assert status["GROQ_API_KEY"].startswith("set: gsk_…")
    assert status["LANGSMITH_API_KEY"].startswith("placeholder")
    assert status["OPENAI_API_KEY"] == "missing"
    assert all(FAKE_KEY not in text for text in status.values())


def test_load_settings_uses_verified_defaults(clean_env: pytest.MonkeyPatch) -> None:
    settings = load_settings(load_dotenv_file=False)
    assert settings.model_fast == DEFAULT_MODEL_FAST
    assert settings.langsmith_tracing is False


def test_load_settings_reads_overrides(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("MASTERY_MODEL_FAST", "  some/other-model  ")
    clean_env.setenv("LANGSMITH_TRACING", "TRUE")

    settings = load_settings(load_dotenv_file=False)

    assert settings.model_fast == "some/other-model"  # Whitespace is stripped.
    assert settings.langsmith_tracing is True


def test_settings_are_immutable() -> None:
    settings = load_settings(load_dotenv_file=False)
    with pytest.raises(AttributeError):
        settings.model_fast = "changed"  # type: ignore[misc]


def test_find_repo_root_from_nested_folder(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "COURSE_OUTLINE.md").write_text("", encoding="utf-8")
    nested = tmp_path / "modules" / "00-foundations"
    nested.mkdir(parents=True)

    assert find_repo_root(nested) == tmp_path.resolve()


def test_find_repo_root_raises_outside_repo(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Start Jupyter from inside"):
        find_repo_root(tmp_path)


def test_this_repository_is_found() -> None:
    root = find_repo_root(Path(__file__).parent)
    assert (root / "src" / "mastery" / "config.py").is_file()
