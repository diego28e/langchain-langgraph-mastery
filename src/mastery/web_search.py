"""Web search for agents: Groq built-in browser search (default) or Tavily (Lesson 05.01).

The course default is Groq's server-side ``browser_search`` (decision D-003). LangChain's
``bind_tools`` can't convert it in ``langchain-groq`` 1.1.3, so it is attached with
``.bind(tools=[...])`` (decision D-006), and wrapped in a normal ``@tool`` when an agent needs
web search next to other tools. Tavily is the switchable alternative
(``MASTERY_WEB_SEARCH=tavily``, needs ``TAVILY_API_KEY``).

Both backends return the same thing to the agent: the findings **fenced as untrusted data**
(Lesson 04.05) plus a ``Sources:`` list, and the URLs again in the tool artifact, so an answer's
citations can be checked against what the tool really returned (:func:`mastery.mcp.check_sources`).
"""

from __future__ import annotations

import os
from typing import Any, Literal

from langchain_core.tools import BaseTool, tool

from mastery.mcp import extract_urls
from mastery.middleware import fence_untrusted

__all__ = ["BROWSER_SEARCH", "Backend", "browser_search_model", "groq_search_sources", "make_tavily",
           "make_web_search_tool", "tavily_sources", "web_search_backend"]

Backend = Literal["groq", "tavily"]
BROWSER_SEARCH: dict[str, str] = {"type": "browser_search"}
#: Groq models with built-in browser search (console.groq.com, verified 2026-10-12).
BROWSER_SEARCH_MODELS = ("openai/gpt-oss-20b", "openai/gpt-oss-120b", "openai/gpt-oss-safeguard-20b")


def web_search_backend(default: Backend = "groq") -> Backend:
    """The backend chosen by ``MASTERY_WEB_SEARCH`` (``groq`` or ``tavily``; default ``groq``)."""
    value = (os.environ.get("MASTERY_WEB_SEARCH") or default).strip().lower()
    if value not in ("groq", "tavily"):
        raise ValueError(f"MASTERY_WEB_SEARCH must be 'groq' or 'tavily', not {value!r}.")
    return value  # type: ignore[return-value]


def browser_search_model(model: Any, *, required: bool = True) -> Any:
    """Attach Groq's built-in browser search with ``.bind`` (``bind_tools`` rejects it, D-006).

    Create the model with ``reasoning_effort="low"`` to keep browsing (and tokens) short.
    """
    kwargs: dict[str, Any] = {"tools": [BROWSER_SEARCH]}
    if required:
        kwargs["tool_choice"] = "required"
    return model.bind(**kwargs)


def groq_search_sources(message: Any) -> list[dict[str, str]]:
    """``[{"title", "url"}]`` from a Groq reply's ``additional_kwargs["executed_tools"]``.

    Reads ``search_results.results`` and ``browser_results`` (fields of the Groq API's
    executed-tool object), then any URL in ``output``. Unique by URL, in order.
    Pass the final (non-streamed) message: streamed chunks may not carry ``executed_tools``.
    """
    found: dict[str, str] = {}
    for executed in (getattr(message, "additional_kwargs", None) or {}).get("executed_tools") or []:
        results = ((executed.get("search_results") or {}).get("results") or []) + (executed.get("browser_results") or [])
        for result in results:
            if result.get("url"):
                found.setdefault(result["url"], result.get("title") or "")
        for url in extract_urls(executed.get("output") or ""):
            found.setdefault(url, "")
    return [{"title": title, "url": url} for url, title in found.items()]


def make_tavily(max_results: int = 5, **kwargs: Any) -> Any:
    """``TavilySearch`` with the course defaults. Honors ``TAVILY_BASE_URL`` (e.g. a local test server)."""
    from langchain_tavily import TavilySearch

    if os.environ.get("TAVILY_BASE_URL"):
        kwargs.setdefault("api_base_url", os.environ["TAVILY_BASE_URL"].rstrip("/"))
    return TavilySearch(max_results=max_results, **kwargs)


def tavily_sources(raw: dict[str, Any]) -> list[dict[str, str]]:
    """``[{"title", "url"}]`` from a Tavily search response."""
    return [{"title": r.get("title") or "", "url": r["url"]} for r in raw.get("results") or [] if r.get("url")]


def _format(findings: str, sources: list[dict[str, str]], label: str) -> str:
    listing = "\n".join(f"- {s['url']}" + (f" ({s['title']})" if s["title"] else "") for s in sources) or "- (none)"
    return f"{fence_untrusted(findings, label)}\n\nSources:\n{listing}"


def make_web_search_tool(backend: Backend | None = None, *, model: Any = None, tavily: Any = None,
                         max_results: int = 5) -> BaseTool:
    """A ``web_search(query)`` tool for agents.

    Args:
        backend: ``"groq"`` or ``"tavily"``. Default: :func:`web_search_backend`.
        model: Groq backend: a GPT-OSS chat model (``reasoning_effort="low"`` recommended).
            Default: ``get_model("fast", reasoning_effort="low")``.
        tavily: Tavily backend: a ``TavilySearch`` instance. Default: :func:`make_tavily`.
        max_results: Tavily backend: results per search.

    Returns:
        A tool whose content is fenced findings plus ``Sources:``; the artifact is
        ``{"backend": ..., "sources": [{"title", "url"}]}``.
    """
    backend = backend or web_search_backend()
    if backend == "groq":
        if model is None:
            from mastery.models import get_model

            model = get_model("fast", reasoning_effort="low")
        searcher = browser_search_model(model)

        @tool(response_format="content_and_artifact")
        def web_search(query: str) -> tuple[str, dict[str, Any]]:
            """Search the web for current information that is not in the documentation tools. One focused query."""
            reply = searcher.invoke(query)
            sources = groq_search_sources(reply)
            return _format(str(reply.text), sources, "web search (Groq)"), {"backend": "groq", "sources": sources}

        return web_search

    if backend == "tavily":
        engine = tavily or make_tavily(max_results=max_results)

        @tool(response_format="content_and_artifact")
        def web_search(query: str) -> tuple[str, dict[str, Any]]:
            """Search the web for current information that is not in the documentation tools. One focused query."""
            raw = engine.invoke({"query": query})
            raw = raw if isinstance(raw, dict) else {"results": []}
            sources = tavily_sources(raw)
            text = "\n\n".join(f"{r.get('title', '')}\n{r.get('url', '')}\n{r.get('content', '')}"
                               for r in raw.get("results") or [])
            return _format(text or "(no results)", sources, "web search (Tavily)"), {"backend": "tavily", "sources": sources}

        return web_search

    raise ValueError(f"Unknown web search backend {backend!r}.")
