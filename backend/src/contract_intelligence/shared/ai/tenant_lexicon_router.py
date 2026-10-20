"""Authenticated tenant lexicon API; client không thể bật activation policy."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.shared.ai.tenant_lexicon_contracts import LexiconCommand
from contract_intelligence.shared.ai.tenant_lexicon_service import (
    LexiconError,
    TenantLexiconService,
)
from contract_intelligence.shared.auth import AuthenticatedUser
from contract_intelligence.shared.auth.dependencies import require_tenant
from contract_intelligence.shared.persistence.session import get_async_session

router = APIRouter(prefix="/tenants/{tenant_id}/lexicon", tags=["Tenant lexicon"])
User = Annotated[AuthenticatedUser, Depends(require_tenant)]
Session = Annotated[AsyncSession, Depends(get_async_session)]


@router.get("")
async def read_lexicon(
    tenant_id: str, user: User, session: Session, version: Annotated[int | None, Query(ge=1)] = None
) -> dict[str, Any]:
    try:
        service = TenantLexiconService(session)
        return {
            "data": await service.read_profile(tenant_id, user, version),
            "metadata": await service.read_metadata(tenant_id, user),
        }
    except LexiconError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code}) from exc


@router.post("/commands")
async def mutate_lexicon(
    tenant_id: str, command: LexiconCommand, user: User, session: Session
) -> dict[str, Any]:
    try:
        return {"data": await TenantLexiconService(session).execute(tenant_id, user, command)}
    except LexiconError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code}) from exc
