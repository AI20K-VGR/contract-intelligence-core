from __future__ import annotations

from app.contracts.clause_frames import Evidence, TimelineEdge
from app.pipeline.frame_extraction import extract_frames
from app.pipeline.frame_projections import project_frames
from app.reasoning.relations import _explicit_amend_reference


def test_entire_agreement_reference_is_not_an_amendment():
    assert not _explicit_amend_reference(
        "Các bên xác nhận toàn bộ Điều 1 đến Điều 18 là thỏa thuận", "5"
    )


def test_date_only_edge_never_suppresses_a_difference():
    frames = extract_frames(
        Evidence("doc", "s1", "node", "Bên A phải thanh toán 100 VND"),
        profile="SALES",
        dossier_id="dossier",
    )
    edge = TimelineEdge(
        "date-only", frames[0].frame_id, None, "AMENDS", frames[0].evidence,
        date_role="EFFECTIVE", date_value="2026-10-01",
    )

    entry = project_frames(frames, timeline=(edge,)).timeline[0]

    assert entry.proposed_value is None
    assert "missing_target" in entry.reasons
    assert entry.review_state == "NEEDS_REVIEW"


def test_explicit_amendment_without_acceptance_stays_unresolved():
    frames = extract_frames(
        Evidence("doc", "s1", "node", "Bên A phải thanh toán 100 VND"),
        profile="SALES",
        dossier_id="dossier",
    )
    edge = TimelineEdge(
        "no-acceptance", frames[0].frame_id, frames[0].frame_id, "AMENDS", frames[0].evidence,
        date_role="EFFECTIVE", date_value="2026-10-01", value_slot="amount",
    )

    entry = project_frames(frames, timeline=(edge,)).timeline[0]

    assert entry.proposed_value is None
    assert "acceptance_evidence_not_assessed" in entry.reasons
