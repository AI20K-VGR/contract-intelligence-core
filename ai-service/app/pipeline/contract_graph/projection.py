"""Project contract-graph edges onto the existing Backend contract (P4; K3, D5, D6).

Every edge leaves AI2 as a ``ContextFinding(kind="AMENDMENT_SIGNAL", relation_type=AMENDS)``;
the operation sub-type never appears in a finding (``reason`` is one sentence for all ops,
``metadata`` is ``{}`` or a ``candidate_id``). Graph numbers go to exactly one coverage key.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.contracts.contract_graph import ContractEdge, ContractGraphResult, EdgeOp
from app.contracts.models import Candidate, ContextFinding, Disposition, RelationType
from app.pipeline.contract_graph.review_policy import auto_pass_enabled

FINDING_PREFIX = "contract-graph:"
GRAPH_MODE = "operation_first"
_REASON = "AI2 phát hiện quan hệ sửa đổi tới {address}; cần người duyệt đối chiếu hai phía."


def _pair(left: str, right: str) -> tuple[str, str]:
    # same key ``compare.py`` uses to unlock a cross-file fact pair
    return tuple(sorted((str(left), str(right))))  # type: ignore[return-value]


def _candidate_pair(candidate: Candidate) -> tuple[str, str] | None:
    if not candidate.evidence_left or not candidate.evidence_right:
        return None
    return _pair(candidate.evidence_left[0].node_id, candidate.evidence_right[0].node_id)


def _legacy_amendment_pairs(candidates: Iterable[Candidate]) -> set[tuple[str, str]]:
    return {
        pair
        for c in candidates
        if c.disposition == Disposition.CANDIDATE_AMENDMENT and (pair := _candidate_pair(c))
    }


def _is_legacy_duplicate(edge: ContractEdge, legacy: set[tuple[str, str]]) -> bool:
    return _pair(edge.source_node_id, edge.target_node_id) in legacy


def deduped_with_legacy(edges: Iterable[ContractEdge], candidates: Sequence[Candidate]) -> int:
    """Edges withheld from findings because a legacy ``CANDIDATE_AMENDMENT`` covers the pair."""

    legacy = _legacy_amendment_pairs(candidates)
    return sum(_is_legacy_duplicate(edge, legacy) for edge in edges)


def edge_findings(
    edges: Iterable[ContractEdge], candidates: Sequence[Candidate]
) -> list[ContextFinding]:
    """One ``AMENDS`` context finding per edge not already reviewed as a candidate amendment.

    RT-07: an edge on the node pair of a ``CANDIDATE_AMENDMENT`` candidate is skipped (one
    review row, not two). Any other candidate on the pair goes into ``metadata.candidate_id``
    (first in ``candidates`` order), which the Backend uses to drop the duplicate context row.
    """

    legacy = _legacy_amendment_pairs(candidates)
    first_candidate: dict[tuple[str, str], str] = {}
    for candidate in candidates:
        pair = _candidate_pair(candidate)
        if pair is not None:
            first_candidate.setdefault(pair, candidate.candidate_id)
    findings: list[ContextFinding] = []
    for edge in edges:
        if _is_legacy_duplicate(edge, legacy):
            continue
        candidate_id = first_candidate.get(_pair(edge.source_node_id, edge.target_node_id))
        findings.append(
            ContextFinding(
                finding_id=FINDING_PREFIX + edge.edge_id,
                kind="AMENDMENT_SIGNAL",
                relation_type=RelationType.AMENDS,
                subject_key=edge.target_address,
                source_node_ids=[edge.source_node_id, edge.target_node_id],
                reason=_REASON.format(address=edge.target_address),
                review_state=edge.review_state,
                citations=[edge.source_citation, edge.target_citation],
                metadata={"candidate_id": candidate_id} if candidate_id else {},
            )
        )
    return findings


def graph_coverage(
    result: ContractGraphResult | None, *, failed: bool = False, deduped_with_legacy: int = 0
) -> dict:
    """The single ``coverage["contract_graph"]`` value; a failed builder reports zero counts."""

    edges = [] if failed or result is None else result.edges
    stats = {} if failed or result is None else result.stats

    def count(key: str) -> int:
        value = stats.get(key, 0)
        return int(value) if isinstance(value, int) else 0

    return {
        "graph_mode": GRAPH_MODE,
        "status": "FAILED" if failed else "OK",
        "edges_total": len(edges),
        "edges_by_op": {op.value: sum(edge.op == op for edge in edges) for op in EdgeOp},
        "unresolved_targets": count("unresolved_targets"),
        "ambiguous_targets": count("ambiguous_targets"),
        "implicit_edges": count("implicit_edges"),
        "auto_pass_enabled": auto_pass_enabled(),
        "truncated": count("truncated"),
        "deduped_with_legacy": 0 if failed else int(deduped_with_legacy),
    }
