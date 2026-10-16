"""Offline stand-in for the public LangChain docs MCP server (``https://docs.langchain.com/mcp``).

It exposes **one** tool with the same name and result format as the real server's search tool,
``search_docs_by_lang_chain(query)``, but answers from the small snapshot committed in
``data/samples/mcp/docs-snapshot.json``. Use it when you are offline, in tests, and in
Project 05's OFFLINE mode. Its pages are real docs URLs, so citations stay checkable.

The real server is better (the whole, current docs); the stand-in is predictable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

__all__ = ["SNAPSHOT", "build_server", "load_snapshot", "search_snapshot"]

from mastery.config import package_repo_root

SNAPSHOT = package_repo_root() / "data" / "samples" / "mcp" / "docs-snapshot.json"
_WORD = re.compile(r"[a-z0-9_]+")
_STOP = {"a", "an", "and", "the", "to", "of", "in", "how", "do", "i", "is", "with", "for", "my", "can", "what",
         "which", "that", "from", "on", "it", "an", "be", "python", "langchain"}


def load_snapshot(path: str | Path | None = None) -> list[dict[str, Any]]:
    """The snapshot's pages: ``[{"title", "url", "page", "content"}, ...]``."""
    return json.loads(Path(path or SNAPSHOT).read_text(encoding="utf-8"))["pages"]


def _terms(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1}


def search_snapshot(query: str, pages: list[dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    """Rank pages by query-term overlap (title and page path count double)."""
    wanted = _terms(query)
    scored = []
    for page in pages:
        head = _terms(page["title"] + " " + page["page"].replace("/", " ").replace("-", " "))
        body = _terms(page["content"])
        score = 2 * len(wanted & head) + len(wanted & body)
        if score:
            scored.append((score, page))
    scored.sort(key=lambda item: (-item[0], item[1]["url"]))
    return [page for _, page in scored[:limit]]


def build_server(snapshot: str | Path | None = None) -> FastMCP:
    """A FastMCP server with ``search_docs_by_lang_chain`` over the snapshot."""
    pages = load_snapshot(snapshot)
    server = FastMCP("Docs by LangChain (offline stand-in)",
                     instructions="Offline snapshot of LangChain docs search results. Answers may be out of date.")

    @server.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
                              "openWorldHint": False})
    def search_docs_by_lang_chain(query: str) -> str:
        """Search docs for relevant guides, how-tos, and examples. (Offline snapshot.)"""
        hits = search_snapshot(query, pages)
        if not hits:
            return "No results in the offline snapshot. Try other words."
        return "\n\n".join(f"Title: {p['title']}\nLink: {p['url']}\nPage: {p['page']}\nContent: {p['content']}"
                           for p in hits)

    return server
