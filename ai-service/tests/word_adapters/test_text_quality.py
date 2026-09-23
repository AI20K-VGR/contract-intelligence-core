"""garbage_char_ratio / valid_word_ratio."""

from __future__ import annotations

from contract_ocr.word_adapters import garbage_char_ratio, valid_word_ratio


class TestGarbageCharRatio:
    def test_clean_vietnamese_text_has_zero_garbage(self):
        assert garbage_char_ratio("Hợp đồng số 123/2024/HĐKT giữa hai bên, ngày 01/01/2024.") == 0.0

    def test_symbol_heavy_scan_garbage_has_high_ratio(self):
        assert garbage_char_ratio("#$^&*{}[]<>~|\\") == 1.0

    def test_mixed_text_is_between_zero_and_one(self):
        ratio = garbage_char_ratio("Hợp đồng ¤¤¤ số 123")
        assert 0.0 < ratio < 1.0

    def test_empty_string_is_zero(self):
        assert garbage_char_ratio("") == 0.0


class TestValidWordRatio:
    def test_all_clean_words_is_one(self):
        assert valid_word_ratio(["Hợp", "đồng", "123"]) == 1.0

    def test_garbled_words_lower_the_ratio(self):
        ratio = valid_word_ratio(["Hợp", "đồng", "#@!!", "l|||"])
        assert ratio == 0.5

    def test_empty_list_is_zero(self):
        assert valid_word_ratio([]) == 0.0

    def test_blank_only_tokens_are_ignored_not_counted_as_invalid(self):
        assert valid_word_ratio(["Hợp", "   ", "đồng"]) == 1.0
