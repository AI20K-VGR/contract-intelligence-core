"""HITL dossier approval + Q&A query path endpoints."""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.infrastructure.ai_adapters import AiAdapterError, query_ai2
from contract_intelligence.schemas.queries import DossierQueryRequest, DossierQueryResponse
from contract_intelligence.shared.acl import AclAction, dossier_access_decision
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.persistence import get_async_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dossiers", tags=["Dossiers"])

# Simulated QueryTrace audit log (stands in for a PostgreSQL table in Sprint 2).
_QUERY_TRACES: list[dict[str, Any]] = []


def reset_query_traces() -> None:
    """Test helper — clear simulated QueryTrace rows."""
    _QUERY_TRACES.clear()


def list_query_traces() -> list[dict[str, Any]]:
    """Return a copy of simulated QueryTrace rows (newest last)."""
    return list(_QUERY_TRACES)


def _simulate_save_query_trace(
    *,
    dossier_id: str,
    actor_id: str,
    tenant_id: str,
    query: str,
    snapshot_version: str,
    citations: list[Any],
    ai2_state: str,
) -> dict[str, Any]:
    """Persist a QueryTrace audit record (simulated PostgreSQL write)."""
    trace = {
        "id": new_ulid("qtr_"),
        "dossier_id": dossier_id,
        "actor_id": actor_id,
        "tenant_id": tenant_id,
        "snapshot_version": snapshot_version,
        "query": query,
        "citations": citations,
        "ai2_state": ai2_state,
        "created_at": utcnow().isoformat(),
    }
    _QUERY_TRACES.append(trace)
    logger.info(
        "dossiers.query.trace_saved",
        trace_id=trace["id"],
        dossier_id=dossier_id,
        actor_id=actor_id,
        snapshot_version=snapshot_version,
        citation_count=len(citations),
    )
    return trace


async def _acl_check_dossier_access(
    session: AsyncSession,
    *,
    dossier_id: str,
    user: AuthenticatedUser,
) -> DossierORM:
    """Verify the dossier exists and the caller's tenant may access it."""
    dossier = await session.get(DossierORM, dossier_id)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Dossier {dossier_id} not found"},
        )
    if not dossier_access_decision(
        action=AclAction.QUERY,
        principal=user,
        dossier_id=dossier_id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    ):
        logger.warning(
            "dossiers.query.acl_denied",
            dossier_id=dossier_id,
            user_tenant=user.tenant_id,
            dossier_tenant=dossier.tenant_id,
            actor_id=user.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACL_DENIED", "message": "Dossier access denied"},
        )
    return dossier


@router.post(
    "/{id}/query",
    status_code=status.HTTP_200_OK,
    response_model=DossierQueryResponse,
    summary="Query dossier via AI2 (ACL check + QueryTrace)",
    responses={
        403: {"description": "ACL denied — tenant mismatch"},
        404: {"description": "Dossier not found"},
        502: {"description": "AI2 query failed"},
    },
)
async def query_dossier(
    id: str,  # noqa: A002 — path param name per API contract
    body: DossierQueryRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> DossierQueryResponse:
    """ACL-gated Q&A: forward to AI2 ``/query`` and persist a QueryTrace."""
    dossier = await _acl_check_dossier_access(session, dossier_id=id, user=user)

    snapshot_version = "latest"
    metadata = dossier.metadata_json if isinstance(dossier.metadata_json, dict) else {}
    snapshot_digest = str(metadata.get("ai2_snapshot_digest") or dossier.checksum or "").strip()
    ai2_payload: dict[str, Any] = {
        "query": body.query,
        "dossier_id": id,
        "snapshot_version": snapshot_version,
        "snapshot_digest": snapshot_digest,
        "query_contract_version": "ai2.query.v1",
        "acl_context": "operator",
        "policy_flags": body.policy_flags,
        "tenant_id": user.tenant_id,
        "actor_id": "backend",
    }

    try:
        ai2_raw = await query_ai2(ai2_payload)
    except AiAdapterError as exc:
        logger.error("dossiers.query.ai2_failed", dossier_id=id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "AI2_QUERY_FAILED", "message": str(exc)},
        ) from exc

    response = DossierQueryResponse(
        state=str(ai2_raw.get("state") or "ok"),
        answer=str(ai2_raw.get("answer") or ""),
        citations=list(ai2_raw.get("citations") or []),
        retrieval_layer=dict(ai2_raw.get("retrieval_layer") or {}),
        reasoning_trace=list(ai2_raw.get("reasoning_trace") or []),
    )

    _simulate_save_query_trace(
        dossier_id=id,
        actor_id=user.user_id,
        tenant_id=user.tenant_id,
        query=body.query,
        snapshot_version=snapshot_version,
        citations=response.citations,
        ai2_state=response.state,
    )
    return response
