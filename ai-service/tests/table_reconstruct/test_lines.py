"""group_physical_lines."""

from __future__ import annotations

from contract_ocr.table_reconstruct import Config, group_physical_lines

from .factories import word


class TestGroupPhysicalLines:
    def test_empty_input(self):
        assert group_physical_lines([]) == []

    def test_words_on_same_y_band_form_one_line(self):
        words = [
            word("STT", 50, 10, 80, 22),
            word("Tên", 100, 10, 150, 22),
            word("Tiền", 250, 11, 300, 23),
        ]
        lines = group_physical_lines(words)
        assert len(lines) == 1
        assert [w.text for w in lines[0].words] == ["STT", "Tên", "Tiền"]

    def test_words_far_apart_in_y_form_separate_lines(self):
        words = [
            word("1", 50, 10, 80, 22),
            word("2", 50, 60, 80, 72),
        ]
        lines = group_physical_lines(words)
        assert len(lines) == 2
        assert lines[0].y0 < lines[1].y0

    def test_lines_are_grouped_independently_per_page(self):
        words = [
            word("1", 50, 10, 80, 22, page=1),
            word("1", 50, 10, 80, 22, page=2),
        ]
        lines = group_physical_lines(words)
        assert [line.page for line in lines] == [1, 2]

    def test_within_line_words_are_sorted_left_to_right(self):
        words = [
            word("B", 200, 10, 220, 22),
            word("A", 50, 10, 70, 22),
        ]
        lines = group_physical_lines(words)
        assert [w.text for w in lines[0].words] == ["A", "B"]

    def test_tolerance_scales_with_median_word_height(self):
        # Median height is 12 here; tolerance = 0.6 * 12 = 7.2, so a 5pt
        # y-center gap should still be treated as the same line.
        config = Config()
        words = [
            word("STT", 50, 10.0, 80, 22.0),
            word("Tên", 100, 12.0, 150, 24.0),
        ]
        lines = group_physical_lines(words, config)
        assert len(lines) == 1
