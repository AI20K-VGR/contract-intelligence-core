from __future__ import annotations

from dataclasses import replace

from app.contracts.clause_frames import Slot
from app.pipeline.semantic_proposal_validation import (
    validate_proposal,
    validate_proposal_response,
)
from app.pipeline.tenant_aliases import ApprovedAlias, ApprovedAliasSnapshot
from test_semantic_v2_alignment import make_frame


def _unknown_action(frame):
    slots = dict(frame.slots)
    slots["action"] = Slot(None, "UNKNOWN", frame.evidence, "unparsed_action")
    return replace(frame, slots=tuple(slots.items()))


def test_grounded_slot_proposal_requires_matching_source_frame():
    frame = make_frame("frame")
    source = make_frame("source", document="annex", amount="30")

    result = validate_proposal(
        {"slot": "amount", "node_id": "source", "value": "30"},
        frame=frame,
        candidate_frames=(source,),
        source_frame=source,
        citation_valid=True,
    )

    assert result.accepted and result.slot.value == source.get("amount").value


def test_invented_modality_is_rejected_even_when_shape_is_valid():
    frame = make_frame("frame")
    source = make_frame("source", document="annex")

    result = validate_proposal(
        {"slot": "modality_negation", "node_id": "source", "value": "MAYBE"},
        frame=frame,
        candidate_frames=(source,),
        source_frame=source,
        citation_valid=True,
    )

    assert not result.accepted and result.code == "PROPOSAL_SYMBOL_NOT_ALLOWED"


def test_unknown_action_needs_closed_or_approved_source_alias():
    frame = _unknown_action(make_frame("frame"))
    source = _unknown_action(make_frame("source", document="annex"))

    rejected = validate_proposal(
        {"slot": "action", "node_id": "source", "value": "PAY"},
        frame=frame,
        candidate_frames=(source,),
        source_frame=source,
        citation_valid=True,
    )
    assert not rejected.accepted and rejected.code == "PROPOSAL_SOURCE_NOT_GROUNDED"

    alias = ApprovedAliasSnapshot(
        "tenant-a", 2, (ApprovedAlias("trả tiền", "PAY", "action", "proposal-1"),)
    )
    source_evidence = replace(source.evidence[0], raw="Bên A phải trả tiền")
    source = replace(source, evidence=(source_evidence,))
    accepted = validate_proposal(
        {"slot": "action", "node_id": "source", "value": "PAY"},
        frame=frame,
        candidate_frames=(source,),
        source_frame=source,
        citation_valid=True,
        aliases=alias,
        tenant_id="tenant-a",
        alias_version=2,
    )
    assert accepted.accepted and accepted.slot.value == "PAY"


def test_unapproved_alias_version_is_rejected():
    frame = _unknown_action(make_frame("frame"))
    source = _unknown_action(make_frame("source", document="annex"))
    aliases = ApprovedAliasSnapshot(
        "tenant-a", 2, (ApprovedAlias("trả tiền", "PAY", "action", "proposal-1"),)
    )

    result = validate_proposal(
        {"slot": "action", "node_id": "source", "value": "PAY"},
        frame=frame,
        candidate_frames=(source,),
        source_frame=replace(source, evidence=(replace(source.evidence[0], raw="Bên A phải trả tiền"),)),
        citation_valid=True,
        aliases=aliases,
        tenant_id="tenant-a",
        alias_version=1,
    )

    assert not result.accepted and result.code == "PROPOSAL_SOURCE_NOT_GROUNDED"


def test_invalid_or_refused_provider_payload_stays_reviewable():
    assert validate_proposal_response(None, max_slots=3).code == "PROPOSAL_PROVIDER_EMPTY"
    assert validate_proposal_response({"slots": "refused"}, max_slots=3).code == "PROPOSAL_SHAPE_INVALID"
    assert validate_proposal_response({"slots": []}, max_slots=3).accepted
