from __future__ import annotations

from dataclasses import replace

from app.contracts.clause_frames import Evidence, Slot
from app.pipeline.frame_comparison import compare_frames
from app.pipeline.frame_extraction import extract_frames

from scripts.collect_e2e_service_logs import _redact
from scripts.run_semantic_v2_e2e import run_case


def test_metamorphic_opposite_polarity_is_a_review_candidate():
    result = run_case(
        "Bên A phải thanh toán cho hóa đơn 30% khi ký.",
        "Bên A không được thanh toán cho hóa đơn 30% khi ký.",
        mode="local-only",
    )
    assert result["coverage"]["provider_calls"] == 0
    assert any(pair["disposition"] == "CONFLICT_CANDIDATE" for pair in result["pairs"])


def test_metamorphic_same_milestone_value_delta_is_retained():
    result = run_case(
        "Bên A phải thanh toán cho hóa đơn 30% khi ký.",
        "Bên A phải thanh toán cho hóa đơn 40% khi ký.",
        mode="local-only",
    )
    assert any(pair["disposition"] == "COMPARABLE_DIFFERENCE" for pair in result["pairs"])


def test_distinct_milestones_are_not_a_false_conflict():
    result = run_case(
        "Bên A phải thanh toán cho hóa đơn 30% khi ký.",
        "Bên A phải thanh toán cho hóa đơn 40% sau khi giao hàng.",
        mode="local-only",
    )
    assert all(pair["disposition"] != "CONFLICT_CANDIDATE" for pair in result["pairs"])


def test_generic_entire_agreement_text_does_not_create_amendment():
    result = run_case(
        "Các bên xác nhận toàn bộ Điều 1 đến Điều 18 là thỏa thuận.",
        "Các bên xác nhận toàn bộ Điều 1 đến Điều 18 là thỏa thuận.",
        mode="local-only",
    )
    assert result["timeline"] == []
    assert result["coverage"]["amendment_state"] == "NOT_REQUESTED"


def test_all_modes_keep_deterministic_pair_when_provider_is_disabled():
    outputs = [
        run_case(
            "Bên A phải thanh toán cho hóa đơn 30% khi ký.",
            "Bên A không được thanh toán cho hóa đơn 30% khi ký.",
            mode=mode,
        )
        for mode in ("local-only", "vector-only", "llm-only", "full")
    ]
    assert [len(output["pairs"]) for output in outputs] == [1, 1, 1, 1]
    assert all(output["coverage"]["deterministic_pairs"] == 1 for output in outputs)


def test_unparsed_optional_condition_never_becomes_duplicate():
    left = extract_frames(
        Evidence("body", "snapshot-body", "body-1", "BÃªn A pháº£i thanh toÃ¡n 30% khi kÃ½."),
        profile="SALES",
        dossier_id="dossier",
    )[0]
    right = extract_frames(
        Evidence("annex", "snapshot-annex", "annex-1", "BÃªn A pháº£i thanh toÃ¡n 30% khi kÃ½."),
        profile="SALES",
        dossier_id="dossier",
    )[0]
    left_slots = dict(left.slots)
    right_slots = dict(right.slots)
    left_slots["condition"] = Slot(None, "UNKNOWN", left.evidence, "not_assessed")
    right_slots["condition"] = Slot(None, "UNKNOWN", right.evidence, "not_assessed")
    pair = compare_frames(
        replace(left, slots=tuple(left_slots.items())),
        replace(right, slots=tuple(right_slots.items())),
    )
    assert pair.disposition != "DUPLICATE"


def test_unknown_quantity_context_never_becomes_duplicate():
    left = extract_frames(
        Evidence("body", "snapshot-body", "body-quantity", "B\u00ean A ph\u1ea3i thanh to\u00e1n cho h\u00f3a \u0111\u01a1n 30% khi k\u00fd."),
        profile="SALES",
        dossier_id="dossier",
    )[0]
    right = extract_frames(
        Evidence("annex", "snapshot-annex", "annex-quantity", "B\u00ean A ph\u1ea3i thanh to\u00e1n cho h\u00f3a \u0111\u01a1n 30% khi k\u00fd."),
        profile="SALES",
        dossier_id="dossier",
    )[0]
    pair = compare_frames(left, right)
    assert pair.disposition != "DUPLICATE"
    assert "quantity_context" in pair.reason


def test_service_log_redaction_consumes_complete_secret_values():
    raw = "Bearer bearer-value sk-DEMO_SENTINEL_123456789 password=pass-value api_key=api-value"
    safe = _redact(raw)
    assert "bearer-value" not in safe
    assert "sk-DEMO_SENTINEL_123456789" not in safe
    assert "pass-value" not in safe
    assert "api-value" not in safe
