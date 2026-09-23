"""Native-vs-OCR routing decision for a page."""

from __future__ import annotations

from typing import Any

from .native import NativeAdapter
from .ocr import OcrAdapter
from .protocols import WordSource
from .text_quality import garbage_char_ratio

MIN_NATIVE_TEXT_LENGTH = 200
MAX_NATIVE_GARBAGE_RATIO = 0.15


def choose_adapter(page: Any) -> WordSource:
    """A digital PDF page with plenty of clean native text goes straight to
    `NativeAdapter` — fast, and its bboxes are exact. Anything else (a
    scan, an image-only page, or a native text layer that's too short or
    too garbled — scan-with-garbage-text-layer, legacy TCVN3/VNI fonts)
    goes to `OcrAdapter` instead.

    `VisionAdapter` is never returned here: it is only ever reached by
    escalating specific cells/regions of `OcrAdapter`'s own output (see
    `escalation.EscalationController`), never chosen for a whole page.
    """
    text = page.get_text().strip()
    if len(text) > MIN_NATIVE_TEXT_LENGTH and garbage_char_ratio(text) < MAX_NATIVE_GARBAGE_RATIO:
        return NativeAdapter()
    return OcrAdapter()
