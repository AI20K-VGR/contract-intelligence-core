"""table_reconstruct must process a `list[Word]` identically no matter which
WordSource produced it — that's the entire point of routing everything
through the same dataclass."""

from __future__ import annotations

import json

from contract_ocr.table_reconstruct import Fragment, build_tables
from contract_ocr.word_adapters import OcrAdapter, Region, VisionAdapter

from .factories import (
    FakeLineDetector,
    FakeRecognizer,
    FakeVisionClient,
    blank_image,
    pdf_page,
)


class TestUniformProcessingAcrossSources:
    def test_native_ocr_and_vision_words_all_build_the_same_table_shape(self):
        native_words = _native_words()
        ocr_words = _ocr_words()
        vision_words = _vision_words()

        assert {w.source for w in native_words} == {"native"}
        assert {w.source for w in ocr_words} == {"ocr"}
        assert {w.source for w in vision_words} == {"vision"}

        for words in (native_words, ocr_words, vision_words):
            fragment = Fragment(doc_id="doc1", page=1, bbox=(0.0, 0.0, 400.0, 300.0), words=words)
            tables = build_tables([fragment])
            assert len(tables) == 1
            rows = [[c.text for c in r.cells] for r in tables[0].rows]
            assert rows == [["1", "Hàng A"], ["2", "Hàng B"]]


def _native_words():
    from contract_ocr.word_adapters import NativeAdapter

    # `build_tables` always treats a non-continuation fragment's first row
    # as its header, so every fixture needs one — "STT"/"Tên" here.
    # "Hàng A"/"Hàng B" as one insert_text call each so PyMuPDF's own word
    # splitter gives the two tokens their natural (small) in-cell spacing —
    # picking that gap by hand would be guessing at font metrics.
    page = pdf_page(
        [
            ("STT", 50, 10),
            ("Tên", 100, 10),
            ("1", 50, 30),
            ("Hàng A", 100, 30),
            ("2", 50, 60),
            ("Hàng B", 100, 60),
        ]
    )
    region = Region(page=1, bbox=(0.0, 0.0, 400.0, 300.0))
    return NativeAdapter().extract(page, region)


def _ocr_words():
    # One detected box per CELL (not one per whole table row) — PaddleOCR's
    # detector naturally separates cells when there's a real gap between
    # columns, which is what makes column detection possible downstream.
    detector = FakeLineDetector(
        [
            (50.0, 10.0, 70.0, 25.0),
            (100.0, 10.0, 200.0, 25.0),
            (50.0, 30.0, 70.0, 45.0),
            (100.0, 30.0, 200.0, 45.0),
            (50.0, 60.0, 70.0, 75.0),
            (100.0, 60.0, 200.0, 75.0),
        ]
    )
    recognizer = FakeRecognizer(["STT", "Tên", "1", "Hàng A", "2", "Hàng B"])
    adapter = OcrAdapter(detector=detector, recognizer=recognizer)
    return adapter.extract(blank_image(), Region(page=1, bbox=(0.0, 0.0, 400.0, 300.0)))


def _vision_words():
    cells = (
        (50.0, 10.0, 80.0, 25.0),
        (100.0, 10.0, 200.0, 25.0),
        (50.0, 30.0, 80.0, 45.0),
        (100.0, 30.0, 200.0, 45.0),
        (50.0, 60.0, 80.0, 75.0),
        (100.0, 60.0, 200.0, 75.0),
    )
    response = json.dumps({"cells": ["STT", "Tên", "1", "Hàng A", "2", "Hàng B"]})
    client = FakeVisionClient(response)
    adapter = VisionAdapter(mode="cells", client=client)
    region = Region(page=1, bbox=(0.0, 0.0, 400.0, 300.0), cells=cells)
    return adapter.extract(blank_image(), region)
