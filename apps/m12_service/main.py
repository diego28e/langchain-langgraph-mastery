"""Orbita Cloud support desk as an HTTP service (Module 12).

Run it from the repository root, with the course env active:

    uvicorn apps.m12_service.main:app --port 8000

DEMO mode (default) uses the offline model: no key, no cost. LIVE mode uses Groq:
set MASTERY_SERVICE_MODE=live and GROQ_API_KEY in .env. Settings: mastery.service.settings.
"""
from pathlib import Path

from mastery.service.app import create_app
from mastery.service.desk import durable_support_manager

# State: MASTERY_SERVICE_DATABASE_URL (sqlite:///… or postgresql://…); in memory when unset.
# The browser UI (Lesson 12.09) is served at /ui/ from apps/m12_service/ui.
app = create_app(durable_support_manager, title="Orbita Cloud support desk", ui_dir=Path(__file__).parent / "ui")
