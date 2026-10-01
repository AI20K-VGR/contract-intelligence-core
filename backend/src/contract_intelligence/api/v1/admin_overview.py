"""Admin overview — system activity feed and storage usage.

RBAC: OPERATOR, REVIEWER, ADMINISTRATOR.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.admin.activity_feed import list_activity, storage_usage
from contract_intelligence.shared.auth import AuthenticatedUser, require_role
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.responses import ApiMeta, ApiResponse

router = APIRouter(prefix="/admin", tags=["Admin"])

Reader = Annotated[
    AuthenticatedUser, Depends(require_role("OPERATOR", "REVIEWER", "ADMINISTRATOR"))
]


class ActivityEventDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    occurred_at: datetime
    actor_display_name: str | None
    title: str
    detail: str | None


class StorageUsageDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    used_bytes: int
    quota_bytes: int | None


@router.get(
    "/activity",
    response_model=ApiResponse[list[ActivityEventDTO]],
    summary="Recent tenant activity",
)
async def get_activity(
    admin: Reader,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 8,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[ActivityEventDTO]]:
    """Dossier, upload, member, review, approval and admin actions for this tenant."""
    own_names = None
    if admin.role != "ADMINISTRATOR":
        own_names = [admin.email, admin.display_name]
    page = await list_activity(
        session,
        tenant_id=admin.tenant_id,
        limit=limit,
        offset=offset,
        actors=own_names,
    )
    return ApiResponse(
        data=[
            ActivityEventDTO(
                id=item.id,
                occurred_at=item.occurred_at,
                actor_display_name=item.actor_display_name,
                title=item.title,
                detail=item.detail,
            )
            for item in page.items
        ],
        meta=ApiMeta(page=(offset // limit) + 1, page_size=limit, total=page.total),
    )


@router.get(
    "/storage",
    response_model=ApiResponse[StorageUsageDTO],
    summary="Tenant storage usage",
)
async def get_storage(
    admin: Reader,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ApiResponse[StorageUsageDTO]:
    """Sum of uploaded document bytes. ``quota_bytes`` is null until a quota exists."""
    usage = await storage_usage(session, tenant_id=admin.tenant_id)
    return ApiResponse(
        data=StorageUsageDTO(used_bytes=usage.used_bytes, quota_bytes=usage.quota_bytes)
    )
