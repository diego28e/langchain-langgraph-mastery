"""Integration test: the course's configured Groq models are live on YOUR account.

Skipped by default. Run it on purpose (it uses your GROQ_API_KEY and one tiny,
free-of-charge Models API request; no tokens are generated):

    pytest -m integration
"""

from __future__ import annotations

import pytest

from mastery.config import is_set, load_env, load_settings
from mastery.groq_catalog import fetch_groq_models

pytestmark = pytest.mark.integration


def test_configured_models_are_live() -> None:
    load_env()
    if not is_set("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY is not set in .env")

    settings = load_settings(load_dotenv_file=False)
    live_ids = {model.id for model in fetch_groq_models()}

    for model_id in (settings.model_fast, settings.model_reasoning):
        assert model_id in live_ids, (
            f"{model_id} is not in your live Groq model list. "
            "Check https://console.groq.com/docs/deprecations and update MASTERY_MODEL_* in .env."
        )
