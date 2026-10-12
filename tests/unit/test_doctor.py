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
