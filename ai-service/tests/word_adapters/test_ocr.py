"""OcrAdapter — PaddleOCR (detection) + VietOCR (recognition), both faked."""

from __future__ import annotations

from contract_ocr.word_adapters import OcrAdapter, Region

from .factories import FakeLineDetector, FakeRecognizer, blank_image


class TestOcrAdapter:
    def test_pairs_each_detected_line_with_its_recognized_text(self):
        detector = FakeLineDetector([(10.0, 10.0, 100.0, 30.0), (10.0, 40.0, 100.0, 60.0)])
        recognizer = FakeRecognizer(["Hàng A", "Hàng B"])
        adapter = OcrAdapter(detector=detector, recognizer=recognizer)

        words = adapter.extract(blank_image(), Region(page=2, bbox=(0.0, 0.0, 400.0, 300.0)))

        assert [w.text for w in words] == ["Hàng A", "Hàng B"]
        assert all(w.source == "ocr" for w in words)
        assert all(w.page == 2 for w in words)

    def test_word_bbox_is_offset_by_the_region_origin(self):
        detector = FakeLineDetector([(10.0, 5.0, 50.0, 20.0)])
        recognizer = FakeRecognizer(["Text"])
        adapter = OcrAdapter(detector=detector, recognizer=recognizer)

        region = Region(page=1, bbox=(100.0, 200.0, 400.0, 300.0))
        [word] = adapter.extract(blank_image(), region)

        assert (word.x0, word.y0, word.x1, word.y1) == (110.0, 205.0, 150.0, 220.0)

    def test_blank_recognized_text_is_dropped(self):
        detector = FakeLineDetector([(0.0, 0.0, 10.0, 10.0), (0.0, 20.0, 10.0, 30.0)])
        recognizer = FakeRecognizer(["", "Hàng B"])
        adapter = OcrAdapter(detector=detector, recognizer=recognizer)

        words = adapter.extract(blank_image(), Region(page=1, bbox=(0.0, 0.0, 400.0, 300.0)))

        assert [w.text for w in words] == ["Hàng B"]

    def test_no_detected_lines_yields_no_words(self):
        adapter = OcrAdapter(detector=FakeLineDetector([]), recognizer=FakeRecognizer([]))
        words = adapter.extract(blank_image(), Region(page=1, bbox=(0.0, 0.0, 400.0, 300.0)))
        assert words == []
