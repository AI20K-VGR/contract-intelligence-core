"""Operator API for normalized Backend/AI2/Frontend log receipts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.admin.service_log import ServiceLogEventORM
from contract_intelligence.shared.auth import AuthenticatedUser, require_role
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.responses import ApiMeta, ApiResponse

router = APIRouter(prefix="/ops/service-logs", tags=["Admin/Ops"])

_SECRET_KEYS = frozenset(
    {"authorization", "api_key", "apikey", "access_token", "refresh_token", "password", "secret"}
)
_SECRET_VALUE = re.compile(r"(?i)(bearer\s+|sk-[a-z0-9_-]{8,}|api[_-]?key\s*[=:]\s*)[^\s,;]+")


def redact_log_payload(value: Any) -> Any:
    """Remove credentials before a diagnostic payload reaches PostgreSQL."""

    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]"
            if str(key).casefold() in _SECRET_KEYS
            else redact_log_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_log_payload(item) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE.sub(r"\1[REDACTED]", value)
    return value


class ServiceLogInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    service: Literal["backend", "ai2", "frontend"]
    source: str = Field(default="docker", min_length=1, max_length=64)
    level: str = Field(default="INFO", min_length=1, max_length=16)
    event: str = Field(min_length=1, max_length=256)
    message: str | None = Field(default=None, max_length=4000)
    dossier_id: str | None = Field(default=None, max_length=128)
    run_id: str | None = Field(default=None, max_length=128)
    job_id: str | None = Field(default=None, max_length=128)
    trace_id: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=128)
    occurred_at: datetime = Field(default_factory=utcnow)
    payload: dict[str, Any] | None = None


class ServiceLogBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[ServiceLogInput] = Field(min_length=1, max_length=500)


class ServiceLogOutput(ServiceLogInput):
    id: str
    tenant_id: str | None

    @classmethod
    def from_orm_row(cls, row: ServiceLogEventORM) -> ServiceLogOutput:
        return cls(
            id=row.id,
            tenant_id=row.tenant_id,
            service=row.service,
            source=row.source,
            level=row.level,
            event=row.event,
            message=row.message,
            dossier_id=row.dossier_id,
            run_id=row.run_id,
            job_id=row.job_id,
            trace_id=row.trace_id,
            request_id=row.request_id,
            occurred_at=row.occurred_at,
            payload=row.payload,
        )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, int]],
    summary="Ingest normalized service log receipts",
)
async def ingest_service_logs(
    body: ServiceLogBatch,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, int]]:
    """Store a bounded, tenant-scoped batch for later E2E inspection."""

    for item in body.events:
        session.add(
            ServiceLogEventORM(
                id=new_ulid("log_"),
                tenant_id=user.tenant_id,
                service=item.service,
                source=item.source,
                level=item.level.upper(),
                event=item.event,
                message=item.message,
                dossier_id=item.dossier_id,
                run_id=item.run_id,
                job_id=item.job_id,
                trace_id=item.trace_id,
                request_id=item.request_id,
                occurred_at=item.occurred_at,
                payload=redact_log_payload(item.payload) if item.payload is not None else None,
            )
        )
    await session.flush()
    return ApiResponse(data={"accepted": len(body.events)})


@router.get(
    "",
    response_model=ApiResponse[list[ServiceLogOutput]],
    summary="Read normalized Backend/AI2/Frontend logs",
)
async def list_service_logs(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
    service: Annotated[Literal["backend", "ai2", "frontend"] | None, Query()] = None,
    dossier_id: Annotated[str | None, Query()] = None,
    run_id: Annotated[str | None, Query()] = None,
    level: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[ServiceLogOutput]]:
    clauses = [ServiceLogEventORM.tenant_id == user.tenant_id]
    if service:
        clauses.append(ServiceLogEventORM.service == service)
    if dossier_id:
        clauses.append(ServiceLogEventORM.dossier_id == dossier_id)
    if run_id:
        clauses.append(ServiceLogEventORM.run_id == run_id)
    if level:
        clauses.append(ServiceLogEventORM.level == level.upper())

    total = int(
        await session.scalar(select(func.count()).select_from(ServiceLogEventORM).where(*clauses))
        or 0
    )
    rows = (
        await session.execute(
            select(ServiceLogEventORM)
            .where(*clauses)
            .order_by(ServiceLogEventORM.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars()
    return ApiResponse(
        data=[ServiceLogOutput.from_orm_row(row) for row in rows],
        meta=ApiMeta(page=(offset // limit) + 1, page_size=limit, total=total),
    )


__all__ = ["router"]
