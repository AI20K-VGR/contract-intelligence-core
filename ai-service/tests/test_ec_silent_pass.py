"""EC cases whose extraction job must not stay PASS with an empty issue list.

The catalog states REVIEW. A probe on 2026-09-27 ran run_idp and got PASS
plus zero handoff issues for these five. The forbidden claims in the catalog
must also stay absent: no invented clause, no legal winner, no language pick.
"""

from fixtures.catalog import all_cases

from app.contracts.models import ReviewState
from app.pipeline.idp import run_idp


def _job(case_id: str):
    pack = all_cases()[case_id]
    before = [node.node_id for node in pack.record.nodes]
    job = run_idp(pack.record, pack.envelope)
    after = [node.node_id for node in pack.record.nodes]
    return pack, job, before, after


def test_ec005_numbering_gap_is_review_and_does_not_invent_clause_3():
    pack, job, before, after = _job("EC-005")
    assert after == before
    assert not any((node.raw_label or "") == "Điều 3" for node in pack.record.nodes)
    assert job.review_state is ReviewState.NEEDS_REVIEW
    assert any(issue.code == "NUMBERING_GAP" for issue in job.handoff_issues)


def test_ec014_table_header_is_not_page_furniture():
    pack = all_cases()["EC-014"]
    job = run_idp(pack.record, pack.envelope)
    assert pack.record.tables[0].header == ["Q1/amount", "Q1/qty", "Q2/amount", "Q2/qty"]
    assert not any(issue.code == "RECONSTRUCTION_BOUNDARY" for issue in job.handoff_issues)


def test_ec007_header_split_is_review_and_nodes_stay_separate():
    pack, job, before, after = _job("EC-007")
    assert after == before
    assert len(pack.record.nodes) == 2
    assert job.review_state is ReviewState.NEEDS_REVIEW
    assert any(issue.code == "RECONSTRUCTION_BOUNDARY" for issue in job.handoff_issues)


def test_ec031_bilingual_pair_is_review_and_does_not_pick_a_language():
    pack, job, before, after = _job("EC-031")
    assert after == before
    labels = {node.raw_label for node in pack.record.nodes}
    assert labels == {"Art 19", "Điều 19"}
    assert job.review_state is ReviewState.NEEDS_REVIEW
    assert any(issue.code == "BILINGUAL_DIVERGENCE" for issue in job.handoff_issues)


def test_ec033_amended_definition_is_review_without_a_winner():
    pack, job, before, after = _job("EC-033")
    assert after == before
    assert job.review_state is ReviewState.NEEDS_REVIEW
    assert any(issue.code == "DEFINITION_CASCADE" for issue in job.handoff_issues)
    assert "legal_winner" not in job.model_dump_json()


def test_ec047_budget_without_llm_is_review():
    _pack, job, _before, _after = _job("EC-047")
    assert job.status.value == "SUCCEEDED"
    assert job.review_state is ReviewState.NEEDS_REVIEW
    assert any(issue.code == "BUDGET_EXCEEDED" for issue in job.handoff_issues)
