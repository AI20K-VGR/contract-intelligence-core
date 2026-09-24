"""Extraction FastAPI dependencies — composition root."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DocumentRepositoryImpl,
)
from contract_intelligence.extraction.application.services.extraction_service import (
    ExtractionService,
)
from contract_intelligence.extraction.infrastructure.persistence.repository_impl import (
    CitationRepositoryImpl,
    ClauseNodeRepositoryImpl,
    DocTableRepositoryImpl,
    FactRepositoryImpl,
    PageRepositoryImpl,
    PipelineRunRepositoryImpl,
)
from contract_intelligence.shared.ai import (
    PipelineOrchestrator,
    get_pipeline_orchestrator,
)
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.storage import FileStorage, get_file_storage


async def get_extraction_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    orchestrator: Annotated[PipelineOrchestrator, Depends(get_pipeline_orchestrator)],
    storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ExtractionService:
    """Compose ExtractionService bound to current tenant + session + orchestrator.

    DocumentRepositoryImpl được inject từ Contract BC infrastructure — đây là
    cross-BC read (Extraction cần list documents của dossier để build pipeline).
    Tuân thủ Dependency Rule: Application layer KHÔNG import infrastructure trực
    tiếp — composition root (file này) mới được phép.
    """
    return ExtractionService(
        pipeline_run_repo=PipelineRunRepositoryImpl(session, tenant_id),
        page_repo=PageRepositoryImpl(session, tenant_id),
        ocr_line_repo=None,  # included via page_repo.get()
        fact_repo=FactRepositoryImpl(session, tenant_id),
        citation_repo=CitationRepositoryImpl(session, tenant_id),
        clause_repo=ClauseNodeRepositoryImpl(session, tenant_id),
        table_repo=DocTableRepositoryImpl(session, tenant_id),
        document_repo=DocumentRepositoryImpl(session, tenant_id),
        storage=storage,
        orchestrator=orchestrator,
        tenant_id=tenant_id,
    )


ExtractionServiceDep = Annotated[ExtractionService, Depends(get_extraction_service)]


__all__ = ["ExtractionServiceDep", "get_extraction_service"]
