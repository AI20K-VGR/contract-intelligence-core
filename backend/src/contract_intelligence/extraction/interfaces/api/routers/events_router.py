"""Server-Sent Events (SSE) endpoint cho real-time pipeline run updates.

DOC-05b §7 chiến lược Polling & Realtime — chuẩn bị SSE endpoint
``GET /runs/{id}/events`` để frontend có thể switch từ polling sang SSE
mà không cần đổi API contract.

Pattern:
    1. Client mở EventSource GET /runs/{id}/events
    2. Backend stream các event ``{"step": "S3", "status": "succeeded", ...}``
    3. Client đóng khi nhận event ``{"status": "succeeded"}`` hoặc ``"failed"``

Implementation:
    - Poll pipeline_step table mỗi 1-2 giây
    - Emit event khi step status thay đổi (so với snapshot trước)
    - Đóng stream khi run ở terminal state (succeeded/failed/cancelled)
    - Heartbeat mỗi 15 giây để giữ connection alive
"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.extraction.infrastructure.persistence.repository_impl import (
    PipelineRunRepositoryImpl,
)
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.persistence import get_async_session

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Events"])


# Heartbeat interval (seconds)
_HEARTBEAT_INTERVAL = 15.0


async def _stream_run_events(
    *,
    session: AsyncSession,
    tenant_id: str,
    run_id: str,
    poll_interval: float = 1.5,
) -> Any:
    """Async generator stream SSE events cho 1 pipeline run."""
    repo = PipelineRunRepositoryImpl(session, tenant_id)
    last_step_snapshot: dict[str, str] = {}
    last_status: str | None = None
    last_heartbeat = asyncio.get_event_loop().time()

    try:
        # Initial validation
        run = await repo.get(run_id)
        if run is None:
            yield _format_event(
                event="error",
                data={"error": "RUN_NOT_FOUND", "run_id": run_id},
            )
            return

        yield _format_event(
            event="run.started",
            data={
                "run_id": run.id,
                "dossier_id": run.dossier_id,
                "status": run.status.value,
                "pipeline_version": run.pipeline_version,
            },
        )

        while True:
            await asyncio.sleep(poll_interval)

            run = await repo.get(run_id)
            if run is None:
                yield _format_event(event="error", data={"error": "RUN_DELETED"})
                return

            # ── Emit step changes ───────────────────────────────────────
            steps: list[dict[str, Any]] = await repo.list_steps(run_id)
            for step in steps:
                step_key = step["step"]
                cur_status = step["status"]
                prev_status = last_step_snapshot.get(step_key)
                if prev_status != cur_status:
                    yield _format_event(
                        event="step.changed",
                        data={
                            "run_id": run_id,
                            "step": step_key,
                            "status": step["status"],
                            "attempt": step.get("attempt"),
                            "pages": step.get("pages"),
                            "duration_ms": step.get("duration_ms"),
                        },
                    )
                    last_step_snapshot[step_key] = step["status"]

            # ── Emit run status change ──────────────────────────────────
            current_status = run.status.value
            if last_status != current_status:
                yield _format_event(
                    event="run.status_changed",
                    data={
                        "run_id": run_id,
                        "status": current_status,
                        "error_code": None,  # PipelineRunORM doesn't carry it in get()
                    },
                )
                last_status = current_status

            # ── Heartbeat ───────────────────────────────────────────────
            now = asyncio.get_event_loop().time()
            if now - last_heartbeat >= _HEARTBEAT_INTERVAL:
                yield ":heartbeat\n\n"
                last_heartbeat = now

            # ── Terminal state — close stream ───────────────────────────
            if current_status in ("succeeded", "failed", "cancelled", "dead"):
                yield _format_event(
                    event="run.completed",
                    data={"run_id": run_id, "status": current_status},
                )
                return

    except asyncio.CancelledError:
        logger.info("sse.client_disconnected", run_id=run_id)
        raise
    except Exception as exc:
        logger.exception("sse.stream_error", run_id=run_id, error=str(exc))
        yield _format_event(
            event="error",
            data={"error": "INTERNAL", "message": str(exc)},
        )


def _format_event(*, event: str, data: dict[str, Any] | None = None) -> str:
    """Format SSE event chuẩn (text/event-stream)."""
    if data is None:
        return f"event: {event}\n\n"
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get(
    "/runs/{run_id}/events",
    summary="Server-Sent Events stream — real-time pipeline run updates",
    responses={
        200: {
            "description": "text/event-stream",
            "content": {"text/event-stream": {}},
        },
    },
)
async def stream_run_events(
    run_id: Annotated[str, Path(min_length=1)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> StreamingResponse:
    """Mở SSE stream cho 1 pipeline run.

    Client (frontend) dùng EventSource API:
        const es = new EventSource(`/api/v1/runs/${runId}/events`, {
            headers: { Authorization: `Bearer ${token}`, 'X-Tenant-Id': tenantId }
        });
        es.addEventListener('step.changed', e => updateUI(JSON.parse(e.data)));
        es.addEventListener('run.completed', e => closeStream());

    Events:
        run.started    — khi stream mở
        step.changed   — khi 1 step S0..S10 đổi trạng thái
        run.status_changed — khi run status đổi
        run.completed  — terminal state → đóng stream
        error          — lỗi server / run not found
        :heartbeat     — keep-alive mỗi 15s
    """
    return StreamingResponse(
        _stream_run_events(
            session=session,
            tenant_id=user.tenant_id,
            run_id=run_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


__all__ = ["router", "stream_run_events"]
