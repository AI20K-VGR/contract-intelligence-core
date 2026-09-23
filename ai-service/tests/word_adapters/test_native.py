"""NativeAdapter."""

from __future__ import annotations

from contract_ocr.word_adapters import NativeAdapter, Region

from .factories import pdf_page


class TestNativeAdapter:
    def test_extracts_words_with_source_native_and_region_page(self):
        page = pdf_page([("Hello", 50, 50), ("World", 90, 50)])
        region = Region(page=3, bbox=(0.0, 0.0, 400.0, 300.0))
        words = NativeAdapter().extract(page, region)

        assert [w.text for w in words] == ["Hello", "World"]
        assert all(w.source == "native" for w in words)
        assert all(w.page == 3 for w in words)

    def test_bboxes_come_straight_from_pymupdf_no_extra_processing(self):
        page = pdf_page([("Hello", 50, 50)])
        region = Region(page=1, bbox=(0.0, 0.0, 400.0, 300.0))
        [word] = NativeAdapter().extract(page, region)

        raw = page.get_text("words")[0]
        assert (word.x0, word.y0, word.x1, word.y1) == (raw[0], raw[1], raw[2], raw[3])

    def test_only_words_within_the_region_are_returned(self):
        page = pdf_page([("TopLine", 50, 50), ("BottomLine", 50, 250)])
        top_region = Region(page=1, bbox=(0.0, 0.0, 400.0, 150.0))
        words = NativeAdapter().extract(page, top_region)

        assert [w.text for w in words] == ["TopLine"]

    def test_empty_page_yields_no_words(self):
        page = pdf_page([])
        region = Region(page=1, bbox=(0.0, 0.0, 400.0, 300.0))
        assert NativeAdapter().extract(page, region) == []
