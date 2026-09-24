"""Use case: lưu kết quả extraction (fact/citation/clause) từ AI Service callback."""

from __future__ import annotations

from contract_intelligence.extraction.domain.entities.citation import Citation
from contract_intelligence.extraction.domain.entities.fact import Fact
from contract_intelligence.extraction.domain.repositories.citation_repository import (
    CitationRepository,
)
from contract_intelligence.extraction.domain.repositories.fact_repository import FactRepository
from contract_intelligence.shared.exceptions import ValidationError


class ExtractionResultService:
    """Use case — POST /pipelines/runs/{id}/results (callback từ AI Service).

    Validate payload, persist citation + fact (bất biến 🔒).
    """

    def __init__(
        self,
        *,
        citation_repo: CitationRepository,
        fact_repo: FactRepository,
    ) -> None:
        self._citation_repo = citation_repo
        self._fact_repo = fact_repo

    async def ingest(self, *, citation: Citation, facts: list[Fact]) -> str:
        if not citation.quote:
            raise ValidationError("Citation quote rỗng", field="quote")
        if not facts:
            raise ValidationError("Phải có ít nhất 1 fact", field="facts")
        await self._citation_repo.add(citation)
        for fact in facts:
            if fact.citation_id != citation.id:
                raise ValidationError(
                    f"Fact {fact.id} trỏ citation_id khác citation đang ingest",
                    field="citation_id",
                )
            await self._fact_repo.add(fact)
        return citation.id
