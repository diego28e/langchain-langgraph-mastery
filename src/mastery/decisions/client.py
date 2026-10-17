"""Build a Jev classifier in the right mode, and read its answers.

Modes (``MASTERY_DECISIONS_MODE``):

* ``auto`` (default): ``live`` when ``TYPESAFE_API_KEY`` is set, otherwise ``replay``.
* ``live``: real calls to ``TYPESAFE_BASE_URL`` (default ``https://api.typesafe.ai``), billed.
* ``replay``: answers come from a recordings file; no key, no network, no cost.
* ``record``: live calls, and every answer is saved to the recordings file (maintainer use).

The model is pinned (``MASTERY_DECISION_MODEL``, default ``jev-1.13.0``) instead of
``jev-latest``: the alias moves to each new release, and a decision you tuned thresholds for
should not change under you without a re-evaluation (Lesson 15.02).
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx2

from mastery.decisions.replay import (RECORDINGS_DIR, AsyncRecordingTransport, RecordingTransport, ReplayStore,
                                      ReplayTransport)

__all__ = ["DEFAULT_MODEL", "MODES", "DecisionSetup", "answer_rows", "decision_classifier", "decision_cost",
           "decisions_mode", "provenance", "with_rate_limit_retry"]

DEFAULT_MODEL = "jev-1.13.0"
MODES = ("auto", "live", "replay", "record")
REPLAY_KEY = "replay-mode-no-key"


def decisions_mode(mode: str | None = None) -> str:
    """Resolve ``auto`` to ``live`` or ``replay``. Raises ``ValueError`` on an unknown mode."""
    raw = (mode or os.environ.get("MASTERY_DECISIONS_MODE") or "auto").strip().lower()
    if raw not in MODES:
        raise ValueError(f"MASTERY_DECISIONS_MODE must be one of {MODES}, not {raw!r}")
    if raw == "auto":
        return "live" if os.environ.get("TYPESAFE_API_KEY", "").strip() else "replay"
    if raw in ("live", "record") and not os.environ.get("TYPESAFE_API_KEY", "").strip():
        raise ValueError(f"MASTERY_DECISIONS_MODE={raw} needs TYPESAFE_API_KEY (see the module README, Setup).")
    return raw


@dataclass
class DecisionSetup:
    """What :func:`decision_classifier` built: the classifier plus how it will answer."""

    classifier: Any
    mode: str
    model: str
    base_url: str
    store: ReplayStore | None = None

    def describe(self) -> str:
        if self.mode == "replay":
            share = self.store.synthetic_share() if self.store else 0.0
            return (f"replay · {len(self.store or [])} recorded requests in {self.store.path.name}"
                    f" ({share:.0%} synthetic) · no key, no network, $0")
        return f"{self.mode} · {self.model} at {self.base_url}"


def decision_classifier(*, mode: str | None = None, model: str | None = None,
                        recordings: Path | str | None = None, timeout: float = 30.0) -> DecisionSetup:
    """A ``TypeSafeClassifier`` for ``mode`` (see the module docstring), wrapped in a :class:`DecisionSetup`."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")        # LangChainBetaWarning on import/construction: said in Markdown
        from langchain_typesafe import TypeSafeClassifier

    resolved = decisions_mode(mode)
    model = model or os.environ.get("MASTERY_DECISION_MODEL", "").strip() or DEFAULT_MODEL
    base_url = os.environ.get("TYPESAFE_BASE_URL", "").strip() or "https://api.typesafe.ai"
    path = Path(recordings) if recordings else RECORDINGS_DIR / "recordings.json"
    store = ReplayStore(path) if resolved in ("replay", "record") else None
    kwargs: dict[str, Any] = {"model": model, "base_url": base_url, "timeout": timeout, "name": f"jev[{resolved}]"}
    if resolved == "replay":
        # Both clients: ainvoke/abatch use async_client, and must never reach the network in replay.
        replay = ReplayTransport(store)
        kwargs.update(api_key=REPLAY_KEY, client=httpx2.Client(transport=replay),
                      async_client=httpx2.AsyncClient(transport=replay))
    elif resolved == "record":
        kwargs["client"] = httpx2.Client(transport=RecordingTransport(httpx2.HTTPTransport(), store), timeout=timeout)
        kwargs["async_client"] = httpx2.AsyncClient(
            transport=AsyncRecordingTransport(httpx2.AsyncHTTPTransport(), store), timeout=timeout)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        classifier = TypeSafeClassifier(**kwargs)
    return DecisionSetup(classifier, resolved, model, base_url, store)


def provenance(response: Any) -> str:
    """``"live"``, ``"replay (recorded)"``, ``"replay (synthetic)"`` or ``"llm fallback"``, from ``request_id``."""
    rid = getattr(response, "request_id", None) or ""
    if rid.startswith("llm-fallback"):
        return "llm fallback"
    if rid.startswith("replay-synthetic-"):
        return "replay (synthetic)"
    if rid.startswith("replay-recorded-"):
        return "replay (recorded)"
    return "live"


def answer_rows(response: Any) -> list[dict[str, Any]]:
    """One display row per answer: question, type, answer, probability/confidence, full distribution."""
    rows = []
    for name, answer in response.answers.items():
        if answer.type == "noul":
            rows.append({"question": name, "type": "noul", "answer": "yes" if answer.noul >= 0.5 else "no",
                         "p_yes": round(answer.noul, 3), "confidence": "", "distribution": ""})
        elif answer.type == "choice":
            dist = ", ".join(f"{k}={v:.2f}" for k, v in sorted(answer.probabilities.items(), key=lambda kv: -kv[1]))
            rows.append({"question": name, "type": "choice", "answer": answer.choice, "p_yes": "",
                         "confidence": round(answer.confidence, 3), "distribution": dist})
        else:
            dist = ", ".join(f"{k}={v:.2f}" for k, v in sorted(answer.probabilities.items()))
            rows.append({"question": name, "type": "score", "answer": round(answer.score, 2), "p_yes": "",
                         "confidence": round(answer.confidence, 3), "distribution": dist})
    return rows


def decision_cost(response: Any) -> float | None:
    """Paid-tier cost (USD) of one response from its ``usage``, priced by :mod:`mastery.pricing`."""
    from mastery.pricing import estimate_cost

    usage = response.usage
    return estimate_cost({"input_tokens": usage.input_tokens or 0, "output_tokens": usage.output_tokens or 0},
                         response.model)


def with_rate_limit_retry(classifier: Any, attempts: int = 3) -> Any:
    """Retry ``429`` (``TypeSafeRateLimitError``) with exponential backoff and jitter.

    ``langchain-typesafe`` 0.0.1a3 does not retry by itself (TypeSafe's own SDKs do). Only rate
    limits are retried: a 401 or a validation error would fail the same way again.
    """
    from langchain_typesafe.client import TypeSafeRateLimitError

    return classifier.with_retry(retry_if_exception_type=(TypeSafeRateLimitError,),
                                 wait_exponential_jitter=True, stop_after_attempt=attempts)
