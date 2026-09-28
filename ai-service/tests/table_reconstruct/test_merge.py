"""should_merge."""

from __future__ import annotations

from contract_ocr.table_reconstruct import Fragment, should_merge

from .factories import DEFAULT_PAGE_BBOX, fragment


class TestShouldMerge:
    def test_different_doc_id_is_a_hard_gate(self):
        frag_a = fragment("doc1", 1, [["1", "Hàng A", "1.000.000"]])
        frag_b = fragment("doc2", 2, [["2", "Hàng B", "2.000.000"]])
        merged, score, reasons = should_merge(frag_a, frag_b)
        assert merged is False
        assert score == 0
        assert reasons == ["different doc_id"]

    def test_continuous_anchor_and_matching_columns_merge(self):
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
        merged, score, reasons = should_merge(frag_a, frag_b)
        assert merged is True
        assert score >= 5
        assert any("anchor column continuous" in r for r in reasons)
        assert any("no header row" in r for r in reasons)

    def test_two_different_appendices_with_stt_reset_to_1_must_split(self):
        # Same table template, but frag_b starts its own STT sequence at 1:
        # a brand new table (e.g. a second appendix), not a continuation.
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
        merged, score, reasons = should_merge(frag_a, frag_b)
        assert merged is False
        assert score == 0
        assert reasons == ["anchor column resets to 1"]

    def test_heading_barrier_between_fragments_blocks_merge(self):
        frag_a = fragment(
            "doc1",
            1,
            [["STT", "Tên", "Tiền"], ["1", "Hàng A", "1.000.000"], ["2", "Hàng B", "2.000.000"]],
        )
        # A "PHỤ LỤC 2" heading line bled into the top of the next fragment.
        frag_b = fragment(
            "doc1",
            2,
            [["", "PHỤ LỤC 2", ""], ["3", "Hàng C", "3.000.000"]],
        )
        merged, score, reasons = should_merge(frag_a, frag_b)
        assert merged is False
        assert score == 0
        assert "heading barrier" in reasons[0]

    def test_empty_fragment_is_a_hard_gate(self):
        frag_a = fragment("doc1", 1, [["1", "Hàng A", "1.000.000"]])
        frag_b = Fragment(doc_id="doc1", page=2, bbox=DEFAULT_PAGE_BBOX, words=[])
        merged, score, reasons = should_merge(frag_a, frag_b)
        assert merged is False
        assert score == 0
