"""Splitter presets that keep citation metadata and give every chunk a stable ``chunk_id``."""
from __future__ import annotations

from collections import Counter
from typing import Literal

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

Preset = Literal["recursive", "markdown", "tokens"]
_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def _token_length():
    """tiktoken's cl100k encoder if installed, else ~4 characters per token. Returns (fn, name)."""
    try:
        import tiktoken

        encoder = tiktoken.get_encoding("cl100k_base")
        return (lambda text: len(encoder.encode(text))), "tiktoken cl100k_base"
    except Exception:  # noqa: BLE001 - not installed, or the encoding file can't be downloaded (offline)
        return (lambda text: max(1, len(text) // 4)), "approx (4 chars/token)"


def split_documents(docs: list[Document], preset: Preset = "recursive", chunk_size: int = 800,
                    chunk_overlap: int = 100) -> list[Document]:
    """Split ``docs`` and return chunks with ``chunk_id``, ``chunk`` (index within its page/file), ``start_index``.

    - ``recursive``: :class:`RecursiveCharacterTextSplitter` (characters), the generic default.
    - ``markdown``: split Markdown on headings first (adds ``section``), then recursively; other types → recursive.
    - ``tokens``: recursive, but ``chunk_size`` / ``chunk_overlap`` are counted in tokens.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    length, _ = _token_length() if preset == "tokens" else (len, "chars")
    recursive = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                                               length_function=length, add_start_index=True)
    headers = MarkdownHeaderTextSplitter(_HEADERS, strip_headers=False)
    chunks: list[Document] = []
    for doc in docs:
        if preset == "markdown" and doc.metadata.get("type") == "markdown":
            pieces = []
            for section in headers.split_text(doc.page_content):
                names = [section.metadata[h] for _, h in _HEADERS if h in section.metadata]
                meta = {**doc.metadata, "section": " > ".join(names)}
                pieces.extend(recursive.split_documents([Document(section.page_content, metadata=meta)]))
        else:
            pieces = recursive.split_documents([doc])
        page = doc.metadata.get("page")
        for n, piece in enumerate(pieces):
            piece.metadata["chunk"] = n
            piece.metadata["chunk_id"] = f"{doc.metadata.get('source', '?')}#p{page or 0}-c{n}"
            chunks.append(piece)
    return chunks


def chunk_stats(chunks: list[Document]) -> dict:
    """Count, average/min/max length in characters, and chunks per type: quick sanity numbers."""
    sizes = [len(c.page_content) for c in chunks] or [0]
    return {"chunks": len(chunks), "avg_chars": round(sum(sizes) / len(sizes)), "min_chars": min(sizes),
            "max_chars": max(sizes), "by_type": dict(Counter(c.metadata.get("type", "?") for c in chunks))}
