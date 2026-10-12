"""Node utilities for LangGraph graphs (Module 07): timing, loop guards, streaming, drawing."""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable, Iterable
from typing import Any

__all__ = ["loop_router", "mermaid_markdown", "run_summary", "show_graph", "stream_updates", "timed"]


def timed(name: str | None = None) -> Callable:
    """Decorator for a node: adds ``{"node", "seconds"}`` to the update's ``run_log`` list.

    The state must declare ``run_log: Annotated[list[dict], operator.add]``. Works with nodes that
    return a dict (or ``None``). Parallel ``Send`` workers each add their own row.
    """
    def wrap(fn: Callable) -> Callable:
        label = name or fn.__name__

        def finish(update: Any, start: float) -> dict:
            update = update or {}
            if not isinstance(update, dict):
                raise TypeError(f"@timed node {label!r} must return a dict, got {type(update).__name__}")
            row = {"node": label, "seconds": round(time.perf_counter() - start, 4)}
            return {**update, "run_log": list(update.get("run_log", [])) + [row]}

        if inspect.iscoroutinefunction(fn):      # async nodes stay async (node timeouts need that, Module 08)
            @functools.wraps(fn)
            async def anode(*args: Any, **kwargs: Any) -> dict:
                start = time.perf_counter()
                return finish(await fn(*args, **kwargs), start)

            return anode

        @functools.wraps(fn)
        def node(*args: Any, **kwargs: Any) -> dict:
            start = time.perf_counter()
            return finish(fn(*args, **kwargs), start)

        return node

    return wrap


def loop_router(*, score_key: str, threshold: int, max_iterations: int, again: str, done: str,
                iteration_key: str = "iteration") -> Callable[[dict], str]:
    """Conditional-edge function for an evaluator-optimizer loop with a hard stop.

    Returns ``done`` when ``state[score_key].score >= threshold`` (or a plain int score) or when
    ``state[iteration_key] >= max_iterations``; otherwise ``again``. Deterministic termination does
    not depend on the model: the counter alone ends the loop.
    """
    if max_iterations < 0:
        raise ValueError("max_iterations must be >= 0")

    def route(state: dict) -> str:
        value = state.get(score_key)
        score = getattr(value, "score", value)
        if score is not None and score >= threshold:
            return done
        if state.get(iteration_key, 0) >= max_iterations:
            return done
        return again

    route.__name__ = f"route_{score_key}"
    return route


def stream_updates(graph: Any, inputs: dict, config: dict | None = None, *, printer: Callable = print,
                   width: int = 90) -> dict:
    """Run ``graph``, print one line per node update, and return the final state.

    Uses ``stream_mode=["updates", "values"]``: ``updates`` says which node changed which keys,
    ``values`` carries the full state after each step (the last one is the result).
    """
    final: dict = {}
    for mode, chunk in graph.stream(inputs, config or {}, stream_mode=["updates", "values"]):
        if mode == "values":
            final = chunk
            continue
        for node, update in (chunk or {}).items():
            keys = ", ".join(k for k in (update or {}) if k != "run_log") or "-"
            printer(f"  ▸ {node:<18} updated: {keys}"[:width])
    return final


def run_summary(run_log: Iterable[dict]) -> dict[str, dict[str, float]]:
    """Aggregate ``run_log`` rows into ``{node: {"calls": n, "seconds": total}}`` (in first-seen order)."""
    out: dict[str, dict[str, float]] = {}
    for row in run_log:
        item = out.setdefault(row["node"], {"calls": 0, "seconds": 0.0})
        item["calls"] += 1
        item["seconds"] = round(item["seconds"] + row["seconds"], 4)
    return out


def mermaid_markdown(graph: Any, *, xray: bool = False) -> str:
    """The graph as a fenced Mermaid block (JupyterLab 4.1+ and GitHub render it; no network)."""
    return "```mermaid\n" + graph.get_graph(xray=xray).draw_mermaid() + "\n```"


def show_graph(graph: Any, *, png: bool = True, xray: bool = False) -> str:
    """Display a compiled graph in Jupyter. Tries a PNG (🌐 mermaid.ink), falls back to Mermaid Markdown.

    Returns ``"png"`` or ``"mermaid"`` so notebooks can say which one you see.
    """
    from IPython.display import Image, Markdown, display

    if png:
        try:
            data = graph.get_graph(xray=xray).draw_mermaid_png(max_retries=1, retry_delay=0.5)
            display(Image(data))
            return "png"
        except Exception as exc:  # noqa: BLE001 - offline, proxy, or mermaid.ink down: fall back
            print(f"⚠️ PNG unavailable ({type(exc).__name__}); showing Mermaid text instead.")
    display(Markdown(mermaid_markdown(graph, xray=xray)))
    return "mermaid"
