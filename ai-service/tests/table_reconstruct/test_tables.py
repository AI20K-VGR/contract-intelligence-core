"""build_tables."""

from __future__ import annotations

from contract_ocr.table_reconstruct import build_tables

from .factories import fragment


class TestBuildTables:
    def test_single_fragment_produces_one_table(self):
        frag = fragment(
            "doc1", 1, [["STT", "Tên", "Tiền"], ["1", "Hàng A", "1.000.000"], ["2", "Hàng B", "2.000.000"]]
        )
        tables = build_tables([frag])
        assert len(tables) == 1
        assert tables[0].header == ["STT", "Tên", "Tiền"]
        assert [c.text for c in tables[0].rows[0].cells] == ["1", "Hàng A", "1.000.000"]

    def test_table_spanning_two_pages_with_repeated_header_drops_the_repeat(self):
        frag_a = fragment(
            "doc1",
            1,
            [["STT", "Tên", "Tiền"], ["1", "Hàng A", "1.000.000"], ["2", "Hàng B", "2.000.000"]],
            start_y=700.0,
        )
        frag_b = fragment(
            "doc1",
            2,
            [["STT", "Tên", "Tiền"], ["3", "Hàng C", "3.000.000"], ["4", "Hàng D", "4.000.000"]],
            start_y=10.0,
        )
        tables = build_tables([frag_a, frag_b])
        assert len(tables) == 1
        table = tables[0]
        assert table.page_start == 1
        assert table.page_end == 2
        assert table.fragment_ids == [0, 1]
        assert table.header == ["STT", "Tên", "Tiền"]
        assert [r.cells[0].text for r in table.rows] == ["1", "2", "3", "4"]
        # The repeated header row on page 2 must not show up as a data row.
        assert all("Tên" not in r.cells[1].text for r in table.rows)

    def test_table_spanning_two_pages_without_repeated_header_keeps_all_rows(self):
        frag_a = fragment(
            "doc1",
            1,
            [["STT", "Tên", "Tiền"], ["1", "Hàng A", "1.000.000"], ["2", "Hàng B", "2.000.000"]],
            start_y=700.0,
        )
        frag_b = fragment(
            "doc1",
            2,
            [["3", "Hàng C", "3.000.000"], ["4", "Hàng D", "4.000.000"]],
            start_y=10.0,
        )
        tables = build_tables([frag_a, frag_b])
        assert len(tables) == 1
        rows = tables[0].rows
        assert [r.cells[0].text for r in rows] == ["1", "2", "3", "4"]

    def test_two_appendices_with_stt_reset_produce_two_tables(self):
        frag_a = fragment(
            "doc1",
            1,
            [["STT", "Tên", "Tiền"], ["1", "Hàng A", "1.000.000"], ["2", "Hàng B", "2.000.000"]],
        )
        frag_b = fragment(
            "doc1",
            2,
            [["STT", "Tên", "Tiền"], ["1", "Hàng X", "9.000.000"], ["2", "Hàng Y", "8.000.000"]],
        )
        tables = build_tables([frag_a, frag_b])
        assert len(tables) == 2
        assert [r.cells[0].text for r in tables[0].rows] == ["1", "2"]
        assert [r.cells[0].text for r in tables[1].rows] == ["1", "2"]
        assert tables[0].fragment_ids == [0]
        assert tables[1].fragment_ids == [1]

    def test_empty_fragment_list_produces_no_tables(self):
        assert build_tables([]) == []

    def test_each_finalized_table_carries_its_own_checks(self):
        frag = fragment(
            "doc1", 1, [["STT", "Tên", "Tiền"], ["1", "Hàng A", "1.000.000"], ["2", "Hàng B", "2.000.000"]]
        )
        tables = build_tables([frag])
        assert set(tables[0].checks) == {
            "row_count_ok",
            "anchor_continuous",
            "arity_ok",
            "sum_check",
            "vn_words_check",
        }
