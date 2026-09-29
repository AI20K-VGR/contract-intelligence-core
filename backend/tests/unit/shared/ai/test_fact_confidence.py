import time

from contract_intelligence.shared.ai.fact_confidence import (
    cited_lines,
    fact_confidence,
    grounding_score,
)

QUOTE = "3.1. Tổng giá trị hợp đồng là 1.286.400.000 đồng theo phạm vi."


def test_grounding_rewards_only_values_the_quote_contains():
    assert grounding_score("1.286.400.000 đồng", QUOTE) == 1.0
    assert grounding_score("1286400000", QUOTE) == 0.95
    assert grounding_score("1.286.400.00 đồng", QUOTE) == 0.60
    assert grounding_score("2.000.000.000", QUOTE) == 0.20
    assert grounding_score("1.286.400.000", "") == 0.20


def test_a_fact_is_as_weak_as_its_weakest_evidence():
    assert fact_confidence(value="1.286.400.000", quote=QUOTE, review_passed=True) == 1.0
    assert (
        fact_confidence(
            value="1.286.400.000", quote=QUOTE, review_passed=True, line_confidences=[0.97, 0.30]
        )
        == 0.30
    )
    # Unknown OCR confidence neither raises nor lowers the score.
    assert (
        fact_confidence(
            value="1.286.400.000", quote=QUOTE, review_passed=True, line_confidences=[None]
        )
        == 1.0
    )
    assert fact_confidence(value="1.286.400.000", quote=QUOTE, review_passed=False) == 0.80


def test_grounding_stays_fast_when_the_value_is_not_in_the_quote():
    words = "bên b thanh toán giá trị hợp đồng trong vòng mười ngày kể từ ngày ký "
    quote = (words * 30)[:2000]
    value = ("khoản phạt vi phạm được tính trên phần nghĩa vụ chậm thực hiện " * 7)[:400]
    started = time.perf_counter()
    assert grounding_score(value, quote) == 0.20
    assert time.perf_counter() - started < 0.05


def test_near_match_is_found_anywhere_in_a_long_quote():
    quote = "Điều 5. " + "Nội dung không liên quan. " * 40 + QUOTE
    assert grounding_score("1.286.400.00 đồng", quote) == 0.60


def test_cited_lines_are_the_page_lines_inside_the_quote():
    lines = [
        (1, "3.1. Tổng giá trị hợp đồng là", 0.97),
        (2, "1.286.400.000 đồng theo phạm vi.", 0.30),
        (3, "Điều 4. Nghiệm thu", 0.90),
    ]
    assert cited_lines(QUOTE, lines) == [0.97, 0.30]
    assert cited_lines("", lines) == []


def test_short_lines_elsewhere_on_the_page_are_not_cited():
    quote = "b) Bên B thanh toán 30% giá trị hợp đồng trong vòng 10 ngày kể từ ngày ký."
    lines = [
        (1, quote, 0.97),
        (2, "kể từ ngày ký.", 0.97),
        (3, "b)", 0.30),
        (4, "10", 0.50),
        (5, "ngày", 0.30),
    ]
    assert cited_lines(quote, lines) == [0.97, 0.97]
    assert (
        fact_confidence(
            value="30%", quote=quote, review_passed=True, line_confidences=cited_lines(quote, lines)
        )
        == 0.97
    )


def test_lines_named_by_the_citation_win_over_text_matching():
    lines = [(1, "b)", 0.30), (2, "Bên B thanh toán 30% giá trị hợp đồng", 0.97)]
    assert cited_lines("Bên B thanh toán 30%", lines, line_nos={2}) == [0.97]
