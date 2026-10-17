"""Read the Hugging Face Hub like a model shortlist: licence, gating, files and sizes (Lesson 14.02).

Everything here uses the **free, public** Hub API (``huggingface_hub.HfApi``): no token is needed to search
public models or read their cards and file lists. A token (``HF_TOKEN``) only matters for gated models,
private repos and paid Inference Providers. ``huggingface_hub`` is imported lazily, so ``import
mastery.local`` works without it, and every function that touches the network has an offline twin
working on a recorded snapshot (``data/samples/local/hub-snapshot.json``).

VERIFIED 2026-10-16 with huggingface-hub 1.33.0 and 2.2.0: ``list_models(search=, filter=, sort=, limit=,
expand=)``, ``model_info(repo_id, files_metadata=True)`` (``siblings[].size``), ``card_data["license"]``,
``gated`` (``False``, ``"auto"`` or ``"manual"``).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["HubModel", "PERMISSIVE", "NON_COMMERCIAL", "license_verdict", "to_hub_model", "search_models",
           "model_details", "quant_files", "ollama_hf_tag", "load_snapshot", "save_snapshot", "GB"]

GB = 1024**3
# SPDX-style ids the Hub uses in model cards. Permissive: commercial use allowed with attribution.
PERMISSIVE = frozenset({"apache-2.0", "mit", "bsd-2-clause", "bsd-3-clause", "cc-by-4.0", "cc0-1.0", "openrail",
                        "bigscience-openrail-m", "creativeml-openrail-m", "unlicense", "isc", "artistic-2.0"})
NON_COMMERCIAL = re.compile(r"(^|-)nc(-|$)|non-?commercial|research", re.I)
_QUANT = re.compile(r"(?<![A-Za-z0-9])((?:I?Q\d+(?:_[A-Z0-9]+)*)|F16|BF16|F32)(?=[.-])", re.I)


@dataclass(frozen=True)
class HubModel:
    """What a team needs from a model page before trying the model."""

    id: str
    license: str | None = None
    gated: str | bool = False            # False, "auto" (click to accept) or "manual" (owner approves)
    pipeline_tag: str | None = None
    downloads: int | None = None
    likes: int | None = None
    files: tuple[tuple[str, int | None], ...] = field(default_factory=tuple)

    @property
    def verdict(self) -> str:
        return license_verdict(self.license)

    @property
    def needs_token(self) -> bool:
        return bool(self.gated)

    def size_gb(self, suffix: str = ".safetensors") -> float | None:
        """Total size of files ending in ``suffix`` (``None`` if sizes weren't requested)."""
        sizes = [s for name, s in self.files if name.endswith(suffix)]
        if not sizes or any(s is None for s in sizes):
            return None
        return round(sum(sizes) / GB, 2)


def license_verdict(license: str | None) -> str:
    """``permissive`` · ``non-commercial`` · ``read the terms`` (custom licences such as llama3.2, gemma) · ``unknown``."""
    if not license:
        return "unknown"
    lic = license.strip().lower()
    if lic in PERMISSIVE:
        return "permissive"
    if NON_COMMERCIAL.search(lic):
        return "non-commercial"
    return "read the terms"


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def to_hub_model(info: Any) -> HubModel:
    """Build a :class:`HubModel` from ``huggingface_hub`` ``ModelInfo`` (any 1.x/2.x) or a snapshot dict."""
    card = _get(info, "card_data") or _get(info, "cardData") or {}
    license = _get(info, "license") or (card.get("license") if isinstance(card, dict) else getattr(card, "license", None))
    if isinstance(license, list):
        license = license[0] if license else None
    files = _get(info, "files")
    if files is None:
        files = [(_get(s, "rfilename"), _get(s, "size")) for s in (_get(info, "siblings") or [])]
    return HubModel(id=_get(info, "id") or _get(info, "modelId"), license=license, gated=_get(info, "gated") or False,
                    pipeline_tag=_get(info, "pipeline_tag"), downloads=_get(info, "downloads"),
                    likes=_get(info, "likes"), files=tuple((n, s) for n, s in files))


def _api(api: Any = None) -> Any:
    if api is not None:
        return api
    from huggingface_hub import HfApi  # lazy: optional dependency

    return HfApi()


def search_models(query: str, *, task: str | None = None, limit: int = 5, api: Any = None) -> list[HubModel]:
    """Most-downloaded public models matching ``query`` (network, no token)."""
    found = _api(api).list_models(search=query, filter=task, sort="downloads", limit=limit,
                                  expand=["downloads", "likes", "gated", "pipeline_tag", "cardData"])
    return [to_hub_model(m) for m in found]


def model_details(repo_id: str, *, api: Any = None) -> HubModel:
    """One model page with file sizes (network, no token for public repos, even gated ones)."""
    return to_hub_model(_api(api).model_info(repo_id, files_metadata=True))


def quant_files(model: HubModel, suffix: str = ".gguf") -> list[tuple[str, float | None]]:
    """``[(quant, GB), ...]`` for the GGUF files of a repo, smallest first (e.g. ``("Q4_K_M", 2.33)``)."""
    out = []
    for name, size in model.files:
        if name.lower().endswith(suffix):
            m = _QUANT.search(Path(name).name)
            out.append((m.group(1).upper() if m else Path(name).stem, round(size / GB, 2) if size else None))
    return sorted(out, key=lambda q: (q[1] is None, q[1] or 0))


def ollama_hf_tag(repo_id: str, quant: str | None = None) -> str:
    """The name Ollama pulls a Hub GGUF repo by: ``hf.co/<repo>:<quant>`` (``ollama pull hf.co/...``)."""
    return f"hf.co/{repo_id}" + (f":{quant}" if quant else "")


def save_snapshot(models: Iterable[HubModel], path: Path | str, **meta: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {**meta, "models": [{**asdict(m), "files": [list(f) for f in m.files]} for m in models]}
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_snapshot(path: Path | str) -> dict[str, HubModel]:
    """Recorded Hub answers, keyed by repo id (the offline twin of :func:`model_details`)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {m["id"]: to_hub_model(m) for m in data["models"]}
