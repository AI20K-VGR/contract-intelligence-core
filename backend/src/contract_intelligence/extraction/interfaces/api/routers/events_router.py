"""Server-Sent Events (SSE) endpoint cho real-time pipeline run updates.

DOC-11 §8: ``GET /runs/{id}/events`` đẩy tiến độ run xuống frontend, không
hỏi lại định kỳ.

Pattern:
    1. Worker đổi trạng thái job/run/step → cùng transaction ghi một dòng
       ``run_event`` (và ``pg_notify`` trên PostgreSQL) — xem
       :mod:`contract_intelligence.shared.run_events`.
    2. Process API nghe ``LISTEN run_events`` và đánh thức stream của run đó.
    3. Stream đọc các dòng ``run_event`` có ``id`` lớn hơn id đã gửi, gửi xuống
       với ``id:`` = ``run_event.id``. Client nối lại với ``Last-Event-ID`` thì
       nhận đủ sự kiện đã lỡ, không trùng.
    4. Stream đóng sau ``run.completed`` khi run ở trạng thái kết thúc.

Stream chỉ mở session ngắn khi đọc — không giữ kết nối DB suốt thời gian mở.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.shared.acl import AclAction, dossier_access_decision
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.persistence import get_session_factory
from contract_intelligence.shared.run_events import (
    TERMINAL_RUN_STATUSES,
    RunEventBroker,
    RunEventORM,
    get_run_event_broker,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Events"])


# Heartbeat interval (seconds)
_HEARTBEAT_INTERVAL = 15.0
# Rows read per wake-up; a stream further behind reads the next batch at once.
_BATCH_SIZE = 200

SessionFactory = Callable[[], AsyncSession]


async def _run_snapshot(
    session: AsyncSession, tenant_id: str, run_id: str
) -> dict[str, Any] | None:
    result = await session.execute(
        select(PipelineRunORM, JobORM)
        .join(JobORM, JobORM.id == PipelineRunORM.job_id, isouter=True)
        .where(PipelineRunORM.id == run_id, PipelineRunORM.tenant_id == tenant_id)
    )
    row = result.first()
    if row is None:
        return None
    run, job = row
    return {
        "run_id": run.id,
        "dossier_id": run.dossier_id,
        "status": run.status,
        "job_status": job.status if job is not None else None,
        "error_code": run.error_code or (job.error_code if job is not None else None),
        "pipeline_version": run.pipeline_version,
    }


async def _events_after(
    session: AsyncSession, tenant_id: str, run_id: str, after_id: int
) -> list[RunEventORM]:
    result = await session.execute(
        select(RunEventORM)
        .where(
            RunEventORM.run_id == run_id,
            RunEventORM.tenant_id == tenant_id,
            RunEventORM.id > after_id,
        )
        .order_by(RunEventORM.id)
        .limit(_BATCH_SIZE)
    )
    return list(result.scalars())


async def _stream_run_events(
    *,
    session_factory: SessionFactory,
    broker: RunEventBroker,
    tenant_id: str,
    run_id: str,
    after_id: int = 0,
    heartbeat_interval: float = _HEARTBEAT_INTERVAL,
) -> AsyncIterator[str]:
    """Async generator stream SSE events cho 1 pipeline run."""
    # Subscribe before the first read: a commit landing between a read and the
    # wait still sets the flag, so nothing falls in the gap.
    with broker.subscribe(run_id) as wake:
        try:
            async with session_factory() as session:
                snapshot = await _run_snapshot(session, tenant_id, run_id)
            if snapshot is None:
                yield _format_event(
                    event="error", data={"error": "RUN_NOT_FOUND", "run_id": run_id}
                )
                return
            yield _format_event(event="run.started", data=snapshot)

            run_status = snapshot["status"]
            error_code = snapshot["error_code"]
            last_id = after_id
            while True:
                wake.clear()
                async with session_factory() as session:
                    rows = await _events_after(session, tenant_id, run_id, last_id)
                for row in rows:
                    data = json.loads(row.payload)
                    yield _format_event(event=row.type, data=data, event_id=row.id)
                    last_id = row.id
                    if row.type == "run.status_changed":
                        run_status = data.get("status", run_status)
                        error_code = data.get("error_code")
                if len(rows) == _BATCH_SIZE:
                    continue
                if run_status in TERMINAL_RUN_STATUSES:
                    yield _format_event(
                        event="run.completed",
                        data={"run_id": run_id, "status": run_status, "error_code": error_code},
                    )
                    return
                try:
                    await asyncio.wait_for(wake.wait(), timeout=heartbeat_interval)
                except TimeoutError:
                    yield ":heartbeat\n\n"
        except asyncio.CancelledError:
            logger.info("sse.client_disconnected", run_id=run_id)
            raise
        except Exception as exc:
            logger.exception("sse.stream_error", run_id=run_id, error=str(exc))
            yield _format_event(event="error", data={"error": "INTERNAL"})


def _format_event(
    *, event: str, data: dict[str, Any] | None = None, event_id: int | None = None
) -> str:
    """Format SSE event chuẩn (text/event-stream)."""
    head = f"id: {event_id}\n" if event_id is not None else ""
    if data is None:
        return f"{head}event: {event}\n\n"
    return f"{head}event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _resume_id(header_value: str | None, query_value: int | None) -> int:
    """``Last-Event-ID`` header (browser reconnect) wins over ``?last_event_id=``."""
    if header_value:
        try:
            return max(0, int(header_value))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Last-Event-ID must be an integer event id",
            ) from None
    return query_value or 0


async def _require_run_readable(
    session_factory: SessionFactory, user: AuthenticatedUser, run_id: str
) -> None:
    async with session_factory() as session:
        result = await session.execute(
            select(DossierORM)
            .join(PipelineRunORM, PipelineRunORM.dossier_id == DossierORM.id)
            .where(PipelineRunORM.id == run_id, PipelineRunORM.tenant_id == user.tenant_id)
        )
        dossier = result.scalar_one_or_none()
    if dossier is None or dossier.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not dossier_access_decision(
        action=AclAction.QUERY,
        principal=user,
        dossier_id=dossier.id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quyền xem hồ sơ này đã bị thu hồi.",
        )


@router.get(
    "/runs/{run_id}/events",
    summary="Server-Sent Events stream — real-time pipeline run updates",
    responses={
        200: {
            "description": "text/event-stream",
            "content": {"text/event-stream": {}},
        },
        403: {"description": "No read access to the run's dossier"},
        404: {"description": "Run not found"},
    },
)
async def stream_run_events(
    run_id: Annotated[str, Path(min_length=1)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    last_event_id_query: Annotated[int | None, Query(alias="last_event_id", ge=0)] = None,
) -> StreamingResponse:
    """Mở SSE stream cho 1 pipeline run.

    ``EventSource`` của trình duyệt không gửi được header ``Authorization``;
    frontend dùng client SSE chạy bằng ``fetch`` (vd. ``@microsoft/fetch-event-source``)
    để gửi Bearer token + ``X-Tenant-Id``, và gửi lại ``Last-Event-ID`` khi nối lại
    (hoặc ``?last_event_id=``).

    Events:
        run.started        — khi stream mở: trạng thái run/job hiện tại (không có id)
        run.status_changed — run đổi trạng thái (status, error_code)
        job.status_changed — job đổi trạng thái (status, error_code)
        step.changed       — 1 step S0..S10 đổi trạng thái
        run.completed      — run kết thúc → server đóng stream
        error              — lỗi server / run not found
        :heartbeat         — keep-alive mỗi 15s
    """
    after_id = _resume_id(last_event_id, last_event_id_query)
    session_factory = get_session_factory()
    await _require_run_readable(session_factory, user, run_id)
    return StreamingResponse(
        _stream_run_events(
            session_factory=session_factory,
            broker=get_run_event_broker(),
            tenant_id=user.tenant_id,
            run_id=run_id,
            after_id=after_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


__all__ = ["router", "stream_run_events"]
