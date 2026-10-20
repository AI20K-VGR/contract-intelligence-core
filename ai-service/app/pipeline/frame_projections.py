"""Three explicit projection collections; missing chains never become inferred edges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.pipeline.tenant_aliases import ApprovedAliasSnapshot

from app.contracts.clause_frames import ClauseFrame, FramePair, TimelineEdge, TimelineEntry
from app.contracts.contract_profiles import _fold
from app.pipeline.clause_keys import normalize_key


@dataclass(frozen=True, slots=True)
class FrameProjections:
    rows: tuple[ClauseFrame, ...]
    pairs: tuple[FramePair, ...]
    timeline: tuple[TimelineEntry, ...]
    review_reasons: tuple[str, ...]


def project_frames(frames: tuple[ClauseFrame, ...], *, pairs: tuple[FramePair, ...] = (),
                   timeline: tuple[TimelineEdge, ...] = (),
                   aliases: ApprovedAliasSnapshot | None = None, tenant_id: str | None = None,
                   alias_version: int | None = None) -> FrameProjections:
    if not all(isinstance(value, tuple) for value in (frames, pairs, timeline)):
        raise TypeError("immutable projection inputs required")
    identifiers = {frame.frame_id for frame in frames}
    if len(identifiers) != len(frames):
        raise ValueError("duplicate frame identity")
    if len({frame.dossier_id for frame in frames}) > 1:
        raise ValueError("cross-dossier projection")
    by_id = {frame.frame_id: frame for frame in frames}
    for pair in pairs:
        if pair.left_id not in identifiers or pair.right_id not in identifiers:
            raise ValueError("pair target missing")
        if (pair.left_evidence != by_id[pair.left_id].evidence
                or pair.right_evidence != by_id[pair.right_id].evidence):
            raise ValueError("pair evidence mismatch")
    reasons = [] if timeline else ["timeline_chain_not_supplied"]
    for frame in frames:
        key = normalize_key(frame, aliases=aliases, tenant_id=tenant_id, alias_version=alias_version)
        if key.certainty != "DEFINITE":
            reasons.append(f"{frame.frame_id}:{key.reason}")
        for name, slot in frame.slots:
            if slot.state in {"UNKNOWN", "UNSUPPORTED"}:
                reasons.append(f"{frame.frame_id}:unresolved_slot:{name}")
    entries = _timeline_entries(timeline, by_id)
    return FrameProjections(frames, pairs, entries, tuple(reasons))


def _timeline_entries(edges: tuple[TimelineEdge, ...], frames: dict[str, ClauseFrame]) -> tuple[TimelineEntry, ...]:
    if len({edge.edge_id for edge in edges}) != len(edges):
        raise ValueError("duplicate timeline edge")
    adjacency: dict[str, set[str]] = {}
    incoming: dict[str, int] = {}
    for edge in edges:
        if edge.source_id not in frames:
            raise ValueError("timeline source missing")
        allowed = {(frame.document_id, frame.snapshot_id)
                   for identifier in (edge.source_id, edge.target_id)
                   if (frame := frames.get(identifier)) is not None}
        evidence = (*edge.evidence, *(edge.acceptance.evidence if edge.acceptance else ()))
        if any((ev.document_id, ev.snapshot_id) not in allowed for ev in evidence):
            raise ValueError("timeline evidence scope mismatch")
        if edge.relation == "AMENDS" and edge.target_id in frames:
            adjacency.setdefault(edge.source_id, set()).add(edge.target_id)
            incoming[edge.target_id] = incoming.get(edge.target_id, 0) + 1

    def cycles(edge: TimelineEdge) -> bool:
        pending = [edge.target_id]
        visited = set()
        while pending:
            node = pending.pop()
            if node == edge.source_id:
                return True
            if node not in visited:
                visited.add(node)
                pending.extend(adjacency.get(node, ()))
        return False

    entries = []
    for edge in edges:
        reasons = []
        proposed_value = None
        if edge.target_id not in frames:
            reasons.append("missing_target")
        if edge.relation == "AMENDS":
            if edge.date_role != "EFFECTIVE" or edge.date_value is None:
                reasons.append("effective_date_missing")
            if cycles(edge):
                reasons.append("cycle")
            if incoming.get(edge.target_id, 0) > 1:
                reasons.append("concurrent_amendments")
            if (edge.acceptance is None or edge.acceptance.state != "GROUNDED"
                    or edge.acceptance.value != "ACCEPTED"
                    or not any(_fold(ev.raw).startswith("cac ben dong y sua doi ")
                               for ev in edge.acceptance.evidence)):
                reasons.append("acceptance_evidence_not_assessed")
            if not reasons and edge.value_slot:
                value = frames[edge.source_id].get(edge.value_slot)
                if value is not None and value.state == "GROUNDED":
                    proposed_value = value
                else:
                    reasons.append("proposed_value_not_grounded")
            if proposed_value is not None:
                reasons.append("proposed_only_no_legal_winner")
        entries.append(TimelineEntry(edge, tuple(reasons), proposed_value))
    return tuple(entries)
