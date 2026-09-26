from __future__ import annotations

from app.contracts.models import Candidate, Chunk, ContractContext, ContractEvent, EvidenceIssue, Fact, IndexContribution, ReviewState


class IndexStore:
    def __init__(self) -> None:
        self.contributions: list[IndexContribution] = []
        self.active_pointer: str | None = None

    def propose(
        self,
        *,
        facts: list[Fact],
        chunks: list[Chunk],
        candidates: list[Candidate],
        extraction_version: int,
        proposed_index_version: str,
        evidence_issues: list[EvidenceIssue] | None = None,
        contract_context: ContractContext | None = None,
        events: list[ContractEvent] | None = None,
        coverage: dict | None = None,
    ) -> IndexContribution:
        grounded_facts = [f for f in facts if f.review_state != ReviewState.INSUFFICIENT_EVIDENCE]
        grounded_ids = {f.fact_id for f in grounded_facts}
        safe_candidates = [c for c in candidates if _grounded(c, grounded_ids)]
        coverage_data = dict(coverage or {})
        coverage_data["n_candidates_suppressed"] = len(candidates) - len(safe_candidates)
        contrib = IndexContribution(
            facts=grounded_facts,
            chunks=chunks,
            candidates=safe_candidates,
            evidence_issues=evidence_issues or [],
            contract_context=contract_context,
            events=events or [],
            coverage=coverage_data,
            extraction_version=extraction_version,
            proposed_index_version=proposed_index_version,
            publish="propose",
        )
        self.contributions.append(contrib)
        # AI2 must not flip the active pointer
        return contrib


def _grounded(candidate: Candidate, grounded_fact_ids: set[str]) -> bool:
    """Keep fact pairs built on grounded facts, or clause pairs whose every citation verified."""

    if candidate.left_id in grounded_fact_ids and candidate.right_id in grounded_fact_ids:
        return True
    if not candidate.evidence_left or not candidate.evidence_right:
        return False
    return all(
        citation.validation_status == "VALID"
        for citation in [*candidate.evidence_left, *candidate.evidence_right]
    )
