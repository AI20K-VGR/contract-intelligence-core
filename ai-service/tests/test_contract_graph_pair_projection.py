from __future__ import annotations

import hashlib

import pytest

from app.contracts.contract_graph import PairLabel, PairRelation, PairResult
from app.contracts.models import Citation, ComparisonScope, ReviewState
from app.pipeline.contract_graph.pair_projection import (
    limited_coverage_issue,
    pair_conflict_candidates,
    pair_coverage,
)
from app.pipeline.outline import citation_for_node
from fixtures.contract_graph_pair_records import pair_record
from fixtures.contract_graph_records import Spec, dossier


def relation(record, a="pb2", b="pa2", label=PairLabel.CONFLICT):
    nodes = record.evidence_nodes()
    ca = Citation(**citation_for_node(nodes, record.pages, a))
    cb = Citation(**citation_for_node(nodes, record.pages, b))
    return PairRelation(relation_id=f"r:{a}:{b}", label=label, node_a_id=a, node_b_id=b,
                        directed=label in {PairLabel.GENERAL_SPECIFIC, PairLabel.REFERENCE},
                        candidate_sources=["topic"], span_a=ca.text_span[:20], span_b=cb.text_span[:20],
                        citation_a=ca, citation_b=cb, classifier_model="claude-fixture",
                        prompt_version="pairs-v1", source_snapshot_digest=record.pins.source_snapshot_digest)


def result(record, relations=None):
    return PairResult(mode="llm", prompt_version="pairs-v1", batches_completed=1,
                      relations=relations if relations is not None else [relation(record)],
                      node_parts={n.node_id: "annex:f-annex" if n.node_id.startswith("pa") else "body:f-body"
                                  for n in record.nodes})


def test_conflict_becomes_comparable_difference_needs_review():
    rec = pair_record()
    candidates, stats = pair_conflict_candidates(result(rec), [], rec)
    assert len(candidates) == stats["conflict_findings"] == 1
    c = candidates[0]
    assert c.finding_type.value == c.disposition.value == "COMPARABLE_DIFFERENCE"
    assert c.model_disposition.value == "UNCLEAR"
    assert c.review_state == ReviewState.NEEDS_REVIEW


def test_conflict_evidence_is_whole_node_citation():
    rec = pair_record()
    c = pair_conflict_candidates(result(rec), [], rec)[0][0]
    assert c.evidence_left[0].text_span == rec.nodes[1].text
    assert c.evidence_left[0].text_span != relation(rec).span_a
    assert c.evidence_left[0].validation_status == c.evidence_right[0].validation_status == "VALID"


def long_record():
    lead = "Hai bên thực hiện đầy đủ trách nhiệm giao nhận và đối chiếu chứng từ. " * 8
    return dossier([
        ("f-body", "body", [Spec("pb2", "Điều 2", lead + "\nBên A thanh toán trong 30 ngày.")]),
        ("f-annex", "annex", [Spec("pa2", "Điều 2", lead + "\nBên A thanh toán trong 15 ngày.")]),
    ], [])


def test_long_multiline_conflict_keeps_entire_node_and_differing_tail():
    rec = long_record()
    cs, stats = pair_conflict_candidates(result(rec), [], rec)
    assert len(cs) == 1
    assert cs[0].evidence_left[0].text_span == rec.nodes[0].text
    assert cs[0].evidence_right[0].text_span == rec.nodes[1].text
    assert "30 ngày" in cs[0].evidence_left[0].text_span
    assert "15 ngày" in cs[0].evidence_right[0].text_span
    assert all(c.validation_status == "VALID" for c in cs[0].evidence_left + cs[0].evidence_right)


def test_full_node_split_across_pages_is_rejected_without_partial_fallback():
    rec = long_record()
    proposed = result(rec)
    page = rec.pages[0]
    first_line, second_line = list(page.line_texts.items())
    second_page = page.model_copy(deep=True, update={
        "page_revision_id": "f-body:p2", "page_number": 3, "page_in_file": 2,
        "text": second_line[1], "line_texts": {second_line[0]: second_line[1]},
        "source_hash": "sha256:" + hashlib.sha256(second_line[1].encode()).hexdigest(),
    })
    page.text = first_line[1]
    page.line_texts = {first_line[0]: first_line[1]}
    page.source_hash = "sha256:" + hashlib.sha256(page.text.encode()).hexdigest()
    rec.nodes[0].page_range = [1, 3]
    rec.pages.append(second_page)
    cs, stats = pair_conflict_candidates(proposed, [], rec)
    assert not cs and stats["conflict_citation_invalid"] == 1


