"""Decision models for Module 15: Jev (TypeSafe's System One model) through ``langchain-typesafe``.

Introduced in Lesson 15.01. :func:`decision_classifier` returns a ``TypeSafeClassifier`` that runs
**live** with ``TYPESAFE_API_KEY`` or in **replay** from recorded answers (no key, no network), so
every Module 15 notebook completes for learners without a TypeSafe balance.
``langchain-typesafe`` is an alpha (0.0.1a3, pinned): this package is the one place to fix if its API moves.
"""
from mastery.decisions.client import (
    DEFAULT_MODEL,
    MODES,
    DecisionSetup,
    answer_rows,
    decision_classifier,
    decision_cost,
    decisions_mode,
    provenance,
    with_rate_limit_retry,
)
from mastery.decisions.llm_fallback import llm_decider
from mastery.decisions.policy import Band, BandCosts, apply_band, band_cost, brier_score, choose_band, margin, top_probability
from mastery.decisions.replay import AsyncRecordingTransport, RECORDINGS_DIR, RecordingTransport, ReplayMiss, ReplayStore, ReplayTransport, request_key

__all__ = ["Band", "BandCosts", "apply_band", "band_cost", "brier_score", "choose_band", "llm_decider", "margin",
           "top_probability", "AsyncRecordingTransport", "DEFAULT_MODEL", "MODES", "RECORDINGS_DIR", "DecisionSetup", "RecordingTransport", "ReplayMiss", "ReplayStore",
           "ReplayTransport", "answer_rows", "decision_classifier", "decision_cost", "decisions_mode", "provenance",
           "request_key", "with_rate_limit_retry"]
