"""Repository Protocols cho bounded context extraction."""

from contract_intelligence.extraction.domain.repositories.citation_repository import (
    CitationRepository,
)
from contract_intelligence.extraction.domain.repositories.fact_repository import FactRepository
from contract_intelligence.extraction.domain.repositories.page_repository import PageRepository

__all__ = ["CitationRepository", "FactRepository", "PageRepository"]
