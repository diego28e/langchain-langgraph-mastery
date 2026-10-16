"""Prompt versions as data (Lesson 10.07): commits by content hash, movable tags, gated promotion.

An offline twin of the LangSmith Prompt Hub: ``push`` returns a commit id (a content hash,
so pushing the same text twice is the same commit), ``tag`` points a name like ``"prod"`` at a
commit, ``pull`` resolves ``"latest"``, a tag or a commit. :meth:`PromptRegistry.promote`
moves a tag only when an eval gate passed: the release rule of Lesson 10.08, applied to prompts.

Example:
    >>> reg = PromptRegistry()
    >>> c1 = reg.push("triage", "Route the request.")
    >>> reg.pull("triage") == "Route the request."
    True
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mastery.evals.meta import content_hash

__all__ = ["PromotionBlocked", "PromptRegistry"]


class PromotionBlocked(RuntimeError):
    """Raised when a tag would move to a commit whose gate did not pass."""


@dataclass
class PromptRegistry:
    commits: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    tags: dict[str, dict[str, str]] = field(default_factory=dict)

    def push(self, name: str, template: str, *, description: str = "") -> str:
        commit = content_hash(template)[:8]
        history = self.commits.setdefault(name, [])
        if not any(c["commit"] == commit for c in history):
            history.append({"commit": commit, "template": template, "description": description})
        return commit

    def history(self, name: str) -> list[dict[str, Any]]:
        return list(self.commits.get(name, []))

    def tag(self, name: str, commit: str, tag: str) -> None:
        if not any(c["commit"] == commit for c in self.commits.get(name, [])):
            raise KeyError(f"{name}: no commit {commit}")
        self.tags.setdefault(name, {})[tag] = commit

    def resolve(self, name: str, ref: str = "latest") -> str:
        history = self.commits.get(name)
        if not history:
            raise KeyError(f"no prompt {name!r}")
        if ref == "latest":
            return history[-1]["commit"]
        if ref in self.tags.get(name, {}):
            return self.tags[name][ref]
        if any(c["commit"] == ref for c in history):
            return ref
        raise KeyError(f"{name}: unknown ref {ref!r}")

    def pull(self, name: str, ref: str = "latest") -> str:
        commit = self.resolve(name, ref)
        return next(c["template"] for c in self.commits[name] if c["commit"] == commit)

    def promote(self, name: str, commit: str, tag: str, gate: Any) -> None:
        """Move ``tag`` to ``commit`` only if ``gate`` (a GateReport or bool) passed."""
        passed = gate if isinstance(gate, bool) else getattr(gate, "passed", False)
        if not passed:
            raise PromotionBlocked(f"{name}@{commit} not promoted to {tag!r}: the eval gate did not pass")
        self.tag(name, commit, tag)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_text(json.dumps({"commits": self.commits, "tags": self.tags}, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> PromptRegistry:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data["commits"], data["tags"])
