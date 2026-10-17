"""Recorded predictions: a router's answers on a ticket set, saved once and compared offline.

A file records who produced it, when, with which prompt, and what it cost, so a comparison months later
(or on a machine without the model) is honest about where the numbers come from.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

__all__ = ["save_predictions", "load_predictions", "RECORDED_DIR"]

RECORDED_DIR = Path(__file__).resolve().parents[3] / "data" / "samples" / "local" / "predictions"


def save_predictions(path: Path | str, model: str, labels: dict[str, str], *, confidence: dict[str, float] | None = None,
                     recorded: str | None = None, **meta: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"model": model, "recorded": recorded or date.today().isoformat(), **meta,
            "labels": dict(sorted(labels.items()))}
    if confidence:
        data["confidence"] = {k: round(v, 4) for k, v in sorted(confidence.items())}
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_predictions(path: Path | str) -> dict[str, Any]:
    """``{"model", "recorded", "labels": {id: queue}, ...}``."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
