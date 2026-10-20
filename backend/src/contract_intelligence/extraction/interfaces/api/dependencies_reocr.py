"""Re-OCR FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.extraction.application.services.reocr_service import ReOcrService
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import get_async_session


async def get_reocr_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> ReOcrService:
    return ReOcrService(session=session, tenant_id=tenant_id)


ReOcrServiceDep = Annotated[ReOcrService, Depends(get_reocr_service)]


__all__ = ["ReOcrServiceDep", "get_reocr_service"]
