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


def test_cited_lines_are_the_page_lines_inside_the_quote():
    lines = [
        ("3.1. Tổng giá trị hợp đồng là", 0.97),
        ("1.286.400.000 đồng theo phạm vi.", 0.30),
        ("Điều 4. Nghiệm thu", 0.90),
    ]
    assert cited_lines(QUOTE, lines) == [0.97, 0.30]
    assert cited_lines("", lines) == []
