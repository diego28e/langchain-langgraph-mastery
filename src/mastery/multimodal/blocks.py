"""LangChain standard multimodal content blocks (Lesson 13.01).

One shape for every provider: ``{"type": "image" | "file" | "audio" | "video", "base64": ...,
"mime_type": ...}`` (or ``"url"`` / ``"file_id"`` instead of ``"base64"``). The chat-model integration
converts it to the provider's wire format. VERIFIED 2026-10-16:
https://docs.langchain.com/oss/python/langchain/messages#multimodal
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

__all__ = [
    "BLOCK_TYPES",
    "audio_block",
    "block_bytes",
    "content_block",
    "file_block",
    "image_block",
    "mime_of",
    "text_block",
    "url_block",
    "video_block",
]

BLOCK_TYPES = ("image", "file", "audio", "video")
_EXTRA_MIME = {
    ".flac": "audio/flac", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".opus": "audio/ogg",
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".webm": "video/webm", ".webp": "image/webp",
    ".md": "text/markdown", ".pdf": "application/pdf",
}


def mime_of(path: str | Path) -> str:
    """Return the MIME type for ``path`` from its extension (stable across operating systems)."""
    suffix = Path(path).suffix.lower()
    if suffix in _EXTRA_MIME:
        return _EXTRA_MIME[suffix]
    guess, _ = mimetypes.guess_type(str(path))
    if guess is None:
        raise ValueError(f"Unknown file type for {Path(path).name!r}; pass mime_type explicitly.")
    return guess


def text_block(text: str) -> dict[str, Any]:
    """A plain text block, to put next to media in one message."""
    return {"type": "text", "text": text}


def content_block(kind: str, data: str | Path | bytes, mime_type: str | None = None) -> dict[str, Any]:
    """Build a base64 standard block of ``kind`` from a path or raw bytes."""
    if kind not in BLOCK_TYPES:
        raise ValueError(f"kind must be one of {BLOCK_TYPES}, got {kind!r}")
    if isinstance(data, bytes):
        if mime_type is None:
            raise ValueError("mime_type is required when passing raw bytes")
        raw = data
    else:
        path = Path(data)
        raw = path.read_bytes()
        mime_type = mime_type or mime_of(path)
    major = mime_type.split("/")[0]
    if kind in ("image", "audio", "video") and major != kind:
        raise ValueError(f"{kind} block needs a {kind}/* MIME type, got {mime_type!r}")
    return {"type": kind, "base64": base64.b64encode(raw).decode("ascii"), "mime_type": mime_type}


def image_block(data: str | Path | bytes, mime_type: str | None = None) -> dict[str, Any]:
    """Image block (PNG, JPEG, WEBP, GIF)."""
    return content_block("image", data, mime_type)


def file_block(data: str | Path | bytes, mime_type: str | None = None) -> dict[str, Any]:
    """File block, typically a PDF (``application/pdf``)."""
    return content_block("file", data, mime_type)


def audio_block(data: str | Path | bytes, mime_type: str | None = None) -> dict[str, Any]:
    """Audio block (WAV, FLAC, MP3, OGG ...)."""
    return content_block("audio", data, mime_type)


def video_block(data: str | Path | bytes, mime_type: str | None = None) -> dict[str, Any]:
    """Video block (MP4, WEBM ...). Large videos belong in the Files API or a URL, not base64."""
    return content_block("video", data, mime_type)


def url_block(kind: str, url: str, mime_type: str | None = None) -> dict[str, Any]:
    """Block that points at a public URL instead of carrying the bytes."""
    if kind not in BLOCK_TYPES:
        raise ValueError(f"kind must be one of {BLOCK_TYPES}, got {kind!r}")
    if not url.startswith(("https://", "http://")):
        raise ValueError("url must start with http:// or https://")
    block: dict[str, Any] = {"type": kind, "url": url}
    if mime_type:
        block["mime_type"] = mime_type
    return block


def block_bytes(block: dict[str, Any]) -> int:
    """Decoded size of a base64 block in bytes (0 for URL / file_id / text blocks)."""
    data = block.get("base64")
    if not data:
        return 0
    padding = data.count("=", -2)
    return len(data) * 3 // 4 - padding
