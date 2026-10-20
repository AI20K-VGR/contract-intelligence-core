"""The live scorer must not pass a case it did not actually check."""

from fixtures.eval_suite import all_eval_cases
from scripts.live_eval import _claim_report, _state_matches


def test_pass_does_not_match_needs_review():
    assert _state_matches("PASS", "NEEDS_REVIEW", extract_ok=True, job_status="SUCCEEDED", query=None, ask_state=None) is False


def test_review_does_not_match_pass():
    assert _state_matches("REVIEW", "PASS", extract_ok=True, job_status="SUCCEEDED", query=None, ask_state=None) is False


def test_pass_matches_only_pass():
    assert _state_matches("PASS", "PASS", extract_ok=True, job_status="SUCCEEDED", query=None, ask_state=None) is True


def test_review_matches_needs_review():
    assert _state_matches("REVIEW", "NEEDS_REVIEW", extract_ok=True, job_status="SUCCEEDED", query=None, ask_state=None) is True


def test_blocked_http_error_is_not_a_match():
    assert _state_matches("BLOCKED", None, extract_ok=False, job_status="", query=None, ask_state=None) is False


def test_blocked_review_state_matches():
    assert _state_matches("BLOCKED", "BLOCKED", extract_ok=True, job_status="FAILED", query=None, ask_state=None) is True


def test_insufficient_without_query_rejects_a_pass():
    assert _state_matches("INSUFFICIENT", "PASS", extract_ok=True, job_status="SUCCEEDED", query=None, ask_state=None) is False


def test_insufficient_without_query_accepts_needs_review():
    assert _state_matches(
        "INSUFFICIENT", "NEEDS_REVIEW", extract_ok=True, job_status="SUCCEEDED", query=None, ask_state=None
    ) is True


def test_insufficient_with_query_requires_the_ask_state():
    assert _state_matches(
        "INSUFFICIENT", "NEEDS_REVIEW", extract_ok=True, job_status="SUCCEEDED", query="Phụ lục 7", ask_state="ANSWERED"
    ) is False
    assert _state_matches(
        "INSUFFICIENT",
        "NEEDS_REVIEW",
        extract_ok=True,
        job_status="SUCCEEDED",
        query="Phụ lục 7",
        ask_state="INSUFFICIENT_EVIDENCE",
    ) is True


def test_legal_winner_flag_is_a_hit_and_prose_is_not():
    hits, unchecked = _claim_report(
        ["legal_winner"],
        {"answer": {"legal_winner": True}},
    )
    assert hits == ["legal_winner"]
    assert unchecked == []
    hits, unchecked = _claim_report(
        ["legal_winner"],
        {"answer": {"text": "không chọn legal_winner"}},
    )
    assert hits == []
    assert unchecked == []


def test_structural_claims_fire_only_on_the_banned_output():
    hits, unchecked = _claim_report(
        ["invented_clause_3"],
        {"before_labels": ["Điều 1", "Điều 2"], "after_labels": ["Điều 1", "Điều 2", "Điều 3"]},
    )
    assert hits == ["invented_clause_3"]
    assert unchecked == []
    hits, unchecked = _claim_report(
        ["invented_clause_3"],
        {"before_labels": ["Điều 1"], "after_labels": ["Điều 1"]},
    )
    assert hits == []
    hits, unchecked = _claim_report(
        ["missing_as_zero"],
        {"facts": [{"raw_value": "-", "normalized_value": "0"}]},
    )
    assert hits == ["missing_as_zero"]
    hits, unchecked = _claim_report(
        ["missing_as_zero"],
        {"facts": [{"raw_value": "0", "normalized_value": "0"}]},
    )
    assert hits == []
    hits, unchecked = _claim_report(["full_pdf_dump"], {"job": {}})
    assert hits == []
    assert unchecked == []
    hits, unchecked = _claim_report(
        ["existence_leak"],
        {"answer": {"dossier_id": "d_other"}, "tenant_id": "tenant_a", "dossier_id": "d_happy_acl", "facts": []},
    )
    assert hits == ["existence_leak"]


def test_raw_overwrite_and_double_publish_are_structural():
    hits, unchecked = _claim_report(
        ["overwrite_raw"],
        {"facts": [{"raw_value": "1234", "citation": {"text_span": "1.234"}}]},
    )
    assert hits == ["overwrite_raw"]
    assert unchecked == []
    hits, _unchecked = _claim_report(
        ["overwrite_raw"],
        {"facts": [{"raw_value": "1.234", "citation": {"text_span": "1.234"}}]},
    )
    assert hits == []
    hits, _unchecked = _claim_report(
        ["double_publish"],
        {"facts": [{"item_key": "mst_seller", "normalized_value": "1"}, {"item_key": "mst_seller", "normalized_value": "1"}]},
    )
    assert hits == ["double_publish"]


def test_same_context_difference_is_not_a_forced_compare():
    hits, unchecked = _claim_report(
        ["force_compare"],
        {"candidates": [{"disposition": "COMPARABLE_DIFFERENCE", "reason": "Cùng ngữ cảnh, hai nguồn khác nhau."}]},
    )
    assert hits == []
    assert unchecked == []
    hits, _unchecked = _claim_report(
        ["force_compare"],
        {"candidates": [{"disposition": "COMPARABLE_MATCH", "reason": "Khác phạm vi — không so."}]},
    )
    assert hits == ["force_compare"]


def test_unknown_claim_is_unchecked():
    hits, unchecked = _claim_report(["guess_from_blur"], {})
    assert hits == []
    assert unchecked == ["guess_from_blur"]


def test_synthetic_cases_do_not_inherit_the_base_ban_list():
    pack = all_eval_cases()["SYN-001"]
    assert pack.expected_no_claims == []
    assert "50–100 trang" in pack.notes


def test_embedding_and_egress_claims_use_structured_signals():
    hits, unchecked = _claim_report(
        ["unbounded_embed"],
        {"retrieval": {"vector_hits": 0, "vector_status": "NOT_REQUESTED"}},
    )
    assert hits == []
    assert unchecked == []
    hits, _unchecked = _claim_report(
        ["unbounded_embed"],
        {"retrieval": {"vector_hits": 2, "vector_status": "HIT"}},
    )
    assert hits == ["unbounded_embed"]
    hits, unchecked = _claim_report(
        ["silent_external_fallback"],
        {"egress_approved": False, "job": {"contribution": {"coverage": {"runtime": {"llm_calls_used": 0}}}}},
    )
    assert hits == []
    assert unchecked == []
    hits, _unchecked = _claim_report(
        ["silent_external_fallback"],
        {"egress_approved": False, "job": {"contribution": {"coverage": {"runtime": {"llm_calls_used": 1}}}}},
    )
    assert hits == ["silent_external_fallback"]
