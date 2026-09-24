from contract_ocr.reconstruction.paragraph_merger import (
    is_hyphenated_break,
    merge_fragments,
    merge_texts,
)
from contract_ocr.reconstruction.provenance import TextFragment


def test_merge_texts_joins_with_single_space():
    merged = merge_texts(
        "Bên mua phải thanh toán trong vòng", "30 ngày kể từ ngày nhận được hóa đơn hợp lệ."
    )
    assert (
        merged == "Bên mua phải thanh toán trong vòng 30 ngày kể từ ngày nhận được hóa đơn hợp lệ."
    )


def test_merge_texts_never_alters_the_words_themselves():
    a = "Số tiền 100.000.000 VND phải thanh toán trước ngày"
    b = "15/09/2026 theo hợp đồng số HD-001."
    merged = merge_texts(a, b)
    assert "100.000.000 VND" in merged
    assert "15/09/2026" in merged
    assert "HD-001" in merged


def test_hyphenated_line_break_is_joined_without_the_hyphen():
    assert is_hyphenated_break("thanh toá-", "n trong vòng đầy đủ.")
    merged = merge_texts("thanh toá-", "n trong vòng đầy đủ.")
    assert merged == "thanh toán trong vòng đầy đủ."


def test_hyphen_is_not_dropped_when_it_is_not_a_word_break():
    # A lone "-" bullet/dash with no real word before it must not be treated
    # as a hyphenated line-break.
    assert not is_hyphenated_break("-", "áp dụng cho mọi hợp đồng.")


def test_hyphen_is_not_dropped_when_next_starts_uppercase():
    # Next fragment starting uppercase looks like a new sentence, not a
    # continuation of the hyphenated word.
    assert not is_hyphenated_break("thanh toá-", "Bên bán có trách nhiệm khác.")


def test_merge_fragments_case1_paragraph_across_pages():
    fragments = [
        TextFragment(10, "p10_b02", "Bên mua phải thanh toán trong vòng"),
        TextFragment(11, "p11_b01", "30 ngày kể từ ngày nhận được hóa đơn hợp lệ."),
    ]
    merged, refs = merge_fragments(fragments)

    assert (
        merged == "Bên mua phải thanh toán trong vòng 30 ngày kể từ ngày nhận được hóa đơn hợp lệ."
    )
    assert [r.page for r in refs] == [10, 11]
    assert [r.block_id for r in refs] == ["p10_b02", "p11_b01"]

    # Case 10: provenance must be recoverable — every source ref must carry
    # both `page` and `block_id`, and its span must round-trip into `merged`.
    for ref in refs:
        assert ref.page is not None
        assert ref.block_id
        assert ref.char_start is not None
        assert ref.char_end is not None
        assert ref.char_end > ref.char_start

    assert merged[refs[0].char_start : refs[0].char_end] == "Bên mua phải thanh toán trong vòng"
    assert (
        merged[refs[1].char_start : refs[1].char_end]
        == "30 ngày kể từ ngày nhận được hóa đơn hợp lệ."
    )


def test_merge_fragments_with_hyphenated_word_split():
    fragments = [
        TextFragment(5, "p5_b09", "Bên bán có nghĩa vụ thanh toá-"),
        TextFragment(6, "p6_b01", "n đầy đủ các khoản phí phát sinh."),
    ]
    merged, refs = merge_fragments(fragments)
    assert merged == "Bên bán có nghĩa vụ thanh toán đầy đủ các khoản phí phát sinh."
    assert merged[refs[0].char_start : refs[0].char_end] == "Bên bán có nghĩa vụ thanh toá"
    assert merged[refs[1].char_start : refs[1].char_end] == "n đầy đủ các khoản phí phát sinh."


def test_merge_fragments_single_fragment_is_a_noop():
    merged, refs = merge_fragments([TextFragment(1, "b1", "Chỉ một đoạn duy nhất.")])
    assert merged == "Chỉ một đoạn duy nhất."
    assert len(refs) == 1
    assert refs[0].char_start == 0
    assert refs[0].char_end == len(merged)


def test_merge_fragments_empty_list():
    merged, refs = merge_fragments([])
    assert merged == ""
    assert refs == []
