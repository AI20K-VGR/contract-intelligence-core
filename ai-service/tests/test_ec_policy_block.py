"""Policy gates that must block external work without dropping local extraction."""

from fixtures.catalog import all_cases

from app.contracts.models import ReviewState
from app.pipeline.idp import run_idp


def test_ec050_embedding_budget_blocks_vector_and_keeps_local_job():
    pack = all_cases()["EC-050"]
    before = [node.node_id for node in pack.record.nodes]
    job = run_idp(pack.record, pack.envelope)
    assert [node.node_id for node in pack.record.nodes] == before
    assert job.status.value == "SUCCEEDED"
    assert job.review_state is ReviewState.BLOCKED
    assert any(issue.code == "EMBEDDING_BUDGET_EXCEEDED" for issue in job.handoff_issues)


def test_ec055_missing_egress_blocks_external_and_keeps_local_job():
    pack = all_cases()["EC-055"]
    before = [node.node_id for node in pack.record.nodes]
    job = run_idp(pack.record, pack.envelope)
    assert [node.node_id for node in pack.record.nodes] == before
    assert job.status.value == "SUCCEEDED"
    assert job.review_state is ReviewState.BLOCKED
    assert any(issue.code == "EGRESS_DENIED" for issue in job.handoff_issues)