def test_conflict_findings_capped_per_dossier():
    rec = pair_record()
    relations = [relation(rec, a, b) for a, b in
                 [("pb1", "pa1"), ("pb2", "pa2"), ("pb3", "pa3"), ("pb4", "pa1"),
                  ("pb5", "pa2"), ("pb6", "pa3"), ("pb1", "pa2"), ("pb2", "pa1")]]
    cs, stats = pair_conflict_candidates(result(rec, relations), [], rec)
    assert [(c.left_id, c.right_id) for c in cs] == [(r.node_a_id, r.node_b_id) for r in relations[:5]]
    assert stats["conflict_capped"] == 3


def test_conflict_deduped_against_existing_candidate_pair():
    rec = pair_record()
    first = pair_conflict_candidates(result(rec), [], rec)[0]
    cs, stats = pair_conflict_candidates(result(rec), first, rec)
    assert not cs and stats["conflict_deduped_with_candidates"] == 1


@pytest.mark.parametrize("label", [PairLabel.GENERAL_SPECIFIC, PairLabel.DUPLICATE, PairLabel.REFERENCE])
def test_general_specific_duplicate_reference_emit_no_candidate(label):
    rec = pair_record()
    assert pair_conflict_candidates(result(rec, [relation(rec, label=label)]), [], rec)[0] == []


@pytest.mark.parametrize("parts,scope", [(("body:f", "body:f"), ComparisonScope.WITHIN_DOCUMENT),
                                       (("annex:f", "annex:g"), ComparisonScope.ANNEX_ANNEX),
                                       (("body:f", "annex:g"), ComparisonScope.CONTRACT_ANNEX)])
def test_scope_from_parts(parts, scope):
    rec = pair_record()
    r = result(rec)
    r.node_parts.update(pb2=parts[0], pa2=parts[1])
    assert pair_conflict_candidates(r, [], rec)[0][0].scope == scope


def test_item_key_is_canonical_address_pair():
    rec = pair_record()
    assert pair_conflict_candidates(result(rec), [], rec)[0][0].item_key


def test_candidate_id_stable():
    rec = pair_record()
    assert pair_conflict_candidates(result(rec), [], rec)[0] == pair_conflict_candidates(result(rec), [], rec)[0]


def test_invalid_citation_is_counted():
    rec = pair_record()
    rec.pages[0].source_hash = None
    cs, stats = pair_conflict_candidates(result(rec), [], rec)
    assert not cs and stats["conflict_citation_invalid"] == 1


REASONS = ["NO_CONSENT", "EGRESS_DENIED", "LLM_UNAVAILABLE", "MODEL_UNSET", "BUDGET_EXHAUSTED", "DEADLINE"]


@pytest.mark.parametrize("reason", REASONS)
def test_limited_coverage_issue_per_reason(reason):
    r = PairResult(mode="rule_only", rule_only_reason=reason, prompt_version="pairs-v1",
                   stats={"candidates_kept": 9})
    issue = limited_coverage_issue(r)
    assert issue.issue_id == "contract-graph:CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE"
    assert issue.review_state == ReviewState.NEEDS_REVIEW
    assert "9" in issue.reason
    assert not any(label.value in issue.reason for label in PairLabel)


def test_reason_and_issue_texts_have_no_label_tokens():
    rec = pair_record()
    c = pair_conflict_candidates(result(rec), [], rec)[0][0]
    assert not any(label.value in c.reason for label in PairLabel)


def test_pair_coverage_keys_fixed_and_failed_zero():
    rec = pair_record()
    success = pair_coverage(result(rec), status="OK", conflict_stats={"conflict_findings": 1})
    failed = pair_coverage(None, status="FAILED", conflict_stats={})
    assert success["pairs"].keys() == failed["pairs"].keys()
    assert failed["pairs"]["relations_total"] == failed["pairs"]["conflict_findings"] == 0
    assert failed["graph_mode"] == "operation_first"


@pytest.mark.parametrize("mode", ["llm", "rule_only"])
def test_graph_mode_values(mode):
    r = PairResult(mode=mode, prompt_version="pairs-v1")
    assert pair_coverage(r, status="OK", conflict_stats={})["graph_mode"] == "operation_first+pairs_" + mode
