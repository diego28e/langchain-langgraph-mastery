"""mastery.doctor: catch broken environment settings early, with a clear fix.

Today it checks one thing: the TLS certificate variables ``SSL_CERT_FILE`` and
``SSL_CERT_DIR``.

Why this exists
---------------
Python's ``ssl`` module, and ``httpx`` (used by the Groq, OpenAI and LangSmith
SDKs), trust whatever certificate bundle ``SSL_CERT_FILE`` names. If that
variable points to a file that does not exist, every HTTPS client fails at
*construction* time with a cryptic::

    FileNotFoundError: [Errno 2] No such file or directory

raised from ``ssl.create_default_context`` / ``load_verify_locations``.
The classic cause in this course: Anaconda's ``openssl`` package on Windows
ships a Git Bash activation script that sets
``SSL_CERT_FILE=$CONDA_PREFIX/ssl/cacert.pem``, but the real file lives at
``$CONDA_PREFIX/Library/ssl/cacert.pem``. (Upstream:
https://github.com/ContinuumIO/anaconda-issues/issues/13509 and
https://github.com/AnacondaRecipes/openssl-feedstock/pull/45.)

``get_model`` and ``load_settings`` call :func:`require_valid_ssl_env`, so you
get an actionable message instead of a stack trace deep inside ``httpx``.
See Lesson 00.02, step 4b.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

__all__ = ["CertificateSettingError", "check_ssl_env", "require_valid_ssl_env"]

FIX_HINT = (
    "Fix (Git Bash on Windows, with the course env active):\n"
    '    conda env config vars set SSL_CERT_FILE="$(cygpath -m "$CONDA_PREFIX")/Library/ssl/cacert.pem"\n'
    "    conda deactivate && conda activate lc-mastery\n"
    "Elsewhere: point the variable at a real CA bundle, or `unset` it so certifi's\n"
    "bundle is used. Details: modules/00-foundations/00-02-create-course-env.md, step 4b."
)


class CertificateSettingError(RuntimeError):
    """An SSL certificate variable points to a path that does not exist."""


def check_ssl_env(environ: Mapping[str, str] | None = None) -> list[str]:
    """Return one human-readable problem per broken certificate variable.

    An empty list means "nothing wrong". Unset or empty variables are fine:
    then the SDKs fall back to certifi's bundle.

    Args:
        environ: Mapping to inspect. Defaults to ``os.environ`` (tests pass a dict).
    """
    env = os.environ if environ is None else environ
    problems = []
    cert_file = env.get("SSL_CERT_FILE", "")
    if cert_file and not Path(cert_file).is_file():
        problems.append(f"SSL_CERT_FILE points to a file that does not exist: {cert_file}")
    cert_dir = env.get("SSL_CERT_DIR", "")
    # httpx only reads SSL_CERT_DIR when SSL_CERT_FILE is unset, but Python's
    # ssl module may read both, so a bad directory is reported too.
    if cert_dir and not Path(cert_dir).is_dir():
        problems.append(f"SSL_CERT_DIR points to a folder that does not exist: {cert_dir}")
    return problems


def require_valid_ssl_env(environ: Mapping[str, str] | None = None) -> None:
    """Raise :class:`CertificateSettingError` (with the fix) if a variable is broken."""
    problems = check_ssl_env(environ)
    if problems:
        raise CertificateSettingError("\n".join([*problems, "", FIX_HINT]))
