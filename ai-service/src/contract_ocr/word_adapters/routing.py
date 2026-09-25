"""Native-vs-OCR routing decision for a page."""

from __future__ import annotations

from typing import Any

from .native import NativeAdapter
from .ocr import OcrAdapter
from .protocols import WordSource
from .text_quality import garbage_char_ratio, has_missing_diacritics_signature

MIN_NATIVE_TEXT_LENGTH = 200
MAX_NATIVE_GARBAGE_RATIO = 0.15


def choose_adapter(page: Any) -> WordSource:
    """A digital PDF page with plenty of clean native text goes straight to
    `NativeAdapter` — fast, and its bboxes are exact. Anything else (a
    scan, an image-only page, or a native text layer that's too short or
    too garbled — scan-with-garbage-text-layer, legacy TCVN3/VNI fonts)
    goes to `OcrAdapter` instead. A native text layer whose diacritics were
    silently dropped (also a legacy TCVN3/VNI symptom) reads as clean under
    `garbage_char_ratio` — its letters are still plain ASCII Vietnamese
    letters — so it's checked separately via `has_missing_diacritics_signature`.

    `VisionAdapter` is never returned here: it is only ever reached by
    escalating specific cells/regions of `OcrAdapter`'s own output (see
    `escalation.EscalationController`), never chosen for a whole page.
    """
    text = page.get_text().strip()
    if (
        len(text) > MIN_NATIVE_TEXT_LENGTH
        and garbage_char_ratio(text) < MAX_NATIVE_GARBAGE_RATIO
        and not has_missing_diacritics_signature(text)
    ):
        return NativeAdapter()
    return OcrAdapter()
