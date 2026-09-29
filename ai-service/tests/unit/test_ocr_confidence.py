from contract_ocr.domain.ocr_confidence import line_text_confidence


def test_the_most_severe_review_flag_wins():
    assert line_text_confidence(verified=True, arbitrated=False, review=[]) == 0.97
    assert line_text_confidence(verified=True, arbitrated=True, review=[]) == 0.90
    assert line_text_confidence(verified=False, arbitrated=False, review=[]) == 0.90
    assert (
        line_text_confidence(
            verified=True,
            arbitrated=True,
            review=["spelling_unverified", "critical_field_conflict"],
        )
        == 0.30
    )


def test_an_unknown_review_flag_is_still_a_doubt():
    assert line_text_confidence(verified=True, arbitrated=False, review=["new_flag"]) == 0.50
