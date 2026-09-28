"""parse_vn_number / vn_words_to_number / is_total_row."""

from __future__ import annotations

from decimal import Decimal

import pytest

from contract_ocr.table_reconstruct import (
    Cell,
    LogicalRow,
    is_total_row,
    parse_vn_number,
    vn_words_to_number,
)


class TestParseVnNumber:
    def test_thousands_and_decimal(self):
        assert parse_vn_number("1.234.567,89") == Decimal("1234567.89")

    def test_plain_thousands(self):
        assert parse_vn_number("1.500.000.000") == Decimal("1500000000")

    def test_no_separators(self):
        assert parse_vn_number("15") == Decimal("15")

    def test_negative(self):
        assert parse_vn_number("-2.000") == Decimal("-2000")

    def test_currency_suffix_is_stripped(self):
        assert parse_vn_number("3.500.000 đồng") == Decimal("3500000")
        assert parse_vn_number("3.500.000đ") == Decimal("3500000")

    def test_rejects_non_numeric_text(self):
        with pytest.raises(ValueError):
            parse_vn_number("Tổng cộng")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError):
            parse_vn_number("   ")

    def test_result_is_decimal_never_float(self):
        value = parse_vn_number("1.000.000,5")
        assert isinstance(value, Decimal)
        assert value == Decimal("1000000.5")


class TestVnWordsToNumber:
    def test_one_billion(self):
        assert vn_words_to_number("một tỷ") == Decimal(1_000_000_000)

    def test_one_point_five_billion(self):
        assert vn_words_to_number("một tỷ năm trăm triệu đồng chẵn") == Decimal(1_500_000_000)

    def test_fifteen_million(self):
        assert vn_words_to_number("mười lăm triệu") == Decimal(15_000_000)

    def test_one_hundred_and_five_thousand(self):
        assert vn_words_to_number("một trăm linh năm nghìn") == Decimal(105_000)

    def test_one_billion_and_five(self):
        assert vn_words_to_number("một tỷ không trăm linh năm đồng") == Decimal(1_000_000_005)

    def test_rejects_unrecognized_tokens(self):
        with pytest.raises(ValueError):
            vn_words_to_number("xin chào thế giới")

    def test_rejects_empty_phrase(self):
        with pytest.raises(ValueError):
            vn_words_to_number("   ")


class TestIsTotalRow:
    def _row(self, texts: list[str]) -> LogicalRow:
        return LogicalRow(
            index=0,
            cells=[Cell(text=t, bboxes=[], pages=[]) for t in texts],
            flags=set(),
        )

    def test_total_row_with_missing_stt(self):
        row = self._row(["", "Tổng cộng", "3.500.000"])
        assert is_total_row(row) is True

    def test_ordinary_numbered_row_is_not_total(self):
        row = self._row(["1", "Hàng A", "1.500.000"])
        assert is_total_row(row) is False

    def test_keyword_alone_is_not_enough_without_missing_stt(self):
        # Mentions "cộng" in a description but still carries a normal STT.
        row = self._row(["2", "Cộng thêm phụ kiện", "500.000"])
        assert is_total_row(row) is False

    def test_empty_row_is_not_total(self):
        row = self._row([])
        assert is_total_row(row) is False
