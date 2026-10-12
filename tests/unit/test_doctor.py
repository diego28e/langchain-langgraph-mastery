"""Tests for mastery.doctor: a bad SSL_CERT_FILE must give a clear message.

Offline: no network, no keys. ``monkeypatch`` sets the variables for one test
and restores them afterwards.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mastery.config import load_settings
from mastery.doctor import CertificateSettingError, check_ssl_env, require_valid_ssl_env
from mastery.models import get_model

# The exact wrong path Anaconda's Git Bash script produces (Lesson 00.02, step 4b).
BAD_PATH = "C:/Users/learner/anaconda3/envs/lc-mastery/ssl/cacert.pem"


@pytest.fixture
def no_ssl_vars(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    return monkeypatch


def test_unset_or_empty_is_fine() -> None:
    assert check_ssl_env({}) == []
    assert check_ssl_env({"SSL_CERT_FILE": "", "SSL_CERT_DIR": ""}) == []


def test_existing_file_and_dir_are_fine(tmp_path: Path) -> None:
    bundle = tmp_path / "cacert.pem"
    bundle.write_text("dummy")
    assert check_ssl_env({"SSL_CERT_FILE": str(bundle), "SSL_CERT_DIR": str(tmp_path)}) == []


def test_missing_file_and_dir_are_reported(tmp_path: Path) -> None:
    problems = check_ssl_env({"SSL_CERT_FILE": BAD_PATH, "SSL_CERT_DIR": str(tmp_path / "nope")})
    assert len(problems) == 2
    assert BAD_PATH in problems[0]


def test_error_message_contains_the_fix() -> None:
    with pytest.raises(CertificateSettingError) as info:
        require_valid_ssl_env({"SSL_CERT_FILE": BAD_PATH})
    message = str(info.value)
    assert BAD_PATH in message
    assert "conda env config vars set SSL_CERT_FILE" in message
    assert "Library/ssl/cacert.pem" in message


def test_get_model_raises_clear_error(no_ssl_vars: pytest.MonkeyPatch) -> None:
    no_ssl_vars.setenv("SSL_CERT_FILE", BAD_PATH)
    # check_key=False: the test needs no API key. The doctor runs before the SDK client.
    with pytest.raises(CertificateSettingError, match="SSL_CERT_FILE"):
        get_model("fast", check_key=False)


def test_load_settings_raises_clear_error(no_ssl_vars: pytest.MonkeyPatch) -> None:
    no_ssl_vars.setenv("SSL_CERT_FILE", BAD_PATH)
    with pytest.raises(CertificateSettingError):
        load_settings(load_dotenv_file=False)


def test_course_stack_dependencies_are_consistent() -> None:
    """A focused `pip check`: fails on version conflicts in the langgraph/langchain/opentelemetry/grpc/chroma stack."""
    from mastery.doctor import check_dependencies

    problems = check_dependencies()
    assert not problems, "Fix with the commands in modules/06-rag/README.md (Before you start):\n" + "\n".join(problems)


def test_check_dependencies_reports_unmet_requirements(monkeypatch) -> None:
    from importlib import metadata

    from mastery import doctor

    class Dist:
        def __init__(self, name, version, requires=()):
            self.metadata = {"Name": name}
            self.version = version
            self.requires = list(requires)

    fake = [Dist("opentelemetry-exporter-prometheus", "0.63b1", ["opentelemetry-sdk~=1.42.1"]),
            Dist("opentelemetry-sdk", "1.45.1"), Dist("langgraph-api", "0.10.3"),
            Dist("langchain-x", "1.0", ['missing-pkg>=1; extra == "never"'])]
    monkeypatch.setattr(metadata, "distributions", lambda: fake)
    problems = doctor.check_dependencies()
    assert any("opentelemetry-sdk~=1.42.1, but 1.45.1" in p for p in problems)
    assert any("langgraph-api 0.10.3 is older than 0.16.0" in p for p in problems)
    assert not any("missing-pkg" in p for p in problems)          # extras-only requirements are ignored
