from __future__ import annotations

import unicodedata

import pytest

from app.pipeline.contract_graph.address import (
    Address,
    canonical,
    inherit,
    parse_addresses,
    parse_parent_context,
)


def _one(text: str) -> Address:
    addrs = parse_addresses(text)
    assert len(addrs) == 1, addrs
    return addrs[0]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("điểm c khoản 1 Điều 3", "diem c khoan 1 dieu 3"),
        ("Khoản 2 của Điều 5", "khoan 2 dieu 5"),
        ("ĐIỀU 7", "dieu 7"),
        ("Sửa đổi, bổ sung khoản 2 Điều 5 như sau", "khoan 2 dieu 5"),
        ("Bãi bỏ Điều 07.", "dieu 7"),
    ],
)
def test_full_address_canonical(text, expected):
    assert canonical(_one(text)) == expected


def test_d_stroke_point_letter_is_preserved():
    stroke = _one("điểm đ khoản 2 Điều 1")
    plain = _one("điểm d khoản 2 Điều 1")

    assert stroke.diem == "đ"
    assert canonical(stroke) == "diem đ khoan 2 dieu 1"
    assert canonical(stroke) != canonical(plain)


@pytest.mark.parametrize(
    "text",
    ["Điều 5.3", "khoản 5.3", "Sửa đổi 5.3 như sau", "Sửa đổi, bổ sung Điều 5.3 của Hợp đồng"],
)
def test_contract_style_numbering(text):
    addr = _one(text)

    assert (addr.dieu, addr.khoan) == ("5", "3")
    assert canonical(addr) == "khoan 3 dieu 5"


def test_bare_dotted_number_without_verb_is_not_an_address():
    assert parse_addresses("đơn giá 5.3 triệu đồng") == []


def test_insert_after_keeps_new_address_and_anchor():
    addr = _one("Bổ sung khoản 5 vào sau khoản 4 Điều 4 như sau")

    assert canonical(addr) == "khoan 5 dieu 4"
    assert addr.insert_after is not None
    assert canonical(addr.insert_after) == "khoan 4 dieu 4"


def test_insert_point_after_point():
    addr = _one("Bổ sung điểm đ vào sau điểm d khoản 2 Điều 3")

    assert canonical(addr) == "diem đ khoan 2 dieu 3"
    assert canonical(addr.insert_after) == "diem d khoan 2 dieu 3"


def test_insert_into_container_without_anchor():
    addr = _one("bổ sung điểm đ vào khoản 2 Điều 3")

    assert addr.insert_after is None
    assert canonical(addr) == "diem đ khoan 2 dieu 3"


@pytest.mark.parametrize(
    ("text", "expected", "stripped"),
    [
        ("khoản 5a Điều 18", "khoan 5a dieu 18", "khoan 5 dieu 18"),
        ("điểm d1 khoản 2 Điều 3", "diem d1 khoan 2 dieu 3", "diem d khoan 2 dieu 3"),
        ("điểm i1 khoản 1 Điều 4", "diem i1 khoan 1 dieu 4", "diem i khoan 1 dieu 4"),
        ("điểm a1 khoản 4 Điều 4", "diem a1 khoan 4 dieu 4", "diem a khoan 4 dieu 4"),
        ("Điều 30a", "dieu 30a", "dieu 30"),
        ("khoản 05A Điều 018", "khoan 5a dieu 18", "khoan 5 dieu 18"),
    ],
)
def test_suffix_addresses_canonical(text, expected, stripped):
    got = canonical(_one(text))

    assert got == expected
    assert got != stripped


def test_insert_suffix_point_list():
    addrs = parse_addresses("Bổ sung điểm d1, d2 vào sau điểm d khoản 2 Điều 3")

    assert [canonical(a) for a in addrs] == [
        "diem d1 khoan 2 dieu 3",
        "diem d2 khoan 2 dieu 3",
    ]
    assert [canonical(a.insert_after) for a in addrs] == ["diem d khoan 2 dieu 3"] * 2


def test_insert_suffix_clause_differs_from_anchor():
    addr = _one("Bổ sung khoản 5a vào sau khoản 5 Điều 18")

    assert canonical(addr) == "khoan 5a dieu 18"
    assert canonical(addr.insert_after) == "khoan 5 dieu 18"
    assert canonical(addr) != canonical(addr.insert_after)


def test_insert_article_after_article():
    addr = _one("Bổ sung Điều 30a vào sau Điều 30 như sau")

    assert canonical(addr) == "dieu 30a"
    assert canonical(addr.insert_after) == "dieu 30"


@pytest.mark.parametrize(
    ("text", "number"),
    [
        ("Phụ lục 01", "1"),
        ("Phụ lục số 2", "2"),
        ("Phụ lục II", "2"),
        ("PHỤ LỤC XX", "20"),
    ],
)
def test_annex_numbers_arabic_padded_and_roman(text, number):
    addr = _one(text)

    assert addr.phu_luc == number
    assert canonical(addr) == f"phu luc {number}"


