"""detect_column_bounds / pick_anchor_column / column_signature."""

from __future__ import annotations

import pytest

from contract_ocr.table_reconstruct import (
    Config,
    column_signature,
    detect_column_bounds,
    group_physical_lines,
    pick_anchor_column,
)

from .factories import DEFAULT_COLUMNS, table_words


class TestDetectColumnBounds:
    def test_three_columns_produce_four_bounds(self):
        words = table_words(
            [
                ["STT", "Tên", "Tiền"],
                ["1", "Hàng A", "1.000.000"],
                ["2", "Hàng B", "2.000.000"],
            ]
        )
        lines = group_physical_lines(words)
        bounds = detect_column_bounds(lines)
        assert len(bounds) == len(DEFAULT_COLUMNS) + 1

    def test_only_header_and_preview_lines_are_used(self):
        # Only the header + config.column_bounds_preview_lines (default 5)
        # rows feed the projection profile — anything after that is ignored,
        # however differently laid out it is.
        config = Config()
        rows = [["STT", "Tên", "Tiền"]] + [["1", "Hàng A", "1.000.000"]] * 5
        words = table_words(rows)
        words += table_words([["XX", "một cột khác hẳn", "0"]], start_y=200.0)
        lines = group_physical_lines(words)
        assert len(lines) == 7

        bounds_with_extra_line = detect_column_bounds(lines, config)
        bounds_without_it = detect_column_bounds(lines[:6], config)
        assert bounds_with_extra_line == bounds_without_it

    def test_empty_lines_yield_no_bounds(self):
        assert detect_column_bounds([]) == []


class TestPickAnchorColumn:
    def test_sequential_number_column_wins(self):
        preview = [
            ["1", "Hàng A", "1.000.000"],
            ["2", "Hàng B", "2.000.000"],
            ["3", "Hàng C", "500.000"],
        ]
        assert pick_anchor_column(preview) == 0

    def test_excludes_requested_columns(self):
        preview = [
            ["1", "Hàng A", "1.000.000"],
            ["2", "Hàng B", "2.000.000"],
        ]
        # With column 0 excluded, the ascending money column should win.
        assert pick_anchor_column(preview, exclude={0}) == 2

    def test_total_row_does_not_spoil_the_anchor_column(self):
        # Without special handling, the missing STT on the totals row would
        # lower column 0's fill rate below the (fully-filled, ascending)
        # money column's score.
        preview = [
            ["1", "Hàng A", "1.500.000"],
            ["", "Tổng cộng", "1.500.000"],
        ]
        assert pick_anchor_column(preview) == 0

    def test_empty_preview_raises(self):
        with pytest.raises(ValueError):
            pick_anchor_column([])


class TestColumnSignature:
    def test_normalizes_and_rounds(self):
        assert column_signature([0.0, 100.0, 200.0], page_width=400.0) == [0.0, 0.25, 0.5]

    def test_rejects_non_positive_page_width(self):
        with pytest.raises(ValueError):
            column_signature([0.0, 100.0], page_width=0.0)
