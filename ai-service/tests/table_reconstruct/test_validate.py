"""validate."""

from __future__ import annotations

from decimal import Decimal

from contract_ocr.table_reconstruct import build_tables, validate

from .factories import fragment


class TestValidate:
    def test_structural_checks_pass_for_a_cleanly_numbered_table(self):
        frag = fragment(
            "doc1",
            1,
            [
                ["STT", "Tên", "Tiền"],
                ["1", "Hàng A", "1.500.000"],
                ["2", "Hàng B", "2.000.000"],
            ],
        )
        table = build_tables([frag])[0]
        checks = validate(table)
        assert checks["row_count_ok"]["passed"] is True
        assert checks["anchor_continuous"]["passed"] is True
        assert checks["arity_ok"]["passed"] is True

    def test_row_count_ok_reflects_a_totals_row_having_no_stt(self):
        # A totals row is intentionally un-numbered, so max(anchor) < len(rows)
        # here — row_count_ok correctly flags this as informational, not a
        # bug: the check is only meaningful for tables without extra rows.
        frag = fragment(
            "doc1",
            1,
            [
                ["STT", "Tên", "Tiền"],
                ["1", "Hàng A", "1.500.000"],
                ["2", "Hàng B", "2.000.000"],
                ["", "Tổng cộng", "3.500.000"],
            ],
        )
        table = build_tables([frag])[0]
        checks = validate(table)
        assert checks["row_count_ok"]["passed"] is False
        assert checks["row_count_ok"]["expected"] == 3
        assert checks["row_count_ok"]["actual"] == 2
        assert checks["sum_check"]["passed"] is True
        assert checks["sum_check"]["expected"] == Decimal("3500000")

    def test_sum_check_detects_a_missing_row(self):
        # The totals row claims 6.000.000 but only 1.500.000 + 2.000.000 of
        # data rows are actually present — a row is missing.
        frag = fragment(
            "doc1",
            1,
            [
                ["STT", "Tên", "Tiền"],
                ["1", "Hàng A", "1.500.000"],
                ["2", "Hàng B", "2.000.000"],
                ["", "Tổng cộng", "6.000.000"],
            ],
        )
        table = build_tables([frag])[0]
        checks = validate(table)
        assert checks["sum_check"]["passed"] is False
        assert checks["sum_check"]["expected"] == Decimal("3500000")
        assert checks["sum_check"]["actual"] == Decimal("6000000")
        assert checks["sum_check"]["offending_rows"]

    def test_sum_check_is_vacuously_true_without_a_total_row(self):
        frag = fragment(
            "doc1", 1, [["STT", "Tên", "Tiền"], ["1", "Hàng A", "1.500.000"], ["2", "Hàng B", "2.000.000"]]
        )
        table = build_tables([frag])[0]
        checks = validate(table)
        assert checks["sum_check"]["passed"] is True
        assert checks["sum_check"]["expected"] is None

    def test_vn_words_check_matches_the_declared_total(self):
        frag = fragment(
            "doc1",
            1,
            [
                ["STT", "Tên", "Tiền"],
                ["1", "Hàng A", "1.500.000"],
                ["", "Tổng cộng", "1.500.000"],
                ["", "(Bằng chữ: Một triệu năm trăm nghìn đồng chẵn)", ""],
            ],
        )
        table = build_tables([frag])[0]
        checks = validate(table)
        assert checks["vn_words_check"]["passed"] is True
        assert checks["vn_words_check"]["expected"] == Decimal(1_500_000)
        assert checks["vn_words_check"]["actual"] == Decimal(1_500_000)

    def test_vn_words_check_flags_a_mismatch(self):
        frag = fragment(
            "doc1",
            1,
            [
                ["STT", "Tên", "Tiền"],
                ["1", "Hàng A", "1.500.000"],
                ["", "Tổng cộng", "1.500.000"],
                ["", "(Bằng chữ: Hai triệu đồng chẵn)", ""],
            ],
        )
        table = build_tables([frag])[0]
        checks = validate(table)
        assert checks["vn_words_check"]["passed"] is False
        assert checks["vn_words_check"]["expected"] == Decimal(1_500_000)
        assert checks["vn_words_check"]["actual"] == Decimal(2_000_000)

    def test_arity_ok_flags_rows_with_wrong_column_count(self):
        frag = fragment(
            "doc1", 1, [["STT", "Tên", "Tiền"], ["1", "Hàng A", "1.000.000"], ["2", "Hàng B", "2.000.000"]]
        )
        table = build_tables([frag])[0]
        table.rows[1].cells.pop()  # corrupt one row's arity
        checks = validate(table)
        assert checks["arity_ok"]["passed"] is False
        assert checks["arity_ok"]["offending_rows"] == [1]
