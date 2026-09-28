from app.contracts.models import ReviewState
from app.pipeline.idp import run_idp
from app.pipeline.index import IndexStore
from fixtures import envelope, mock_record


def test_index_contribution_is_propose_only_and_never_moves_active_pointer():
    record = mock_record()
    result = run_idp(record, envelope(), llm=None)
    assert result.contribution is not None

    store = IndexStore()
    first = store.propose(
        facts=result.contribution.facts,
        chunks=result.contribution.chunks,
        candidates=result.contribution.candidates,
        evidence_issues=result.contribution.evidence_issues,
        contract_context=result.contribution.contract_context,
        events=result.contribution.events,
        coverage=result.contribution.coverage,
        extraction_version=result.contribution.extraction_version,
        proposed_index_version=result.contribution.proposed_index_version,
    )
    second = store.propose(
        facts=result.contribution.facts,
        chunks=result.contribution.chunks,
        candidates=result.contribution.candidates,
        evidence_issues=result.contribution.evidence_issues,
        contract_context=result.contribution.contract_context,
        events=result.contribution.events,
        coverage=result.contribution.coverage,
        extraction_version=result.contribution.extraction_version,
        proposed_index_version=result.contribution.proposed_index_version,
    )

    assert first.publish == "propose"
    assert second.publish == "propose"
    assert store.active_pointer is None
    assert len(store.contributions) == 2


def test_review_required_output_cannot_be_treated_as_published_index():
    record = mock_record()
    record.pages[0].quality = "LOW"
    result = run_idp(record, envelope(), llm=None)

    assert result.contribution is not None
    assert result.review_state == ReviewState.NEEDS_REVIEW
    assert result.contribution.publish == "propose"
