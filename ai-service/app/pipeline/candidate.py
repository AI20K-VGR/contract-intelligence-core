from __future__ import annotations

from app.contracts.models import Candidate, EvidenceIssue, Fact
from app.pipeline.compare import compare_facts


class CandidatePairer:
    def pair(self, facts: list[Fact], *, annex_labels: set[str] | None = None) -> list[Candidate]:
        cands, _issues = compare_facts(facts, annex_labels_present=annex_labels or set())
        return cands

    def pair_with_issues(
        self, facts: list[Fact], *, annex_labels: set[str] | None = None
    ) -> tuple[list[Candidate], list[EvidenceIssue]]:
        return compare_facts(facts, annex_labels_present=annex_labels or set())
