from __future__ import annotations

from app.contracts.models import Candidate, EvidenceIssue, Fact
from app.pipeline.compare import compare_facts


class CandidatePairer:
    def pair(
        self,
        facts: list[Fact],
        *,
        annex_labels: set[str] | None = None,
        relation_pairs: set[tuple[str, str]] | None = None,
        require_relation_for_cross_document: bool = False,
    ) -> list[Candidate]:
        cands, _issues = compare_facts(
            facts,
            annex_labels_present=annex_labels or set(),
            relation_pairs=relation_pairs,
            require_relation_for_cross_document=require_relation_for_cross_document,
        )
        return cands

    def pair_with_issues(
        self,
        facts: list[Fact],
        *,
        annex_labels: set[str] | None = None,
        relation_pairs: set[tuple[str, str]] | None = None,
        require_relation_for_cross_document: bool = False,
        split_installments: bool = False,
    ) -> tuple[list[Candidate], list[EvidenceIssue]]:
        return compare_facts(
            facts,
            annex_labels_present=annex_labels or set(),
            relation_pairs=relation_pairs,
            require_relation_for_cross_document=require_relation_for_cross_document,
            split_installments=split_installments,
        )
