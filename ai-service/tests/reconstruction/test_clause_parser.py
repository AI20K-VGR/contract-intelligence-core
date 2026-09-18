import pytest

from contract_ocr.reconstruction.clause_parser import (
    ALPHA_CLOSE_PAREN,
    ALPHA_PAREN,
    DECIMAL,
    KHOAN_LABEL,
    NUMBER_PAREN,
    ROMAN_PAREN,
    SECTION,
    parse_marker,
)


@pytest.mark.parametrize(
    "text,marker_type,normalized,level_hint",
    [
        ("Điều 5. THANH TOÁN", SECTION, "5", 1),
        ("ĐIỀU 12", SECTION, "12", 1),
        ("Article 1", SECTION, "1", 1),
        ("ARTICLE 10 - Term", SECTION, "10", 1),
        ("Section 3", SECTION, "3", 1),
        ("Khoản 2", KHOAN_LABEL, "2", 2),
        ("5.2.1 Some clause", DECIMAL, "5.2.1", 3),
        ("5.1 Bên mua phải thanh toán", DECIMAL, "5.1", 2),
        ("12.3.4", DECIMAL, "12.3.4", 3),
        ("1. Introduction", DECIMAL, "1", 1),
        ("(a) some item", ALPHA_PAREN, "a", None),
        ("(b)", ALPHA_PAREN, "b", None),
        ("(i) sub item", ROMAN_PAREN, "i", None),
        ("(ii)", ROMAN_PAREN, "ii", None),
        ("(iv)", ROMAN_PAREN, "iv", None),
        ("1) first", NUMBER_PAREN, "1", None),
        ("2)", NUMBER_PAREN, "2", None),
        ("a) alt style", ALPHA_CLOSE_PAREN, "a", None),
    ],
)
def test_parse_marker_recognizes_known_forms(text, marker_type, normalized, level_hint):
    marker = parse_marker(text)
    assert marker is not None
    assert marker.marker_type == marker_type
    assert marker.normalized == normalized
    assert marker.level_hint == level_hint


def test_parse_marker_example_from_spec():
    marker = parse_marker("5.2.1")
    assert marker.raw == "5.2.1"
    assert marker.normalized == "5.2.1"
    assert marker.level_hint == 3
    assert marker.marker_type == DECIMAL


@pytest.mark.parametrize(
    "text",
    [
        "30 ngày kể từ ngày nhận được hóa đơn hợp lệ.",
        "Bên mua phải thanh toán trong vòng",
        "đảm bảo việc bàn giao đúng tiến độ.",
        "",
        "   ",
        "CONFIDENTIAL",
    ],
)
def test_parse_marker_returns_none_for_plain_text(text):
    assert parse_marker(text) is None
