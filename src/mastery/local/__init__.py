"""Local models for Module 14: is Ollama running, which models are there, what can they do, how fast are they.

Introduced in Lesson 14.01. Everything here talks to the Ollama HTTP API (``OLLAMA_BASE_URL``, default
``http://localhost:11434``) with short timeouts and never pulls a model by itself: downloads are GBs, so
the learner runs ``ollama pull <name>`` deliberately. ``hub`` (Lesson 14.02) reads Hugging Face model pages.
"""
from mastery.local.ollama import (
    LocalModel,
    ModelMissing,
    OllamaStatus,
    OllamaUnavailable,
    Speed,
    fits_in_memory,
    measure,
    ollama_status,
    require_model,
)

from mastery.local.hub import HubModel, license_verdict, load_snapshot, model_details, ollama_hf_tag, quant_files, search_models

__all__ = ["HubModel", "license_verdict", "load_snapshot", "model_details", "ollama_hf_tag", "quant_files", "search_models",
           "LocalModel", "ModelMissing", "OllamaStatus", "OllamaUnavailable", "Speed", "fits_in_memory", "measure",
           "ollama_status", "require_model"]
