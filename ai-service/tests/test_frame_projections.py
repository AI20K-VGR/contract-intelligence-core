from __future__ import annotations

from dataclasses import replace

import pytest

from app.contracts.clause_frames import Evidence, TimelineEdge
from app.pipeline.frame_extraction import extract_frames
from app.pipeline.frame_projections import project_frames


def extract(text):
    return extract_frames(Evidence("doc", "s1", "p1/n1", text),
                          profile="SALES", dossier_id="d1")


def test_negation_and_permission_have_distinct_modality_and_family():
    prohibited = extract("Bên B không được thanh toán cho bên A.")[0]
    permitted = extract("Bên B được phép thanh toán cho bên A.")[0]
    assert prohibited.family == "PROHIBITION"
    assert prohibited.get("modality_negation").value == "PROHIBITED"
    assert permitted.family == "RIGHT"
    assert permitted.get("modality_negation").value == "PERMITTED"


def test_passive_payment_does_not_invent_payer():
    frame = extract("Bên B được thanh toán.")[0]
    assert frame.get("actor").state == "UNKNOWN"
    assert frame.get("beneficiary").value == "B"


def test_unknown_clause_stays_visible_and_not_mapped():
    projection = project_frames(extract("Bên B thực hiện công việc khác."))
    assert len(projection.rows) == 1
    assert projection.rows[0].get("action").state == "UNKNOWN"
    assert projection.review_reasons


def test_multiple_actions_keep_separate_evidence_frames():
    frames = extract("Bên B phải thanh toán; Bên A phải giao hàng.")
    assert len(frames) == 2
    assert {frame.get("action").value for frame in frames} == {"PAY", "DELIVER"}
    assert len({frame.frame_id for frame in frames}) == 2


def test_amount_currency_extraction_preserves_unknown_context():
    frame = extract("Bên B phải thanh toán 500 VND.")[0]
    assert str(frame.get("amount").value) == "500"
    assert frame.get("currency").value == "VND"
    assert frame.get("base").state == "UNKNOWN"
    assert frame.get("period").state == "UNKNOWN"


def test_no_annex_reference_inferred_from_text_similarity():
    projection = project_frames(extract("Bên B phải thanh toán theo phụ lục."))
    assert projection.timeline == ()
    assert "timeline_chain_not_supplied" in projection.review_reasons


def test_signing_date_never_becomes_effective_date():
    frames = extract("Bên B phải thanh toán 500 VND.")
    edge = TimelineEdge("e1", frames[0].frame_id, frames[0].frame_id, "AMENDS",
                        frames[0].evidence, date_role="SIGNING", date_value="2026-10-01")
    entry = project_frames(frames, timeline=(edge,)).timeline[0]
    assert entry.proposed_value is None
    assert entry.review_state == "NEEDS_REVIEW"
    assert "effective_date_missing" in entry.reasons


def test_reference_does_not_propose_amendment_value():
    frames = extract("Bên B phải thanh toán 500 VND.")
    edge = TimelineEdge("e1", frames[0].frame_id, frames[0].frame_id, "REFERENCES", frames[0].evidence)
    assert project_frames(frames, timeline=(edge,)).timeline[0].proposed_value is None


def test_missing_target_remains_visible():
    frames = extract("Bên B phải thanh toán.")
    edge = TimelineEdge("e1", frames[0].frame_id, None, "AMENDS", frames[0].evidence)
    projection = project_frames(frames, timeline=(edge,))
    assert "missing_target" in projection.timeline[0].reasons
    assert projection.timeline[0].review_state == "NEEDS_REVIEW"


def test_cycle_is_flagged_and_never_selects_winner():
    frames = extract("Bên B phải thanh toán; Bên A phải giao hàng.")
    a, b = frames
    edges = (TimelineEdge("e1", a.frame_id, b.frame_id, "AMENDS", a.evidence),
             TimelineEdge("e2", b.frame_id, a.frame_id, "AMENDS", b.evidence))
    entries = project_frames(frames, timeline=edges).timeline
    assert all("cycle" in entry.reasons for entry in entries)
    assert all(entry.proposed_value is None for entry in entries)


def test_timeline_evidence_outside_frame_snapshot_is_rejected():
    frames = extract("Bên B phải thanh toán.")
    edge = TimelineEdge("e1", frames[0].frame_id, None, "AMENDS",
                        (replace(frames[0].evidence[0], snapshot_id="other"),))
    with pytest.raises(ValueError, match="scope"):
        project_frames(frames, timeline=(edge,))

@pytest.mark.parametrize("profile,key", [
    ("SALES", "unit_price"), ("SUPPLY_SERVICE", "sla"),
    ("LEASE", "rent"), ("CONSTRUCTION_WORK", "schedule"),
    ("EMPLOYMENT", "salary"), ("NDA", "confidentiality_term"),
])
def test_explicit_parameter_routes_with_profile_without_invented_actor(profile, key):
    from app.contracts.contract_profiles import get_contract_profile
    field = next(field for field in get_contract_profile(profile).fields if field.key == key)
    frame = extract_frames(Evidence("doc", "s1", "p1/n1", f"{field.key}: 500 VND"),
                           profile=profile, dossier_id="d1")[0]
    assert frame.family == "PARAMETER"
    assert frame.get("parameter").value == key
    assert frame.get("actor").state == "UNKNOWN"


