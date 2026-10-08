"""P4 projection: contract-graph edges leave AI2 as ``AMENDS`` context findings (K3, D5) and
as one ``coverage.contract_graph`` key (D6); the legacy annex ``AMENDMENT_SIGNAL`` is replaced
only when the builder ran (Q3, RT-07)."""

from __future__ import annotations

import json
import re
import uuid
from contextlib import ExitStack
from unittest import mock

import pytest

from app.contracts.contract_graph import ContractEdge, ContractGraphResult, EdgeOp
from app.contracts.models import (
    Candidate,
    Disposition,
    FindingType,
    ModelDisposition,
    RelationType,
    ReviewState,
)
from app.pipeline import idp
from app.pipeline.contract_context import build_contract_context
from app.pipeline.contract_graph import builder
from app.pipeline.contract_graph.builder import build_contract_graph
from app.pipeline.contract_graph.projection import (
    deduped_with_legacy,
    edge_findings,
    graph_coverage,
)
from fixtures import envelope
from fixtures.contract_graph_records import graph_record

FLAG = "AI2_CONTRACT_GRAPH_ENABLED"
SUBTYPES = re.compile(r"INSERTION|SUBSTITUTION|REPEAL|REJECTION|SCOPE_LIMIT")
UUID_SOURCES = ("app.pipeline.idp.uuid4", "app.pipeline.clause.uuid4", "app.pipeline.compare.uuid4")


@pytest.fixture(scope="module")
def graph() -> ContractGraphResult:
    record = graph_record()
    return build_contract_graph(record, record.facts)


def _edge(graph: ContractGraphResult, source: str) -> ContractEdge:
    return next(e for e in graph.edges if e.source_node_id == source)


def _candidate(left: str, right: str, disposition: Disposition, cid: str = "cand_x") -> Candidate:
    def cite(node_id: str):
        from app.contracts.models import Citation

        return Citation(node_id=node_id, page_revision_id="p", text_span="x")

    return Candidate(
        candidate_id=cid,
        left_id=f"fact-{left}",
        right_id=f"fact-{right}",
        finding_type=FindingType.DIVERGENCE,
        model_disposition=ModelDisposition.INCOMPLETE,
        review_state=ReviewState.NEEDS_REVIEW,
        evidence_left=[cite(left)],
        evidence_right=[cite(right)],
        disposition=disposition,
    )


def _run(record, monkeypatch, *, enabled: bool = True):
    if enabled:
        monkeypatch.setenv(FLAG, "1")
    else:
        monkeypatch.delenv(FLAG, raising=False)
    counter = iter(range(1, 1 << 30))
    with ExitStack() as stack:
        for target in UUID_SOURCES:
            stack.enter_context(mock.patch(target, lambda: uuid.UUID(int=next(counter))))
        return idp.run_idp(record, envelope(), job_id="job_cg")


def test_every_op_projects_to_amends(graph):
    base = _edge(graph, "a1")
    edges = [
        base.model_copy(update={"op": op, "edge_id": f"cedge:{op.value.lower()}"}) for op in EdgeOp
    ]

    findings = edge_findings(edges, [])

    assert len(findings) == len(EdgeOp)
    for finding, edge in zip(findings, edges):
        assert finding.relation_type == RelationType.AMENDS
        assert finding.kind == "AMENDMENT_SIGNAL"
        assert finding.finding_id == "contract-graph:" + edge.edge_id
        assert finding.subject_key == edge.target_address
        assert finding.source_node_ids == [edge.source_node_id, edge.target_node_id]
    assert len({f.reason for f in findings}) == len({e.target_address for e in edges})


def test_findings_carry_no_subtype_strings(graph):
    edges = [
        _edge(graph, "a1").model_copy(update={"op": op, "edge_id": f"cedge:{i}"})
        for i, op in enumerate(EdgeOp)
    ]

    for finding in edge_findings(edges, []):
        dumped = json.dumps(finding.model_dump(mode="json"), ensure_ascii=False)
        assert not SUBTYPES.search(dumped), dumped
        assert finding.metadata == {}


def test_findings_keep_two_sided_citations_and_review_state(graph):
    edge = _edge(graph, "a1").model_copy(update={"review_state": ReviewState.INSUFFICIENT_EVIDENCE})

    (finding,) = edge_findings([edge], [])

    assert finding.citations == [edge.source_citation, edge.target_citation]
    assert {c.source_file_id for c in finding.citations} == {"f-annex", "f-body"}
    assert finding.review_state == ReviewState.INSUFFICIENT_EVIDENCE


