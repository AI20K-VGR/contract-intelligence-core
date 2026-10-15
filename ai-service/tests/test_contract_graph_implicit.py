"""K4: an annex without addresses meets the body only through ``item_key``; always NEEDS_REVIEW."""

from __future__ import annotations

from app.contracts.contract_graph import EdgeMethod, EdgeOp
from app.contracts.models import RelationSupport, ReviewState
from app.pipeline.contract_graph.builder import build_contract_graph
from fixtures.contract_graph_records import FactSpec, Spec, implicit_record


def _full_calibration() -> dict:
    return {
        "schema": "contract-graph-calibration.v1",
        "ground_truth": "approved-only",
        "ops": {op.value: {"n": 60, "k": 60, "report": None} for op in EdgeOp},
    }


def _graph(record, **kwargs):
    return build_contract_graph(record, record.facts, **kwargs)


def test_implicit_substitution_by_item_key_is_always_needs_review():
    graph = _graph(implicit_record(), calibration=_full_calibration(), auto_pass=True)

    (edge,) = graph.edges
    assert (edge.op, edge.method, edge.support) == (
        EdgeOp.SUBSTITUTION,
        EdgeMethod.ITEM_KEY,
        RelationSupport.HEURISTIC,
    )
    assert (edge.implicit, edge.standard) == (True, False)
    assert (edge.source_node_id, edge.target_node_id) == ("x1", "b_d2k1")
    assert edge.review_state == ReviewState.NEEDS_REVIEW
    assert graph.stats["implicit_edges"] == 1
    assert graph.issues == []


def test_implicit_same_value_emits_no_edge():
    record = implicit_record(annex_facts=[FactSpec("fa1", "x1", "so_luong_thep_cuon", "100")])
    graph = _graph(record)

    assert graph.edges == []
    assert graph.issues == []
    assert graph.stats["implicit_same_value"] == 1


def test_implicit_multiple_body_nodes_is_ambiguous_issue():
    record = implicit_record(
        body_facts=[
            FactSpec("fb1", "b_d2k1", "so_luong_thep_cuon", "100"),
            FactSpec("fb2", "b_d2k2", "so_luong_thep_cuon", "90"),
        ]
    )
    graph = _graph(record)

    assert graph.edges == []
    (issue,) = graph.issues
    assert (issue.missing, issue.review_state) == ("TARGET_AMBIGUOUS", ReviewState.NEEDS_REVIEW)
    assert issue.issue_id.startswith("contract-graph:")


def test_implicit_no_body_match_is_not_found_issue():
    record = implicit_record(body_facts=[FactSpec("fb1", "b_d2k1", "so_luong_thep_tam", "100")])
    graph = _graph(record)

    assert graph.edges == []
    (issue,) = graph.issues
    assert (issue.missing, issue.review_state) == (
        "TARGET_NOT_FOUND",
        ReviewState.INSUFFICIENT_EVIDENCE,
    )


def test_implicit_skipped_when_annex_part_has_explicit_edges():
    record = implicit_record(annex_extra=[Spec("x2", "2.", "Bãi bỏ khoản 3 Điều 7.", "x_pl")])
    graph = _graph(record)

    assert [(e.op, e.implicit, e.source_node_id) for e in graph.edges] == [
        (EdgeOp.REPEAL, False, "x2")
    ]
    assert graph.stats["implicit_edges"] == 0


def test_annex_without_implicit_marker_emits_nothing():
    graph = _graph(implicit_record(annex_text="Danh mục hàng hóa giao đợt 2."))

    assert graph.edges == []
    assert graph.issues == []


def test_implicit_marker_with_address_is_not_implicit():
    # "Điều chỉnh Điều 2" names its target: explicit lane only (here: no "như sau" ⇒ no template)
    graph = _graph(implicit_record(annex_text="Điều chỉnh số lượng tại Điều 2 theo bảng dưới."))

    assert [e for e in graph.edges if e.implicit] == []
