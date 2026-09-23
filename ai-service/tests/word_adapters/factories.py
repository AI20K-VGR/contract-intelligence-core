"""Fakes and small builders for testing word_adapters without any real
PaddleOCR/VietOCR/OpenAI dependency, and without a real PDF file."""

from __future__ import annotations

from typing import Any

import numpy as np
import pymupdf

from contract_ocr.table_reconstruct.types import Bbox
from contract_ocr.word_adapters.protocols import LineDetector, TextRecognizer


def pdf_page(
    lines: list[tuple[str, float, float]], *, width: float = 400.0, height: float = 300.0
) -> pymupdf.Page:
    """A real (in-memory) PyMuPDF page with `lines` inserted as
    (text, x, y) — genuine `page.get_text("words")` output, no mocking of
    PyMuPDF's own geometry/rotation handling."""
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    for text, x, y in lines:
        page.insert_text((x, y), text, fontsize=12)
    return page


def blank_image(width: int = 400, height: int = 300) -> np.ndarray:
    return np.zeros((height, width, 3), dtype=np.uint8)


class FakeLineDetector:
    """Returns a fixed list of line bboxes regardless of the image given."""

    def __init__(self, boxes: list[Bbox]) -> None:
        self._boxes = boxes

    def detect(self, image: Any) -> list[Bbox]:
        return list(self._boxes)


class FakeRecognizer:
    """Returns one text per call, in the order `detect()`'s boxes were
    given, so tests can assert exact detector-box-to-text pairing."""

    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls: list[Any] = []

    def recognize(self, crop: Any) -> str:
        self.calls.append(crop)
        return self._texts[len(self.calls) - 1]


def detector_and_recognizer(
    boxes_and_texts: list[tuple[Bbox, str]],
) -> tuple[LineDetector, TextRecognizer]:
    boxes = [b for b, _ in boxes_and_texts]
    texts = [t for _, t in boxes_and_texts]
    return FakeLineDetector(boxes), FakeRecognizer(texts)


class FakeVisionClient:
    """Returns a fixed, scripted response and records every call it
    received so tests can assert exactly what was sent (prompt content,
    number of images, json_mode) without any network access."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete(
        self, *, images: list[Any], system_prompt: str, user_prompt: str, json_mode: bool
    ) -> str:
        self.calls.append(
            {
                "images": images,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "json_mode": json_mode,
            }
        )
        return self.response


class FakeVisionAdapter:
    """Stands in for a real `VisionAdapter` in escalation tests — returns a
    canned `list[Word]` per call and records every `(image, region)` it was
    asked to re-read."""

    def __init__(self, words: list[Any]) -> None:
        self._words = words
        self.calls: list[Any] = []

    def extract(self, image: Any, region: Any) -> list[Any]:
        self.calls.append((image, region))
        return list(self._words)


class FakePage:
    """A minimal stand-in for a pymupdf.Page, for routing tests that only
    ever call `page.get_text()` with no arguments."""

    def __init__(self, text: str) -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text