def test_article_inside_annex():
    addr = _one("Điều 1 Phụ lục 1")

    assert (addr.dieu, addr.phu_luc) == ("1", "1")
    assert canonical(addr) == "dieu 1 phu luc 1"


@pytest.mark.parametrize(
    ("text", "level"),
    [("khoản này", "khoan"), ("Điểm này", "diem"), ("Điều này", "dieu")],
)
def test_self_reference(text, level):
    addr = _one(text)

    assert addr.self_level == level
    assert (addr.dieu, addr.khoan, addr.diem) == (None, None, None)


def test_self_article_with_explicit_clause():
    addr = _one("theo khoản 2 Điều này")

    assert (addr.khoan, addr.self_level) == ("2", "dieu")


def test_relative_point_has_single_level():
    addr = _one("Sửa đổi, bổ sung điểm a như sau")

    assert (addr.diem, addr.khoan, addr.dieu) == ("a", None, None)


def test_list_of_targets_shares_article():
    addrs = parse_addresses("Bãi bỏ khoản 3 và khoản 4 Điều 7")

    assert [canonical(a) for a in addrs] == ["khoan 3 dieu 7", "khoan 4 dieu 7"]
    assert {a.dieu for a in addrs} == {"7"}


def test_bare_clause_list():
    addrs = parse_addresses("Bãi bỏ khoản 1, 2 và 3 Điều 9")

    assert [canonical(a) for a in addrs] == ["khoan 1 dieu 9", "khoan 2 dieu 9", "khoan 3 dieu 9"]


def test_parent_context_with_multiple_clauses():
    parent = parse_parent_context(
        "Sửa đổi, bổ sung một số điểm của khoản 1 và khoản 2 Điều 3 như sau"
    )

    assert parent is not None
    assert parent.dieu == "3"
    assert parent.khoan is None
    assert parent.khoan_options == ("1", "2")


def test_parent_context_insert_into_two_clauses():
    parent = parse_parent_context(
        "Bổ sung một điểm vào khoản 4 và một khoản vào sau khoản 5 của Điều 18 như sau"
    )

    assert parent == Address(dieu="18", khoan_options=("4", "5"))


def test_parent_context_single_article():
    assert parse_parent_context("Sửa đổi, bổ sung Điều 4 như sau") == Address(dieu="4")


def test_parent_context_without_address_is_none():
    assert parse_parent_context("Sửa đổi một số điều như sau") is None


def test_parent_context_across_articles_is_none():
    assert parse_parent_context("Sửa đổi Điều 4 và Điều 5 như sau") is None


def test_inherit_fills_missing_levels_without_overwrite():
    parent = Address(dieu="3", khoan="1")

    assert inherit(Address(diem="c"), parent) == Address(dieu="3", khoan="1", diem="c")
    # child already names its clause: only the article is filled
    assert inherit(Address(khoan="2", diem="a"), parent) == Address(dieu="3", khoan="2", diem="a")
    # child already names its article: kept as is
    full = Address(dieu="9", diem="b")
    assert inherit(full, parent) == full
    # multi-clause parent: the child gets the options, never a guessed clause
    multi = Address(dieu="3", khoan_options=("1", "2"))
    assert inherit(Address(diem="a"), multi) == Address(
        dieu="3", diem="a", khoan_options=("1", "2")
    )
    # the anchor of an insertion inherits too
    child = Address(diem="i1", khoan="1", insert_after=Address(diem="i", khoan="1"))
    assert inherit(child, multi) == Address(
        dieu="3", khoan="1", diem="i1", insert_after=Address(dieu="3", khoan="1", diem="i")
    )
    # self reference is resolved from the source node, not from the parent item
    assert inherit(Address(self_level="khoan"), parent) == Address(self_level="khoan")


def test_inherit_without_parent_is_identity():
    child = Address(diem="a")

    assert inherit(child, None) is child


def test_nfd_input_parses_like_nfc():
    text = "Bổ sung điểm đ vào sau điểm d khoản 2 Điều 3"
    nfd = unicodedata.normalize("NFD", text)

    assert nfd != text
    assert parse_addresses(nfd) == parse_addresses(text)


@pytest.mark.parametrize(
    "text",
    ["sửa chữa hàng lỗi", "", "Bên Bán giao hàng tại điểm hẹn", "điều kiện thanh toán khoản tiền"],
)
def test_non_address_text_returns_empty(text):
    assert parse_addresses(text) == []


def test_canonical_never_includes_insert_anchor():
    addr = Address(dieu="4", khoan="5", insert_after=Address(dieu="4", khoan="4"))

    assert canonical(addr) == "khoan 5 dieu 4"


@pytest.mark.parametrize(
    "text",
    [
        "Sửa đổi, bổ sung điểm b.7 Khoản 3 Điều 16 như sau",
        "điểm 3 khoản 2 Điều 5",
        "Sửa đổi Điều 1 Phụ lục XXV",
    ],
)
def test_unreadable_level_never_degrades_to_a_coarser_address(text):
    # dropping the unreadable "điểm b.7" would silently target the whole "khoản 3 Điều 16"
    assert parse_addresses(text) == []
