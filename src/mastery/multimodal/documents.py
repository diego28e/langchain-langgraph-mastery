"""Document intake: text layer first, vision when there is none, scored against ground truth (13.01).

The rule the lesson teaches: a born-digital PDF already *contains* its text, so reading it with pypdf
is free, exact and instant. Only pages without a usable text layer (scans, photos) need a vision model.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = [
    "InvoiceFields",
    "LineItem",
    "PageRoute",
    "PageText",
    "ReceiptFields",
    "extract_text",
    "page_images",
    "parse_amount",
    "reconcile_receipt",
    "route_document",
    "score_fields",
]


class LineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float


class InvoiceFields(BaseModel):
    """What accounts payable needs from a vendor invoice."""

    vendor: str = Field(description="Company that issued the invoice")
    invoice_number: str = Field(description="Invoice number exactly as printed")
    date: str = Field(description="Issue date as YYYY-MM-DD")
    due_date: str | None = Field(default=None, description="Due date as YYYY-MM-DD, if printed")
    currency: str = Field(description="ISO 4217 code, e.g. USD or COP")
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: float | None = None
    tax: float | None = None
    total: float = Field(description="Grand total as a number, no thousands separators")


class ReceiptFields(BaseModel):
    """A shop receipt, to match against the expense ledger."""

    merchant: str
    date: str = Field(description="YYYY-MM-DD")
    currency: str = Field(description="ISO 4217 code; Colombian pesos are COP")
    total: float = Field(description="Total as a number. In COP '47.600' means 47600")
    payment_method: str | None = Field(default=None, description="cash, credit_card or debit_card")


@dataclass(frozen=True)
class PageText:
    page: int          # 1-based
    text: str
    chars: int
    images: int        # embedded raster images on the page


@dataclass(frozen=True)
class PageRoute:
    page: int
    method: Literal["text", "vision"]
    reason: str


def _reader(pdf: str | Path | bytes):
    from pypdf import PdfReader

    return PdfReader(io.BytesIO(pdf) if isinstance(pdf, bytes) else str(pdf))


def extract_text(pdf: str | Path | bytes) -> list[PageText]:
    """Text layer of every page (empty for scans). Uses pypdf, no model, no network."""
    pages = []
    for i, page in enumerate(_reader(pdf).pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append(PageText(page=i, text=text, chars=len(re.sub(r"\s", "", text)), images=len(page.images)))
    return pages


def page_images(pdf: str | Path | bytes, page: int = 1) -> list[tuple[bytes, str]]:
    """Embedded images of a page as ``(bytes, mime_type)``: for a scan, the scan itself."""
    out = []
    for img in _reader(pdf).pages[page - 1].images:
        suffix = Path(img.name).suffix.lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".jp2": "image/jp2"}.get(
            suffix, "image/png"
        )
        out.append((img.data, mime))
    return out


def route_document(pages: list[PageText], *, min_chars: int = 200) -> list[PageRoute]:
    """Decide per page: ``"text"`` (use the text layer) or ``"vision"`` (send the page as an image).

    A page goes to vision when its text layer has fewer than ``min_chars`` non-space characters
    (a scan, or a slide that is one big picture). Charts inside a text page are *also* flagged
    for vision when the page has embedded images, because the numbers live in the picture.
    """
    routes = []
    for p in pages:
        if p.chars < min_chars:
            why = "no text layer (scan)" if p.chars == 0 else f"only {p.chars} characters of text"
            routes.append(PageRoute(p.page, "vision", why))
        elif p.images:
            routes.append(PageRoute(p.page, "vision", f"text layer plus {p.images} embedded image(s)"))
        else:
            routes.append(PageRoute(p.page, "text", f"{p.chars} characters of text"))
    return routes


def parse_amount(value: Any, *, decimal: str = ".") -> float | None:
    """Turn ``"1,197.14"``, ``"$ 47.600"`` (``decimal=","``) or ``1197.14`` into a float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[^\d.,\-]", "", str(value))
    if not s:
        return None
    thousands = "," if decimal == "." else "."
    s = s.replace(thousands, "").replace(decimal, ".")
    try:
        return float(s)
    except ValueError:
        return None


def _norm(value: Any) -> str:
    return re.sub(r"[\s.,]+", " ", str(value)).strip().casefold()


def score_fields(
    predicted: BaseModel | dict[str, Any], truth: dict[str, Any], fields: list[str] | None = None,
    *, tolerance: float = 0.01,
) -> dict[str, Any]:
    """Field-level accuracy: numbers within ``tolerance``, text compared case/punctuation-insensitive.

    Returns ``{"fields": {name: bool}, "correct": n, "total": n, "accuracy": float, "wrong": [...]}``.
    ``line_items`` is scored as one field: same count and every amount matches.
    """
    pred = predicted.model_dump() if isinstance(predicted, BaseModel) else dict(predicted)
    names = fields or [k for k in truth if not k.startswith("_") and k != "items"]
    result: dict[str, bool] = {}
    wrong: list[str] = []
    for name in names:
        want, got = truth.get(name), pred.get(name)
        if name == "line_items":
            got = got or []
            ok = len(got) == len(want or []) and all(
                abs((parse_amount(g.get("amount")) or 0) - w["amount"]) <= tolerance for g, w in zip(got, want)
            )
        elif isinstance(want, (int, float)) and not isinstance(want, bool):
            g = parse_amount(got)
            ok = g is not None and abs(g - want) <= tolerance
        else:
            ok = _norm(got) == _norm(want)
        result[name] = ok
        if not ok and name == "line_items":
            wrong.append(f"line_items: expected {len(want or [])} items with matching amounts, got {len(got)}")
        elif not ok:
            wrong.append(f"{name}: expected {want!r}, got {got!r}")
    correct = sum(result.values())
    return {"fields": result, "correct": correct, "total": len(result),
            "accuracy": round(correct / len(result), 3) if result else 0.0, "wrong": wrong}


def reconcile_receipt(
    receipt: BaseModel | dict[str, Any], ledger: list[dict[str, Any]], *, tolerance: float = 0.5
) -> list[dict[str, Any]]:
    """Ledger rows (e.g. ``expenses-2026.csv``) with the receipt's date, currency and total.

    Merchant names differ between receipts and bank exports ("CARULLA EXPRESS" vs "Carulla Express"),
    so the merchant only has to share a word. Exactly one match means the receipt is accounted for;
    none means a missing expense; two or more means a possible duplicate charge.
    """
    r = receipt.model_dump() if isinstance(receipt, BaseModel) else dict(receipt)
    words = set(_norm(r.get("merchant", "")).split())
    total = parse_amount(r.get("total"))
    out = []
    for row in ledger:
        amount = parse_amount(row.get("amount"))
        if (
            str(row.get("date")) == str(r.get("date"))
            and str(row.get("currency", "")).upper() == str(r.get("currency", "")).upper()
            and amount is not None and total is not None and abs(amount - total) <= tolerance
            and words & set(_norm(row.get("merchant", "")).split())
        ):
            out.append(row)
    return out
