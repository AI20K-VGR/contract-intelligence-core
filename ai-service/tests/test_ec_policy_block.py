"""Policy gates that must block external work without dropping local extraction."""

from app.contracts.models import ReviewState
from app.pipeline.idp import run_idp
from fixtures.catalog import all_cases


def test_ec050_embedding_budget_blocks_vector_and_keeps_local_job():
    pack = all_cases()["EC-050"]
    before = [node.node_id for node in pack.record.nodes]
    job = run_idp(pack.record, pack.envelope)
    assert [node.node_id for node in pack.record.nodes] == before
    assert job.status.value == "SUCCEEDED"
    assert job.review_state is ReviewState.BLOCKED
    assert any(issue.code == "EMBEDDING_BUDGET_EXCEEDED" for issue in job.handoff_issues)


def test_ec055_missing_egress_blocks_external_and_keeps_local_job():
    # Egress off blocks the external calls, not the job: local extraction is a
    # reviewable result (ST-067/D-4), so the review state is NEEDS_REVIEW.
    class ExplodingLLM:
        def configured(self):
            return True

        def complete_json(self, *_args, **_kwargs):
            raise AssertionError("egress is off: the provider must not be called")

    pack = all_cases()["EC-055"]
    before = [node.node_id for node in pack.record.nodes]
    job = run_idp(pack.record, pack.envelope, llm=ExplodingLLM())
    assert [node.node_id for node in pack.record.nodes] == before
    assert job.status.value == "SUCCEEDED"
    assert job.review_state is ReviewState.NEEDS_REVIEW
    egress = [issue for issue in job.handoff_issues if issue.code == "EGRESS_DENIED"]
    assert egress and egress[0].review_state is ReviewState.NEEDS_REVIEW
