from contract_intelligence.shared.ai.persistence import _semantic_finding_disposition
from contract_intelligence.shared.ai.schemas import SemanticFrame, SemanticPair, SemanticSlot

EVIDENCE = {
    "document_id": "doc-1",
    "snapshot_id": "snap-1",
    "source_ref": "node-1",
    "raw": "payment 30% within 7 business days",
    "citation": {
        "node_id": "node-1",
        "page_revision_id": "page-1",
        "text_span": "payment 30% within 7 business days",
        "source_file_id": "doc-1",
        "validation_status": "VALID",
    },
}


def test_v2_frame_keeps_deadline_unit_and_pair_diagnostics():
    evidence = EVIDENCE
    slots = {
        "deadline_unit": SemanticSlot(
            value_type="TEXT",
            value="business-day",
            state="GROUNDED",
            evidence=[evidence],
            reason="",
        ),
    }
    frame = SemanticFrame(
        frame_id="frame-1",
        family="OBLIGATION",
        profile="SALES",
        document_id="doc-1",
        snapshot_id="snap-1",
        dossier_id="dos-1",
        evidence=[evidence],
        slots=slots,
        key={
            "key": ["PAY"],
            "certainty": "DEFINITE",
            "reason": "",
            "method": "CLOSED_SYMBOL",
            "alias_digest": None,
            "alias_version": None,
            "alias_proposal_ids": [],
        },
    )
    pair = SemanticPair(
        pair_id="pair-1",
        left_id=frame.frame_id,
        right_id="frame-2",
        disposition="CONFLICT_CANDIDATE",
        reason="different amount",
        left_evidence=[evidence],
        right_evidence=[evidence],
        method="CLOSED_SYMBOL",
        candidate_sources=["deterministic"],
        alignment_key=["PAY", "scope:shipping"],
        conflict_kind="SEMANTIC_CONFLICT",
        slots_in_difference=["amount"],
    )
    assert frame.slots["deadline_unit"].value == "business-day"
    assert pair.alignment_key == ["PAY", "scope:shipping"]


def test_v2_pair_dispositions_remain_separate_in_finding_read_model():
    assert (
        _semantic_finding_disposition(
            SemanticPair(
                pair_id="p-conflict",
                left_id="left",
                right_id="right",
                disposition="CONFLICT_CANDIDATE",
                reason="opposite modality",
                left_evidence=[EVIDENCE],
                right_evidence=[EVIDENCE],
                method="CLOSED_SYMBOL",
                candidate_sources=["SEMANTIC_ALIGNMENT"],
            )
        )
        == "conflict_candidate"
    )
    assert (
        _semantic_finding_disposition(
            SemanticPair(
                pair_id="p-arithmetic",
                left_id="left",
                right_id="right",
                disposition="COMPARABLE_DIFFERENCE",
                reason="table total differs",
                left_evidence=[EVIDENCE],
                right_evidence=[EVIDENCE],
                method="CLOSED_SYMBOL",
                candidate_sources=["TYPED_TABLE"],
                conflict_kind="ARITHMETIC_INCONSISTENCY",
            )
        )
        == "arithmetic_inconsistency"
    )
    assert (
        _semantic_finding_disposition(
            SemanticPair(
                pair_id="p-amend",
                left_id="left",
                right_id="right",
                disposition="COMPARABLE_DIFFERENCE",
                reason="amendment chain",
                left_evidence=[EVIDENCE],
                right_evidence=[EVIDENCE],
                method="CLOSED_SYMBOL",
                candidate_sources=["EXPLICIT_REF"],
                conflict_kind="AMENDMENT_REVIEW",
            )
        )
        == "amendment_review"
    )