def test_edge_duplicating_legacy_candidate_amendment_is_not_projected(graph):
    edge = _edge(graph, "a7")  # a7 -> b_d5k2, the fact pair compare.py unlocks
    legacy = _candidate("b_d5k2", "a7", Disposition.CANDIDATE_AMENDMENT)

    findings = edge_findings([edge, _edge(graph, "a1")], [legacy])

    assert [f.finding_id for f in findings] == ["contract-graph:" + _edge(graph, "a1").edge_id]
    assert deduped_with_legacy([edge, _edge(graph, "a1")], [legacy]) == 1
    coverage = graph_coverage(graph, deduped_with_legacy=1)
    assert coverage["deduped_with_legacy"] == 1


def test_edge_with_non_amendment_candidate_carries_candidate_id(graph):
    # RT-07 / D5: BE drops a context finding with ``metadata.candidate_id``, so the pair the edge
    # unlocked keeps one review row (the candidate), not two.
    edge = _edge(graph, "a7")
    other = _candidate("b_d5k2", "a7", Disposition.COMPARABLE_DIFFERENCE, cid="cand_first")
    later = _candidate("a7", "b_d5k2", Disposition.COMPARABLE_DIFFERENCE, cid="cand_later")
    unrelated = _candidate("b_d3k1c", "a9", Disposition.CANDIDATE_AMENDMENT, cid="cand_other")

    (finding,) = edge_findings([edge], [unrelated, other, later])

    assert finding.metadata == {"candidate_id": "cand_first"}
    assert deduped_with_legacy([edge], [unrelated, other, later]) == 0


def test_flag_on_suppresses_legacy_amendment_signal(monkeypatch):
    result = _run(graph_record(), monkeypatch)
    findings = result.contribution.contract_context.findings

    legacy = [
        f
        for f in findings
        if f.kind == "AMENDMENT_SIGNAL" and not f.finding_id.startswith("contract-graph:")
    ]
    assert legacy == []
    assert any(f.finding_id.startswith("contract-graph:") for f in findings)
    # direct switch on the builder; default keeps the old path
    record = graph_record()
    kinds = [f.kind for f in build_contract_context(record, facts=record.facts).findings]
    assert "AMENDMENT_SIGNAL" in kinds
    suppressed = build_contract_context(record, facts=record.facts, suppress_amendment_signal=True)
    assert "AMENDMENT_SIGNAL" not in [f.kind for f in suppressed.findings]


def test_flag_on_builder_failure_keeps_legacy_amendment_signal(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("synthetic builder failure")

    monkeypatch.setattr(builder, "build_contract_graph", boom)
    result = _run(graph_record(), monkeypatch)
    findings = result.contribution.contract_context.findings

    legacy = [f for f in findings if f.kind == "AMENDMENT_SIGNAL"]
    assert legacy and not any(f.finding_id.startswith("contract-graph:") for f in findings)


def test_flag_on_run_idp_dedupes_unlocked_pair_against_legacy_candidate(monkeypatch):
    result = _run(graph_record(), monkeypatch)
    contribution = result.contribution
    graph_ids = {
        f.source_node_ids[0]
        for f in contribution.contract_context.findings
        if f.finding_id.startswith("contract-graph:")
    }

    assert "a7" not in graph_ids  # (a7, b_d5k2) already is a CANDIDATE_AMENDMENT finding
    assert {"a1", "a2", "a3", "a9"} <= graph_ids
    assert contribution.coverage["contract_graph"]["deduped_with_legacy"] == 1


def test_coverage_counts_every_op_including_zero(graph):
    coverage = graph_coverage(graph)

    assert coverage["graph_mode"] == "operation_first"
    assert coverage["status"] == "OK"
    assert coverage["edges_total"] == len(graph.edges)
    assert list(coverage["edges_by_op"]) == [op.value for op in EdgeOp]
    assert coverage["edges_by_op"]["REPEAL"] == 0
    assert sum(coverage["edges_by_op"].values()) == len(graph.edges)
    assert coverage["edges_by_op"]["SUBSTITUTION"] == sum(
        e.op == EdgeOp.SUBSTITUTION for e in graph.edges
    )
    assert coverage["unresolved_targets"] == graph.stats["unresolved_targets"] == 1
    assert coverage["ambiguous_targets"] == graph.stats["ambiguous_targets"]
    assert coverage["implicit_edges"] == graph.stats["implicit_edges"]
    assert coverage["truncated"] == 0
    assert coverage["auto_pass_enabled"] is False
    assert coverage["deduped_with_legacy"] == 0
    json.dumps(coverage)  # wire-serializable as is


def test_coverage_failed_status_has_zero_counts():
    coverage = graph_coverage(None, failed=True)

    assert coverage["status"] == "FAILED"
    assert coverage["edges_total"] == 0
    assert coverage["edges_by_op"] == {op.value: 0 for op in EdgeOp}
    for key in ("unresolved_targets", "ambiguous_targets", "implicit_edges", "truncated"):
        assert coverage[key] == 0
    assert coverage["deduped_with_legacy"] == 0
