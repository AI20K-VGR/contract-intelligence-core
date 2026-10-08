"""P3 flag ON: typed edges, issues and ``relation_pairs`` from ``run_idp`` (flag OFF is the golden)."""

from __future__ import annotations

import copy
import uuid
from contextlib import ExitStack
from unittest import mock

import pytest

from app.contracts.contract_graph import ContractGraphResult, EdgeMethod, EdgeOp
from app.contracts.models import Citation, JobStatus, RelationSupport, ReviewState
from app.pipeline import idp
from app.pipeline.contract_graph import builder
from app.pipeline.contract_graph.builder import build_contract_graph, contract_graph_enabled
from app.pipeline.outline import citation_for_node
from app.tools.persist import record_to_dict
from fixtures import envelope
from fixtures.contract_graph_records import Spec, dossier, graph_record, no_unlock_record

FLAG = "AI2_CONTRACT_GRAPH_ENABLED"
UUID_SOURCES = ("app.pipeline.idp.uuid4", "app.pipeline.clause.uuid4", "app.pipeline.compare.uuid4")


def _run(record, *, enabled: bool, monkeypatch):
    if enabled:
        monkeypatch.setenv(FLAG, "1")
    else:
        monkeypatch.delenv(FLAG, raising=False)
    counter = iter(range(1, 1 << 30))
    with ExitStack() as stack:
        for target in UUID_SOURCES:
            stack.enter_context(mock.patch(target, lambda: uuid.UUID(int=next(counter))))
        result = idp.run_idp(record, envelope(), job_id="job_cg")
    return result


def _edges(graph: ContractGraphResult) -> dict[str, list]:
    out: dict[str, list] = {}
    for edge in graph.edges:
        out.setdefault(edge.source_node_id, []).append(edge)
    return out


@pytest.fixture
def graph() -> ContractGraphResult:
    record = graph_record()
    return build_contract_graph(record, record.facts)


def test_flag_on_emits_typed_edges_with_two_sided_citations(graph):
    by_source = _edges(graph)

    (sub,) = by_source["a1"]
    assert (sub.op, sub.target_node_id, sub.target_address, sub.method, sub.standard) == (
        EdgeOp.SUBSTITUTION,
        "b_d3k1c",
        "diem c khoan 1 dieu 3",
        EdgeMethod.EXACT,
        True,
    )
    assert sub.new_text == "“c) Đợt 3 thanh toán 70% giá trị hợp đồng.”"
    (ins,) = by_source["a2"]
    assert (ins.op, ins.target_node_id, ins.target_address, ins.anchor_node_id) == (
        EdgeOp.INSERTION,
        "b_d7",
        "khoan 4 dieu 7",
        "b_d7k3",
    )
    (scope,) = by_source["a3"]
    assert (scope.op, scope.target_node_id, scope.scope_text) == (
        EdgeOp.SCOPE_LIMIT,
        "b_d5",
        "lô hàng 2",
    )
    for edge in graph.edges:
        assert edge.edge_id.startswith("cedge:") and len(edge.edge_id) == len("cedge:") + 24
        assert edge.source_citation.node_id == edge.source_node_id
        assert edge.target_citation.node_id == edge.target_node_id
        assert edge.source_citation.validation_status == "VALID"
        assert edge.target_citation.validation_status == "VALID"
        assert len(edge.source_citation.text_span) <= 240
        assert edge.support == RelationSupport.EXPLICIT_TEXT
        assert edge.source_snapshot_digest == "sha256:aaa"
    assert sub.source_citation.text_span == "Sửa đổi điểm c khoản 1 Điều 3 như sau:"


def test_flag_on_missing_target_is_insufficient_evidence_issue(graph, monkeypatch):
    assert "a4" not in _edges(graph)
    (issue,) = [i for i in graph.issues if i.citation and i.citation.node_id == "a4"]
    assert (issue.missing, issue.review_state) == (
        "TARGET_NOT_FOUND",
        ReviewState.INSUFFICIENT_EVIDENCE,
    )
    assert issue.issue_id.startswith("contract-graph:")

    result = _run(graph_record(), enabled=True, monkeypatch=monkeypatch)
    issues = result.contribution.evidence_issues
    assert issue.issue_id in [i.issue_id for i in issues]
    assert issues[-1].issue_id == graph.issues[-1].issue_id  # D4: appended after every old issue


def test_flag_on_excluded_sentences_emit_nothing(graph):
    by_source = _edges(graph)

    assert "a5" not in by_source and "a6" not in by_source
    assert not [i for i in graph.issues if i.citation and i.citation.node_id in {"a5", "a6"}]
    assert set(by_source) == {"a1", "a2", "a3", "a7", "a8", "a9", "a10", "a11"}


