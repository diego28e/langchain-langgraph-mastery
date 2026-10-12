"""Document loaders that keep the metadata citations need: ``source``, ``page``, ``title``, ``type``.

PDFs are read with ``pypdf`` directly (as the LangChain knowledge-base tutorial does), HTML with
BeautifulSoup, Markdown as UTF-8 text. ``source`` is a repo-relative POSIX path, so citations look
the same on Windows and Linux.
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path

from langchain_core.documents import Document

from mastery.config import find_repo_root

_DROP_TAGS = ("script", "style", "nav", "footer", "header", "noscript", "form")


def _source(path: Path, root: Path | None) -> str:
    path = Path(path).resolve()
    base = Path(root).resolve() if root else Path(find_repo_root()).resolve()
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def load_markdown(path: str | Path, root: str | Path | None = None) -> list[Document]:
    """One Document per Markdown file. ``title`` = the first ``# `` heading."""
    path = Path(path)
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")   # Windows checkouts may use CRLF
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    meta = {"source": _source(path, root), "type": "markdown", "title": match.group(1).strip() if match else path.stem}
    return [Document(page_content=text, metadata=meta)]


def load_pdf(path: str | Path, root: str | Path | None = None) -> list[Document]:
    """One Document per PDF page; ``page`` is 1-based (what people see), ``pages`` the total."""
    from pypdf import PdfReader

    path = Path(path)
    reader = PdfReader(path)
    title = (reader.metadata.title if reader.metadata and reader.metadata.title else None) or path.stem
    docs = []
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            warnings.warn(f"{path.name} page {number} has no text layer (scanned?). Use OCR or a layout parser.",
                          stacklevel=2)
            continue
        docs.append(Document(page_content=text, metadata={"source": _source(path, root), "type": "pdf", "page": number,
                                                          "pages": len(reader.pages), "title": title}))
    return docs


def load_html(path: str | Path, root: str | Path | None = None) -> list[Document]:
    """Visible main text of an HTML file (scripts, styles, navigation and footers removed)."""
    from bs4 import BeautifulSoup

    path = Path(path)
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    for tag in soup(_DROP_TAGS):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else path.stem
    body = soup.find("main") or soup.body or soup
    lines = []
    for el in body.find_all(["h1", "h2", "h3", "p", "li", "td"]):
        text = el.get_text(" ", strip=True)
        if text:
            lines.append(("#" * int(el.name[1]) + " " + text) if el.name.startswith("h") else text)
    return [Document(page_content="\n\n".join(lines), metadata={"source": _source(path, root), "type": "html",
                                                                 "title": title})]


def load_corpus(directory: str | Path, root: str | Path | None = None) -> list[Document]:
    """Load every ``.md``, ``.pdf`` and ``.html`` file under ``directory`` (sorted, so runs are repeatable).

    ``source`` is relative to ``root`` (default: ``directory`` itself, e.g. ``products/nimbus-pro.md``).
    """
    root = root or directory
    loaders = {".md": load_markdown, ".pdf": load_pdf, ".html": load_html, ".htm": load_html}
    docs: list[Document] = []
    for path in sorted(Path(directory).rglob("*")):
        loader = loaders.get(path.suffix.lower())
        if loader and path.is_file():
            docs.extend(loader(path, root))
    return docs