def test_definition_preserves_literal_term_and_value():
    frame = extract('"Ngày làm việc" nghĩa là ngày từ thứ hai đến thứ sáu.')[0]
    assert frame.family == "DEFINITION"
    assert frame.get("parameter").value == "Ngày làm việc"
    assert frame.get("definition").value == "ngày từ thứ hai đến thứ sáu."


def test_unmapped_colon_key_does_not_become_grounded_parameter():
    frame = extract("unknown_field: 500 VND")[0]
    assert frame.get("parameter").state == "UNKNOWN"

@pytest.mark.parametrize("text,unit", [
    ("Bên B phải thanh toán trong 5 ngày làm việc.", "business-day"),
    ("Bên B phải thanh toán trong 5 ngày.", "day"),
])
def test_explicit_deadline_preserves_unit_without_calendar_conversion(text, unit):
    frame = extract(text)[0]
    assert frame.get("deadline").value == "5"
    assert frame.get("deadline_unit").value == unit
    assert frame.get("unit").state == "UNKNOWN"
    assert frame.get("temporal_trigger").state == "UNKNOWN"


def test_condition_and_exception_are_retained_as_raw_spans():
    frame = extract("Bên B phải thanh toán nếu nghiệm thu, trừ khi có tranh chấp.")[0]
    assert frame.get("condition").value == "nghiệm thu"
    assert frame.get("exception").value == "có tranh chấp."


def test_same_snapshot_item_candidate_does_not_invent_relation():
    from app.pipeline.clause_keys import build_candidates
    frames = extract("Bên B phải thanh toán; Bên A phải giao hàng.")
    pairs = build_candidates(frames, same_item=((frames[0].frame_id, frames[1].frame_id),))
    assert pairs[0].sources == ("SAME_ITEM_RELATION_UNCONFIRMED",)

def test_explicit_accepted_amendment_proposes_only_review_value():
    from app.contracts.clause_frames import Slot
    frames = extract("Bên B phải thanh toán 500 VND; Bên B phải thanh toán 600 VND")
    newer, older = frames
    accepted = Slot("ACCEPTED", "GROUNDED",
                    (Evidence("doc", "s1", "acceptance", "C\u00e1c b\u00ean \u0111\u1ed3ng \u00fd s\u1eeda \u0111\u1ed5i gi\u00e1 tr\u1ecb."),))
    edge = TimelineEdge("e", newer.frame_id, older.frame_id, "AMENDS", newer.evidence,
                        date_role="EFFECTIVE", date_value="2026-10-01",
                        acceptance=accepted, value_slot="amount")
    entry = project_frames(frames, timeline=(edge,)).timeline[0]
    assert entry.proposed_value == newer.get("amount")
    assert entry.review_state == "NEEDS_REVIEW"
    assert "proposed_only_no_legal_winner" in entry.reasons


def test_concurrent_amendments_do_not_propose_winner():
    from app.contracts.clause_frames import Slot
    frames = extract("Bên B phải thanh toán 500 VND; Bên B phải thanh toán 600 VND; Bên B phải thanh toán 700 VND")
    a, b, target = frames
    edges = tuple(TimelineEdge(str(i), f.frame_id, target.frame_id, "AMENDS", f.evidence,
                  date_role="EFFECTIVE", date_value="2026-10-01",
                  acceptance=Slot("ACCEPTED", "GROUNDED", f.evidence), value_slot="amount")
                  for i, f in enumerate((a, b)))
    entries = project_frames(frames, timeline=edges).timeline
    assert all(entry.proposed_value is None and "concurrent_amendments" in entry.reasons for entry in entries)

def test_remedy_requires_explicit_breach_qualifier():
    from app.pipeline.clause_keys import normalize_key
    frame = extract("Bên B phải bồi thường 5% nếu vi phạm hợp đồng.")[0]
    assert frame.family == "REMEDY"
    assert frame.get("amount").value == 5
    assert frame.get("unit").value == "percent"
    assert frame.get("base").state == "UNKNOWN"
    assert normalize_key(frame).key == ("B", "COMPENSATE", "BREACH")


def test_remedy_does_not_default_to_breach_when_unspecified():
    from app.pipeline.clause_keys import normalize_key
    frame = extract("Bên B phải bồi thường 500 VND.")[0]
    assert frame.family == "REMEDY"
    assert normalize_key(frame).certainty == "UNKNOWN"

def test_acceptance_label_without_acceptance_span_cannot_propose_value():
    from app.contracts.clause_frames import Slot
    frames = extract("Bên B phải thanh toán 500 VND; Bên B phải thanh toán 600 VND")
    newer, older = frames
    edge = TimelineEdge("e", newer.frame_id, older.frame_id, "AMENDS", newer.evidence,
                        date_role="EFFECTIVE", date_value="2026-10-01",
                        acceptance=Slot("ACCEPTED", "GROUNDED", newer.evidence), value_slot="amount")
    entry = project_frames(frames, timeline=(edge,)).timeline[0]
    assert entry.proposed_value is None
    assert "acceptance_evidence_not_assessed" in entry.reasons

def test_negated_permission_never_becomes_positive_right():
    frame = extract("Bên B không được phép thanh toán cho bên A.")[0]
    assert frame.family == "PROHIBITION"
    assert frame.get("modality_negation").value == "PROHIBITED"


def test_qualified_permission_not_assumed_positive():
    frame = extract("Bên B chưa được phép thanh toán.")[0]
    assert frame.get("modality_negation").state == "UNKNOWN"
