"""Multimodal input helpers for Module 13 (documents, images, audio and video blocks).

Introduced in Lesson 13.01. Everything here is offline: building blocks, checking provider limits and
reading PDFs never calls a model.
"""
from mastery.multimodal.blocks import (
    BLOCK_TYPES,
    audio_block,
    block_bytes,
    content_block,
    file_block,
    image_block,
    mime_of,
    text_block,
    url_block,
    video_block,
)
from mastery.multimodal.documents import (
    InvoiceFields,
    LineItem,
    PageRoute,
    PageText,
    ReceiptFields,
    extract_text,
    page_images,
    parse_amount,
    reconcile_receipt,
    route_document,
    score_fields,
)
from mastery.multimodal.limits import LIMITS, LimitError, ProviderLimits, RequestEstimate, check_request, limits_for, pdf_pages

__all__ = [
    "BLOCK_TYPES", "LIMITS", "InvoiceFields", "LimitError", "LineItem", "PageRoute", "PageText",
    "ProviderLimits", "ReceiptFields", "RequestEstimate", "audio_block", "block_bytes", "check_request",
    "content_block", "extract_text", "file_block", "image_block", "limits_for", "mime_of", "page_images",
    "parse_amount", "pdf_pages", "reconcile_receipt", "route_document", "score_fields", "text_block", "url_block", "video_block",
]
