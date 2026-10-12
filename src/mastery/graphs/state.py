"""Reusable state pieces for LangGraph graphs (Module 07).

Reducers decide how a node's partial update is merged into a state key:
no reducer = overwrite; ``operator.add`` = concatenate lists; the helpers here
cover the other cases the course needs. See Lesson 07.02.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field

__all__ = [
    "CHECKPOINT_TYPES",
    "ContentState",
    "Critique",
    "Outline",
    "SectionNote",
    "SectionPlan",
    "append_unique",
    "keep_last",
    "memory_checkpointer",
    "merge_dicts",
]


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    """Reducer: shallow-merge dicts; keys in ``right`` win. ``None`` counts as empty."""
    return {**(left or {}), **(right or {})}


def append_unique(left: list | None, right: list | Any | None) -> list:
    """Reducer: append items not already present, keeping the first-seen order. Accepts one item or a list."""
    out = list(left or [])
    items = right if isinstance(right, list) else ([] if right is None else [right])
    for item in items:
        if item not in out:
            out.append(item)
    return out


def keep_last(n: int) -> Callable[[list | None, list | None], list]:
    """Reducer factory: concatenate, then keep only the newest ``n`` items (a bounded log)."""
    if n < 1:
        raise ValueError("n must be >= 1")

    def reducer(left: list | None, right: list | None) -> list:
        return (list(left or []) + list(right or []))[-n:]

    reducer.__name__ = f"keep_last_{n}"
    return reducer


# --- Project 07 (content pipeline) schemas: structured outputs + state -------------------------------

class SectionPlan(BaseModel):
    """One section of the outline: a heading and the question its research must answer."""
    title: str = Field(description="Section heading, 2-8 words")
    question: str = Field(description="The question this section answers, used to search the sources")


class Outline(BaseModel):
    """The plan for a blog post."""
    title: str = Field(description="Blog post title")
    sections: list[SectionPlan] = Field(description="3 to 5 sections, in reading order", min_length=1, max_length=6)


class Critique(BaseModel):
    """An editor's review of a draft."""
    score: int = Field(description="Overall quality from 1 (poor) to 10 (publishable)", ge=1, le=10)
    issues: list[str] = Field(default_factory=list, description="Concrete problems to fix, most important first")


class SectionNote(TypedDict):
    """Research collected for one section (written by a parallel ``research_section`` worker)."""
    title: str
    notes: str
    sources: list[str]


class ContentState(TypedDict, total=False):
    """State of the Project 07 content pipeline."""
    topic: str
    outline: Outline
    sections: Annotated[list[SectionNote], operator.add]   # parallel workers append; order = completion order
    draft: str
    critique: Critique
    iteration: int                                           # number of revisions done so far
    scores: Annotated[list[int], operator.add]               # critique score history
    final: str
    run_log: Annotated[list[dict], operator.add]             # per-node timings (mastery.graphs.timed)


#: Pydantic models above that may sit in checkpointed state (LangGraph 1.2 warns on unregistered types).
CHECKPOINT_TYPES = [("mastery.graphs.state", "SectionPlan"), ("mastery.graphs.state", "Outline"),
                    ("mastery.graphs.state", "Critique"), ("mastery.graphs.research", "Plan"),
                    ("mastery.graphs.research", "Clarity")]


def memory_checkpointer():
    """An ``InMemorySaver`` that allows this module's Pydantic models when reading checkpoints back."""
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    return InMemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES))
