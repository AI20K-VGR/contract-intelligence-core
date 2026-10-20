"""Validation for bounded semantic enrichment proposals.

The provider is allowed to suggest a missing slot, but it is never allowed to
create a symbol or evidence record.  This module keeps that boundary small and
deterministic so the same checks are usable by the online enrichment path and
by offline tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.clause_frames import SLOT_NAMES, ClauseFrame, Slot
from app.pipeline.clause_keys import ACTION_SYMBOLS, QUALIFIER_SYMBOLS
from app.pipeline.tenant_aliases import ApprovedAliasSnapshot, normalized_source

_MODALITY_SYMBOLS = frozenset({"REQUIRED", "PERMITTED", "PROHIBITED", "FACTUAL"})
_SYMBOL_SLOTS = {
    "action": ACTION_SYMBOLS,
    "qualifier": QUALIFIER_SYMBOLS,
    "modality_negation": _MODALITY_SYMBOLS,
}
_SHARED_ANCHORS = ("actor", "action", "modality_negation")


@dataclass(frozen=True, slots=True)
class ProposalValidation:
    """Stable, reviewable result for one provider proposal."""

    accepted: bool
    code: str
    slot: Slot | None = None


def _invalid(code: str) -> ProposalValidation:
    return ProposalValidation(False, code)


def _shape(proposal: Any) -> bool:
    return (
        isinstance(proposal, dict)
        and set(proposal) == {"slot", "node_id", "value"}
        and all(isinstance(proposal.get(key), str) and proposal[key].strip()
                for key in ("slot", "node_id", "value"))
    )


def validate_proposal_response(response: Any, *, max_slots: int) -> ProposalValidation:
    """Validate the provider envelope before inspecting individual slots."""

    if response is None:
        return _invalid("PROPOSAL_PROVIDER_EMPTY")
    if not isinstance(response, dict) or set(response) != {"slots"}:
        return _invalid("PROPOSAL_SHAPE_INVALID")
    proposals = response["slots"]
    if not isinstance(proposals, list) or len(proposals) > max_slots:
        return _invalid("PROPOSAL_SHAPE_INVALID")
    if any(not _shape(proposal) for proposal in proposals):
        return _invalid("PROPOSAL_SHAPE_INVALID")
    # An empty response is a valid refusal: it contributes no grounded data.
    return ProposalValidation(True, "PROPOSAL_EMPTY" if not proposals else "PROPOSAL_ENVELOPE_VALID")


def _value_equal(left: object, right: object) -> bool:
    return str(left) == str(right)


def _source_matches(frame: ClauseFrame, node_id: str) -> bool:
    """Accept a structural node id while retaining test/frame-id compatibility."""

    if frame.frame_id == node_id:
        return True
    source_ref = frame.evidence[0].source_ref if frame.evidence else ""
    return source_ref.split("#span", 1)[0] == node_id


def _shared_context_matches(frame: ClauseFrame, candidate: ClauseFrame, *, excluded: str) -> bool:
    """Require grounded common anchors while allowing the proposed slot itself unknown."""

    for name in _SHARED_ANCHORS:
        if name == excluded:
            continue
        left, right = frame.get(name), candidate.get(name)
        if left is None or right is None:
            return False
        if left.state != "GROUNDED" or right.state != "GROUNDED":
            return False
        if not _value_equal(left.value, right.value):
            return False
    return True


def _approved_alias_slot(
    proposal: dict[str, str],
    *,
    source_frame: ClauseFrame,
    aliases: ApprovedAliasSnapshot | None,
    tenant_id: str | None,
    alias_version: int | None,
) -> Slot | None:
    if proposal["slot"] not in {"action", "qualifier"} or aliases is None:
        return None
    # The snapshot and requested tenant/version are part of the trust boundary.
    if tenant_id != aliases.tenant_id or alias_version != aliases.version:
        return None
    for alias in aliases.aliases:
        if alias.kind != proposal["slot"] or alias.symbol != proposal["value"]:
            continue
        phrase = normalized_source(alias.source)
        text = " ".join(evidence.raw for evidence in source_frame.evidence)
        if phrase not in normalized_source(text):
            continue
        return Slot(
            proposal["value"],
            "GROUNDED",
            source_frame.evidence,
            "approved_tenant_alias",
        )
    return None


def validate_proposal(
    proposal: Any,
    *,
    frame: ClauseFrame,
    candidate_frames: tuple[ClauseFrame, ...],
    source_frame: ClauseFrame | None,
    citation_valid: bool,
    aliases: ApprovedAliasSnapshot | None = None,
    tenant_id: str | None = None,
    alias_version: int | None = None,
) -> ProposalValidation:
    """Accept a proposal only when a checked source frame proves the value.

    The provider value is compared as text because wire JSON has no Decimal
    type.  The returned ``Slot`` always comes from a source frame (or an
    approved alias backed by that frame); no provider text becomes evidence.
    """

    if not _shape(proposal):
        return _invalid("PROPOSAL_SHAPE_INVALID")
    name = proposal["slot"]
    if name not in SLOT_NAMES or frame.get(name) is None:
        return _invalid("PROPOSAL_SLOT_UNSUPPORTED")
    target = frame.get(name)
    if target is None or target.state not in {"UNKNOWN", "GROUNDED"}:
        return _invalid("PROPOSAL_SLOT_NOT_UNKNOWN")
    allowed = _SYMBOL_SLOTS.get(name)
    if allowed is not None and proposal["value"] not in allowed:
        # Alias resolution is checked below; an arbitrary provider symbol is
        # never accepted merely because the JSON shape is valid.
        if not any(
            alias.kind == name and alias.symbol == proposal["value"]
            for alias in (aliases.aliases if aliases else ())
        ):
            return _invalid("PROPOSAL_SYMBOL_NOT_ALLOWED")
    if source_frame is None or not _source_matches(source_frame, proposal["node_id"]):
        return _invalid("PROPOSAL_SOURCE_NOT_GROUNDED")
    if not source_frame.evidence:
        return _invalid("PROPOSAL_SOURCE_NOT_GROUNDED")
    if not citation_valid:
        return _invalid("PROPOSAL_CITATION_INVALID")

    # Approved aliases are a tenant/versioned exception to closed symbols.  A
    # phrase must still occur in the cited source span.
    alias_slot = _approved_alias_slot(
        proposal,
        source_frame=source_frame,
        aliases=aliases,
        tenant_id=tenant_id,
        alias_version=alias_version,
    )
    if alias_slot is not None:
        if not _shared_context_matches(frame, source_frame, excluded=name):
            return _invalid("PROPOSAL_SOURCE_NOT_GROUNDED")
        return ProposalValidation(True, "PROPOSAL_APPROVED_ALIAS", alias_slot)

    matches: list[Slot] = []
    for candidate in candidate_frames:
        if not _source_matches(candidate, proposal["node_id"]):
            continue
        if candidate.family != frame.family:
            continue
        if not _shared_context_matches(frame, candidate, excluded=name):
            continue
        proposed = candidate.get(name)
        if proposed is None or proposed.state != "GROUNDED":
            continue
        if not _value_equal(proposed.value, proposal["value"]):
            continue
        if any(not evidence.raw.strip() for evidence in proposed.evidence):
            continue
        matches.append(proposed)

    if len(matches) != 1:
        # A valid closed symbol still needs a grounded source.  This is kept
        # distinct from a provider shape error so the UI can request review.
        return _invalid("PROPOSAL_SOURCE_NOT_GROUNDED")
    return ProposalValidation(True, "PROPOSAL_GROUNDED", matches[0])