def test_flag_on_every_edge_needs_review_by_default(graph, monkeypatch):
    monkeypatch.delenv("AI2_CONTRACT_GRAPH_AUTO_PASS", raising=False)

    assert graph.edges
    assert {edge.review_state for edge in graph.edges} == {ReviewState.NEEDS_REVIEW}
    record = graph_record()
    forced = build_contract_graph(record, record.facts, auto_pass=True)
    assert {edge.review_state for edge in forced.edges} == {ReviewState.NEEDS_REVIEW}


def _pair(result, left: str, right: str) -> list:
    return [c for c in result.contribution.candidates if {c.left_id, c.right_id} == {left, right}]


def test_flag_on_relation_pairs_unlock_cross_file_candidate(monkeypatch):
    off = _run(graph_record(), enabled=False, monkeypatch=monkeypatch)
    on = _run(graph_record(), enabled=True, monkeypatch=monkeypatch)

    assert _pair(off, "fact-body-don-gia", "fact-annex-don-gia") == []
    assert any(i.missing == "BODY_ANNEX_RELATION" for i in off.contribution.evidence_issues)
    assert len(_pair(on, "fact-body-don-gia", "fact-annex-don-gia")) == 1
    assert not any(i.missing == "BODY_ANNEX_RELATION" for i in on.contribution.evidence_issues)


def _review_ids(record) -> tuple[list[str], list[str]]:
    ids = [item.review_item_id for item in record.review_items]
    issue_items = [i for i in ids if not i.startswith(("review:candidate:", "review:fact:"))]
    other = [i for i in ids if i.startswith(("review:candidate:", "review:fact:"))]
    return issue_items, other


def test_flag_on_keeps_existing_review_item_ids(monkeypatch):
    # RT-12: only on a dossier whose edges unlock no fact pair
    off_record, on_record = no_unlock_record(), no_unlock_record()
    off = _run(off_record, enabled=False, monkeypatch=monkeypatch)
    on = _run(on_record, enabled=True, monkeypatch=monkeypatch)

    def shape(result):
        return [
            (c.left_id, c.right_id, c.finding_type, c.review_state)
            for c in result.contribution.candidates
        ]

    def relation(result):
        return [
            i for i in result.contribution.evidence_issues if i.missing == "BODY_ANNEX_RELATION"
        ]

    assert shape(off) == shape(on)
    assert relation(off) == relation(on) and relation(off)
    graph = build_contract_graph(no_unlock_record(), no_unlock_record().facts)
    assert graph.edges and graph.issues
    off_issues, off_other = _review_ids(off_record)
    on_issues, on_other = _review_ids(on_record)
    # P4/Q3: flag on drops the legacy annex AMENDMENT_SIGNAL; every old issue before it keeps
    # its positional id, then come the per-edge context issues, then the graph issues (D4).
    off_missing = {i.issue_id: i.missing for i in off.contribution.evidence_issues}
    off_kinds = {i.review_item_id: i.kind for i in off_record.review_items}
    legacy = [
        k for k, rid in enumerate(off_issues)
        if off_missing.get(off_kinds[rid]) == "CONTRACT_CONTEXT_AMENDMENT_SIGNAL"
    ]
    assert legacy == [len(off_issues) - 1]  # on this dossier the legacy signal is the last old issue
    cut = legacy[0]
    assert on_issues[:cut] == off_issues[:cut]
    edge_finding_ids = [
        f.finding_id
        for f in on.contribution.contract_context.findings
        if f.finding_id.startswith("contract-graph:")
    ]
    assert edge_finding_ids
    added = [i for i in on_record.review_items if i.review_item_id in on_issues[cut:]]
    assert [i.kind for i in added] == [
        *(f"contract-context:{fid}" for fid in edge_finding_ids),
        *(issue.issue_id for issue in graph.issues),
    ]
    assert len(on_issues) == cut + len(edge_finding_ids) + len(graph.issues)
    assert on_other == off_other


def test_rejection_scope_limit_require_annex_or_operation_context():
    record = graph_record(body_rights=True)
    graph = build_contract_graph(record, record.facts)
    by_source = _edges(graph)

    assert "b_d8" not in by_source
    assert graph.stats["scope_rejection_out_of_context"] == 2
    assert [e.op for e in by_source["a3"]] == [EdgeOp.SCOPE_LIMIT]
    (rejection,) = by_source["a11"]
    assert (rejection.op, rejection.target_node_id, rejection.standard) == (
        EdgeOp.REJECTION,
        "b_d7k2",
        False,
    )


def test_operation_unit_ancestor_allows_rejection_in_body():
    record = dossier(
        [
            (
                "f-body",
                "body",
                [
                    Spec("b_d7", "Điều 7", "Nghiệm thu"),
                    Spec("b_d7k2", "2.", "Bên A nghiệm thu.", "b_d7"),
                    Spec(
                        "m1",
                        "Điều 9",
                        "1. Sửa đổi, bổ sung Điều 7 như sau:\n"
                        "a) Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7.",
                    ),
                ],
            ),
        ],
        [],
    )
    graph = build_contract_graph(record, [])

    assert [(e.op, e.target_node_id) for e in graph.edges] == [(EdgeOp.REJECTION, "b_d7k2")]
    assert graph.stats["scope_rejection_out_of_context"] == 0


