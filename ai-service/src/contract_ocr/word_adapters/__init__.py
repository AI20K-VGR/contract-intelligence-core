"""Converts every OCR/vision source into the same `list[Word]` shape that
`contract_ocr.table_reconstruct` consumes.

Three interchangeable `WordSource` adapters:
    - `NativeAdapter`  — PyMuPDF native text (`source="native"`)
    - `OcrAdapter`     — PaddleOCR detection + VietOCR recognition (`source="ocr"`)
    - `VisionAdapter`  — a vision LLM, last resort (`source="vision"`)

`choose_adapter` routes a page to Native or OCR. `EscalationController`
decides, per cell/region and capped per page, when OCR output is
untrustworthy enough to re-read with `VisionAdapter`.
"""

from __future__ import annotations

from .escalation import EscalationController, EscalationResult
from .native import NativeAdapter
from .ocr import OcrAdapter
from .protocols import LineDetector, TextRecognizer, VisionClient, WordSource
from .routing import choose_adapter
from .text_quality import garbage_char_ratio, has_missing_diacritics_signature, valid_word_ratio
from .types import Region
from .vision import VisionAdapter

__all__ = [
    "EscalationController",
    "EscalationResult",
    "LineDetector",
    "NativeAdapter",
    "OcrAdapter",
    "Region",
    "TextRecognizer",
    "VisionAdapter",
    "VisionClient",
    "WordSource",
    "choose_adapter",
    "garbage_char_ratio",
    "has_missing_diacritics_signature",
    "valid_word_ratio",
]
