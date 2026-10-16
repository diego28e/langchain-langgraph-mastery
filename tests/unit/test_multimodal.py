"""Module 13.01 helpers: standard blocks, provider limits, PDF routing and field scoring (offline)."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from mastery.multimodal import (
    InvoiceFields,
    LimitError,
    audio_block,
    block_bytes,
    check_request,
    extract_text,
    file_block,
    image_block,
    limits_for,
    mime_of,
    page_images,
    parse_amount,
    route_document,
    score_fields,
    url_block,
)

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples" / "multimodal"
TRUTH = json.loads((SAMPLES / "ground-truth.json").read_text(encoding="utf-8"))


def test_image_block_has_standard_shape_and_size() -> None:
    block = image_block(SAMPLES / "receipt-photo.jpg")
    assert block["type"] == "image" and block["mime_type"] == "image/jpeg"
    assert block_bytes(block) == (SAMPLES / "receipt-photo.jpg").stat().st_size
    assert base64.b64decode(block["base64"])[:2] == b"\xff\xd8"


def test_blocks_reject_wrong_mime_and_bad_urls() -> None:
    with pytest.raises(ValueError):
        audio_block(SAMPLES / "receipt-photo.jpg")
    with pytest.raises(ValueError):
        image_block(b"raw")
    with pytest.raises(ValueError):
        url_block("image", "file:///etc/passwd")
    assert mime_of("call.FLAC") == "audio/flac" and mime_of("a.pdf") == "application/pdf"


def test_groq_rejects_pdfs_and_a_fourth_image() -> None:
    img = image_block(SAMPLES / "receipt-photo.jpg")
    assert check_request([img] * 3, "groq:qwen/qwen3.8-27b").media_tokens == 3 * 2048
    assert limits_for("qwen/qwen3.8-27b").provider == "groq"
    with pytest.raises(LimitError, match="at most 3"):
        check_request([img] * 4, "groq")
    with pytest.raises(LimitError, match="does not accept file"):
        check_request([file_block(SAMPLES / "invoice-digital.pdf")], "groq")


def test_gemini_pdf_and_audio_token_estimates() -> None:
    est = check_request(
        [{"role": "user", "content": [file_block(SAMPLES / "invoice-digital.pdf")]}], "google_genai:gemini-3.6-flash"
    )
    assert est.pdf_pages == 1 and est.media_tokens == 258
    fake_audio = audio_block(b"\x00" * 10, mime_type="audio/wav")
    assert check_request([fake_audio], "google_genai", audio_seconds=60).media_tokens == 60 * 32
    with pytest.raises(KeyError):
        limits_for("openai:gpt-x")


def test_inline_size_limit() -> None:
    big = {"type": "image", "base64": "A" * (28 * 1024 * 1024), "mime_type": "image/png"}
    with pytest.raises(LimitError, match="MB inline"):
        check_request([big], "groq")
    est = check_request([big], "groq", raise_on_error=False)
    assert any("MB inline" in n for n in est.notes)


def test_digital_pdf_goes_to_text_scan_goes_to_vision() -> None:
    digital = extract_text(SAMPLES / "invoice-digital.pdf")
    scanned = extract_text(SAMPLES / "invoice-scanned.pdf")
    assert "INV-2026-0412" in digital[0].text and scanned[0].chars == 0
    assert route_document(digital)[0].method == "text"
    route = route_document(scanned)[0]
    assert route.method == "vision" and "scan" in route.reason
    (data, mime), = page_images(SAMPLES / "invoice-scanned.pdf")
    assert mime == "image/jpeg" and len(data) > 10_000


def test_parse_amount_handles_both_conventions() -> None:
    assert parse_amount("1,197.14") == 1197.14
    assert parse_amount("$ 47.600", decimal=",") == 47600
    assert parse_amount("n/a") is None and parse_amount(None) is None


def test_score_fields_counts_ocr_slips() -> None:
    truth = TRUTH["invoice-scanned.pdf"]
    perfect = InvoiceFields.model_validate(truth)
    assert score_fields(perfect, truth)["accuracy"] == 1.0
    slipped = perfect.model_dump() | {"invoice_number": "INV-2O26-0412", "total": 1197.41}
    scored = score_fields(slipped, truth)
    assert scored["correct"] == scored["total"] - 2
    assert any("total" in w for w in scored["wrong"])


def test_samples_are_small_and_consistent() -> None:
    for path in SAMPLES.iterdir():
        assert path.stat().st_size < 1_000_000, path.name
    receipt = TRUTH["receipt-photo.jpg"]
    assert sum(i["amount"] for i in receipt["items"]) == receipt["total"]
    inv = TRUTH["invoice-digital.pdf"]
    assert round(sum(i["amount"] for i in inv["line_items"]), 2) == inv["subtotal"]
    assert round(inv["subtotal"] + inv["tax"], 2) == inv["total"]


def test_receipt_reconciles_with_exactly_one_ledger_row() -> None:
    import csv

    from mastery.multimodal import ReceiptFields, reconcile_receipt

    path = SAMPLES.parent / "expenses" / "expenses-2026.csv"
    with path.open(encoding="utf-8", newline="") as f:
        ledger = list(csv.DictReader(f))
    receipt = ReceiptFields.model_validate(TRUTH["receipt-photo.jpg"])
    (row,) = reconcile_receipt(receipt, ledger)
    assert row["merchant"] == "Carulla Express" and row["amount"] == "47600"
    misread = receipt.model_copy(update={"total": 4760.0})   # "47.600" read as 4,760
    assert reconcile_receipt(misread, ledger) == []