def test_flag_on_contract_annex_verbs_emit_substitution(graph):
    by_source = _edges(graph)

    for source, target in (("a7", "b_d5k2"), ("a8", "b_d7"), ("a9", "b_d5k2")):
        (edge,) = by_source[source]
        assert (edge.op, edge.standard, edge.target_node_id) == (EdgeOp.SUBSTITUTION, False, target)
        assert edge.review_state == ReviewState.NEEDS_REVIEW


def test_flag_on_suffix_insertion_targets_new_address(graph):
    (edge,) = _edges(graph)["a10"]

    assert (edge.op, edge.target_address) == (EdgeOp.INSERTION, "khoan 5a dieu 18")
    assert edge.target_node_id == "b_d18"
    assert edge.target_node_id != "b_d18k5"
    assert edge.anchor_node_id == "b_d18k5"


def test_new_article_insertion_has_no_fake_node():
    # VL-6: a new Điều resolves UNIQUE with no node; no edge may point at the anchor instead
    record = dossier(
        [
            ("f-body", "body", [Spec("b_d30", "Điều 30", "Tổng thầu")]),
            (
                "f-annex",
                "annex",
                [Spec("a1", "1.", "Bổ sung Điều 30a vào sau Điều 30 như sau:\n“Điều 30a. EPC”")],
            ),
        ],
        [],
    )
    graph = build_contract_graph(record, [])

    assert graph.edges == []
    (issue,) = graph.issues
    assert (issue.missing, issue.review_state) == ("NEW_UNIT_ADDITION", ReviewState.NEEDS_REVIEW)
    assert issue.citation.node_id == "a1"
    assert graph.stats["new_unit_insertions"] == 1


def test_builder_failure_becomes_issue_not_job_failure(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("synthetic builder failure")

    monkeypatch.setattr(builder, "build_contract_graph", boom)
    result = _run(graph_record(), enabled=True, monkeypatch=monkeypatch)

    assert result.status == JobStatus.SUCCEEDED
    failed = [
        i for i in result.contribution.evidence_issues if i.missing == "CONTRACT_GRAPH_FAILED"
    ]
    assert len(failed) == 1
    assert failed[0].review_state == ReviewState.NEEDS_REVIEW
    assert result.contribution.evidence_issues[-1] is failed[0] or (
        result.contribution.evidence_issues[-1].missing == "CONTRACT_GRAPH_FAILED"
    )


def test_builder_does_not_mutate_record_or_facts():
    record = graph_record()
    facts = [fact.model_copy(deep=True) for fact in record.facts]
    before_record = copy.deepcopy(record_to_dict(record))
    before_nodes = [node.model_dump() for node in record.nodes]
    before_facts = [fact.model_dump() for fact in facts]

    build_contract_graph(record, facts)

    assert record_to_dict(record) == before_record
    assert [node.model_dump() for node in record.nodes] == before_nodes
    assert [fact.model_dump() for fact in facts] == before_facts


def test_edge_cap_truncates_with_issue(monkeypatch):
    monkeypatch.setattr(builder, "MAX_EDGES", 1)
    record = graph_record()
    graph = build_contract_graph(record, record.facts)

    assert len(graph.edges) == 1
    truncated = [i for i in graph.issues if i.missing == "CONTRACT_GRAPH_TRUNCATED"]
    assert len(truncated) == 1 and truncated[0].review_state == ReviewState.NEEDS_REVIEW
    assert graph.stats["truncated"] == 7


@pytest.mark.parametrize(
    ("value", "enabled"),
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("TRUE", True),
        (" on ", True),
        ("", False),
        ("0", False),
        ("false", False),
        ("off", False),
        ("2", False),
        (None, False),
    ],
)
def test_flag_truthy_values(monkeypatch, value, enabled):
    if value is None:
        monkeypatch.delenv(FLAG, raising=False)
    else:
        monkeypatch.setenv(FLAG, value)

    assert contract_graph_enabled() is enabled
    assert idp._contract_graph_enabled() is enabled


def test_citation_for_node_maps_to_citation_model():
    record = graph_record()
    raw = citation_for_node(record.evidence_nodes(), record.pages, "b_d3k1c")

    assert set(raw) <= set(Citation.model_fields)
    citation = Citation(**raw)
    assert (citation.node_id, citation.validation_status) == ("b_d3k1c", "VALID")


def test_edge_ids_are_deterministic_and_unique(graph):
    record = graph_record()
    again = build_contract_graph(record, record.facts)

    assert [e.edge_id for e in again.edges] == [e.edge_id for e in graph.edges]
    assert len({e.edge_id for e in graph.edges}) == len(graph.edges)
    assert graph.model_dump() == again.model_dump()
