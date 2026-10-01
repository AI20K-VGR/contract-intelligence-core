"""merge_into_logical_rows."""

from __future__ import annotations

from contract_ocr.table_reconstruct import (
    detect_column_bounds,
    group_physical_lines,
    merge_into_logical_rows,
    slice_lines,
)
from contract_ocr.table_reconstruct.types import ColumnValue, SlicedLine

from .factories import DEFAULT_COLUMNS, table_words


def _build_rows(rows: list[list[str]], anchor_col: int = 0):
    """Builds sliced rows and merges them with a *given* anchor column —
    `merge_into_logical_rows` takes `anchor_col` as already decided, so
    these tests isolate its own row-splitting logic rather than also
    exercising `pick_anchor_column`'s column-scoring (covered separately
    in test_columns.py).
    """
    words = table_words(rows)
    lines = group_physical_lines(words)
    bounds = detect_column_bounds(lines)
    sliced = slice_lines(lines, bounds)
    return merge_into_logical_rows(sliced, anchor_col), anchor_col


class TestMergeIntoLogicalRows:
    def test_empty_input(self):
        assert merge_into_logical_rows([], 0) == []

    def test_simple_rows_stay_separate(self):
        rows, _ = _build_rows(
            [
                ["1", "Hàng A", "1.000.000"],
                ["2", "Hàng B", "2.000.000"],
            ]
        )
        assert len(rows) == 2
        assert [c.text for c in rows[0].cells] == ["1", "Hàng A", "1.000.000"]
        assert [c.text for c in rows[1].cells] == ["2", "Hàng B", "2.000.000"]

    def test_multiline_cell_wraps_into_one_logical_row(self):
        # The description wraps onto 3 physical lines; only the first
        # carries an STT value.
        rows, _ = _build_rows(
            [
                ["1", "Thiết bị máy tính", "10.000.000"],
                ["", "cấu hình cao", ""],
                ["", "bảo hành 24 tháng", ""],
                ["2", "Hàng B", "2.000.000"],
            ]
        )
        assert len(rows) == 2
        assert rows[0].cells[1].text == "Thiết bị máy tính cấu hình cao bảo hành 24 tháng"
        # Every physical line that contributed text left its own bbox behind.
        assert len(rows[0].cells[1].bboxes) == 3
        assert rows[1].cells[0].text == "2"

    def test_anchor_misread_as_letter_l_is_recovered(self):
        rows, anchor_col = _build_rows(
            [
                ["1", "Hàng A", "1.000.000"],
                ["l", "Hàng B", "2.000.000"],  # OCR confused "1" with "l"
                ["3", "Hàng C", "3.000.000"],
            ]
        )
        assert len(rows) == 3
        assert rows[1].cells[anchor_col].text == "l"
        assert "needs_review" in rows[1].flags

    def test_total_row_in_the_middle_stays_its_own_row(self):
        rows, _ = _build_rows(
            [
                ["1", "Hàng A", "1.500.000"],
                ["", "Tổng cộng", "3.500.000"],
                ["2", "Hàng B", "2.000.000"],
            ]
        )
        assert len(rows) == 3
        assert rows[1].cells[1].text == "Tổng cộng"
        assert "needs_review" in rows[1].flags

    def test_filled_down_cell_inherits_previous_rows_value(self):
        # A "Đơn vị" (unit) column vertically merged across two rows: blank
        # on the second physical line for that column only.
        columns = DEFAULT_COLUMNS + ((440.0, 480.0),)
        words = table_words(
            [
                ["1", "Hàng A", "1.000.000", "Cái"],
                ["2", "Hàng B", "2.000.000", ""],
            ],
            columns=columns,
        )
        lines = group_physical_lines(words)
        bounds = detect_column_bounds(lines)
        sliced = slice_lines(lines, bounds)
        rows = merge_into_logical_rows(sliced, anchor_col=0)

        assert rows[1].cells[3].text == "Cái"
        assert "filled_down" in rows[1].flags

    def test_filled_down_never_applies_to_the_anchor_column(self):
        # A row created via a fallback layer (empty anchor) must NOT have
        # its anchor cell filled in from the row above — that would make a
        # totals row look like a normally-numbered one again.
        rows, anchor_col = _build_rows(
            [
                ["1", "Hàng A", "1.500.000"],
                ["", "Tổng cộng", "3.500.000"],
            ]
        )
        assert rows[1].cells[anchor_col].text == ""

    def test_later_continuation_column_is_not_truncated(self):
        lines = [
            SlicedLine(
                page=1,
                y0=10,
                y1=20,
                columns=[
                    ColumnValue(text="1", bbox=(0, 10, 10, 20)),
                    ColumnValue(text="Hàng hóa", bbox=(20, 10, 80, 20)),
                ],
            ),
            SlicedLine(
                page=1,
                y0=21,
                y1=31,
                columns=[
                    ColumnValue(text="", bbox=None),
                    ColumnValue(text="bảo hành", bbox=(20, 21, 80, 31)),
                    ColumnValue(text="12 tháng", bbox=(90, 21, 130, 31)),
                ],
            ),
        ]

        rows = merge_into_logical_rows(lines, anchor_col=0)

        assert len(rows) == 1
        assert [cell.text for cell in rows[0].cells] == [
            "1",
            "Hàng hóa bảo hành",
            "12 tháng",
        ]
        assert "needs_review" in rows[0].flags
