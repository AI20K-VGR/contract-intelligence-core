"""Normalize explicit symbols only; profile routing never supplies missing slots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.pipeline.tenant_aliases import ApprovedAliasSnapshot

from app.contracts.clause_frames import ClauseFrame, ClauseKey
from app.contracts.contract_profiles import get_contract_profile

ACTION_SYMBOLS = frozenset({
    "PAY", "DELIVER", "ACCEPT", "NOTIFY", "TERMINATE", "COMPENSATE",
    "PENALTY", "DISCLOSE", "KEEP_CONFIDENTIAL", "RETURN", "REPAIR", "PERFORM",
})
QUALIFIER_SYMBOLS = frozenset({"BREACH", "DELAY", "NONPAYMENT", "DAMAGE", "CONFIDENTIALITY"})


def normalize_key(frame: ClauseFrame, *, aliases: ApprovedAliasSnapshot | None = None,
                  tenant_id: str | None = None, alias_version: int | None = None) -> ClauseKey:
    if frame.family in {"PARAMETER", "DEFINITION"} and frame.get("parameter") is not None:
        parameter = frame.get("parameter")
        if parameter.state != "GROUNDED" or not isinstance(parameter.value, str):
            return ClauseKey(None, "UNKNOWN", "missing_or_uncertain:parameter")
        if frame.family == "PARAMETER" and parameter.value not in {
            field.key for field in get_contract_profile(frame.profile).fields
        }:
            return ClauseKey(None, "UNKNOWN", "unmapped:parameter")
        return ClauseKey((frame.family, parameter.value), "DEFINITE", "explicit_parameter")
    names = ("actor", "action", "qualifier") if frame.family == "REMEDY" else ("actor", "action")
    values = []
    resolutions = []
    for name in names:
        slot = frame.get(name)
        if slot is None or slot.state != "GROUNDED" or not isinstance(slot.value, str):
            return ClauseKey(None, "UNKNOWN", f"missing_or_uncertain:{name}")
        if name == "actor" and slot.value in {"ANY_PARTY", "?", "UNRESOLVED"}:
            return ClauseKey(None, "UNKNOWN", "unresolved:actor")
        value = slot.value
        allowed = ACTION_SYMBOLS if name == "action" else QUALIFIER_SYMBOLS if name == "qualifier" else None
        if allowed is not None and value not in allowed:
            resolution = (aliases.resolve(tenant_id, alias_version, value, name)
                          if aliases is not None and tenant_id is not None and alias_version is not None else None)
            if resolution is None or resolution.symbol not in allowed:
                return ClauseKey(None, "UNKNOWN", f"unmapped:{name}")
            value = resolution.symbol
            resolutions.append(resolution)
        values.append(value)
    modality = frame.get("modality_negation")
    if frame.family != "REMEDY":
        if modality is None or modality.state != "GROUNDED":
            return ClauseKey(None, "UNKNOWN", "missing_or_uncertain:modality_negation")
        if modality.value not in {"REQUIRED", "PERMITTED", "PROHIBITED", "FACTUAL"}:
            return ClauseKey(None, "UNKNOWN", "unmapped:modality_negation")
        values.extend((frame.family, str(modality.value)))
    if resolutions:
        return ClauseKey(tuple(values), "DEFINITE", "grounded_approved_alias", "TENANT_ALIAS",
                         resolutions[0].digest, resolutions[0].version,
                         tuple(resolution.proposal_id for resolution in resolutions))
    return ClauseKey(tuple(values), "DEFINITE", "grounded_closed_symbols")


@dataclass(frozen=True, slots=True)
class KeyCandidate:
    left_id: str
    right_id: str
    sources: tuple[str, ...]


def build_candidates(frames: tuple[ClauseFrame, ...], *,
                     explicit_refs: tuple[tuple[str, str], ...] = (),
                     same_article: tuple[tuple[str, str], ...] = (),
                     same_item: tuple[tuple[str, str], ...] = (),
                     aliases: ApprovedAliasSnapshot | None = None, tenant_id: str | None = None,
                     alias_version: int | None = None) -> tuple[KeyCandidate, ...]:
    """Keep source reasons distinct; uncertain keys never create SAME_KEY pairs."""
    by_id = {frame.frame_id: frame for frame in frames}
    if len(by_id) != len(frames):
        raise ValueError("duplicate frame identity")
    candidates: dict[tuple[str, str], set[str]] = {}

    def add(left_id: str, right_id: str, source: str) -> None:
        if left_id not in by_id or right_id not in by_id or left_id == right_id:
            raise ValueError("invalid candidate target")
        if by_id[left_id].dossier_id != by_id[right_id].dossier_id:
            raise ValueError("cross-dossier candidate")
        identity = tuple(sorted((left_id, right_id)))
        candidates.setdefault(identity, set()).add(source)

    groups: dict[tuple, list[ClauseFrame]] = {}
    explicit_links = {
        tuple(sorted(pair))
        for pairs in (explicit_refs, same_article, same_item)
        for pair in pairs
    }
    for frame in frames:
        key = normalize_key(frame, aliases=aliases, tenant_id=tenant_id, alias_version=alias_version)
        if key.certainty == "DEFINITE":
            group = groups.setdefault((frame.dossier_id, frame.profile, key.key), [])
            for previous in group:
                identity = tuple(sorted((previous.frame_id, frame.frame_id)))
                if previous.document_id != frame.document_id or identity in explicit_links:
                    add(previous.frame_id, frame.frame_id, "SAME_KEY")
                elif _different_payment_milestones(previous, frame) and previous.document_id == frame.document_id:
                    continue
                else:
                    add(previous.frame_id, frame.frame_id, "SAME_KEY")
            group.append(frame)
    for source, refs in (("EXPLICIT_REF", explicit_refs), ("SAME_ARTICLE", same_article),
                         ("SAME_ITEM_RELATION_UNCONFIRMED", same_item)):
        for left_id, right_id in refs:
            add(left_id, right_id, source)

    # Candidate discovery uses an operation key separate from the full
    # identity key.  This is deliberately cross-document (or explicitly
    # related) so repeated clauses inside one structural node are not paired
    # merely because their polarity/value differs.
    from app.pipeline.semantic_alignment import alignment_key

    alignment_groups: dict[tuple, list[ClauseFrame]] = {}
    for frame in frames:
        key = alignment_key(frame, aliases=aliases, tenant_id=tenant_id, alias_version=alias_version)
        if key.key is None:
            continue
        group = alignment_groups.setdefault((frame.dossier_id, key.key), [])
        for previous in group:
            identity = tuple(sorted((previous.frame_id, frame.frame_id)))
            if previous.document_id != frame.document_id or identity in explicit_links:
                if "SAME_KEY" not in candidates.get(identity, set()):
                    add(previous.frame_id, frame.frame_id, "SEMANTIC_ALIGNMENT")
        group.append(frame)
    return tuple(KeyCandidate(left, right, tuple(sorted(sources)))
                 for (left, right), sources in sorted(candidates.items()))


def _different_payment_milestones(left: ClauseFrame, right: ClauseFrame) -> bool:
    if left.family != "OBLIGATION" or left.get("action") is None or right.get("action") is None:
        return False
    if left.get("action").value != "PAY" or right.get("action").value != "PAY":
        return False
    for name in ("amount", "deadline", "temporal_trigger"):
        a, b = left.get(name), right.get(name)
        if a is not None and b is not None and a.state == b.state == "GROUNDED" and a.value != b.value:
            return True
    return False
