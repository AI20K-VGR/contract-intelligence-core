"""choose_adapter."""

from __future__ import annotations

from contract_ocr.word_adapters import NativeAdapter, OcrAdapter, choose_adapter

from .factories import FakePage


class TestChooseAdapter:
    def test_long_clean_native_text_uses_native_adapter(self):
        page = FakePage("Hợp đồng số 123/2024. " * 20)
        assert isinstance(choose_adapter(page), NativeAdapter)

    def test_short_native_text_falls_back_to_ocr(self):
        page = FakePage("Quá ngắn")
        assert isinstance(choose_adapter(page), OcrAdapter)

    def test_garbled_native_text_falls_back_to_ocr(self):
        # Long enough, but mostly garbage characters — e.g. a scan with a
        # noisy text layer, or a legacy TCVN3/VNI-encoded font.
        page = FakePage("#$^&*{}[]<>~|\\" * 20)
        assert isinstance(choose_adapter(page), OcrAdapter)

    def test_blank_page_falls_back_to_ocr(self):
        page = FakePage("")
        assert isinstance(choose_adapter(page), OcrAdapter)
