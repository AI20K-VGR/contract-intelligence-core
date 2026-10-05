"""Dossier Q&A query path: POST /dossiers/{id}/query and /ask."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.infrastructure.ai_adapters import AiAdapterError, query_ai2
from contract_intelligence.schemas.queries import (
    DossierQueryRequest,
    DossierQueryResponse,
    QueryHistoryItem,
)
from contract_intelligence.shared.acl import (
    AclAction,
    dossier_access_decision,
    dossier_denied_detail,
)
from contract_intelligence.shared.ai.persistence import load_ai2_read_model
from contract_intelligence.shared.ai.schemas import SemanticExtension
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.query_history import list_query_history, record_query_answer
from contract_intelligence.shared.query_policy import (
    QueryEndpoint,
    QueryLimitExceeded,
    enforce_query_limits,
    enforce_result_acl,
    save_query_trace,
    server_query_policy_flags,
)
from contract_intelligence.shared.responses import ApiMeta, ApiResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dossiers", tags=["Dossiers"], dependencies=[Depends(get_tenant_id)])

_QUERY_CONTRACT_VERSION = "ai2.query.v1"
_SNAPSHOT_VERSION = "latest"


def _acl_allows(user: AuthenticatedUser, dossier: DossierORM, action: AclAction) -> bool:
    return dossier_access_decision(
        action=action,
        principal=user,
        dossier_id=dossier.id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    )


async def _acl_check_dossier_access(
    session: AsyncSession,
    *,
    dossier_id: str,
    user: AuthenticatedUser,
) -> DossierORM:
    """Verify the dossier exists, is not tombstoned, and the caller may query it."""
    dossier = await session.scalar(
        select(DossierORM).where(DossierORM.id == dossier_id, DossierORM.deleted_at.is_(None))
    )
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Dossier {dossier_id} not found"},
        )
    if not _acl_allows(user, dossier, AclAction.QUERY):
        logger.warning(
            "dossiers.query.acl_denied",
            dossier_id=dossier_id,
            user_tenant=user.tenant_id,
            dossier_tenant=dossier.tenant_id,
            actor_id=user.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=dossier_denied_detail(
                action=AclAction.QUERY,
                principal=user,
                dossier_id=dossier.id,
                dossier_tenant_id=dossier.tenant_id,
                metadata=dossier.metadata_json,
            ),
        )
    return dossier


async def _dossier_document_ids(session: AsyncSession, dossier: DossierORM) -> set[str]:
    result = await session.execute(
        select(DocumentORM.id).where(
            DocumentORM.dossier_id == dossier.id,
            DocumentORM.tenant_id == dossier.tenant_id,
        )
    )
    return {str(value) for value in result.scalars().all()}


_ENDED_WITHOUT_RESULT = {"failed": "CURRENT_RUN_FAILED", "cancelled": "CURRENT_RUN_CANCELLED"}


def _no_semantic_result_coming(run: PipelineRunORM) -> str | None:
    """Why ``run`` can never get a semantic result, or None while one may still come.

    Mirrors the worker's semantic pin: a run frozen with ``semantic_profile:
    null`` (or not yet frozen while semantic is off) is legacy processing.
    """
    ended = _ENDED_WITHOUT_RESULT.get(run.status)
    if ended is not None:
        return ended
    try:
        config = json.loads(run.config_snapshot or "{}")
    except (TypeError, json.JSONDecodeError):
        config = {}
    if not isinstance(config, dict):
        config = {}
    if "semantic_profile" in config:
        return "SEMANTIC_DISABLED_FOR_RUN" if config["semantic_profile"] is None else None
    if os.getenv("AI2_SEMANTIC_ENABLED", "false").strip().casefold() != "true":
        return "SEMANTIC_DISABLED"
    return None


async def _semantic_result(session: AsyncSession, dossier: DossierORM) -> dict[str, Any]:
    """Current job owner is authoritative; a pending run never falls back to old data."""
    result: dict[str, Any] = {
        "dossier_id": dossier.id,
        "run_id": None,
        "result_digest": None,
        "state": "NOT_MEASURED",
        "reason": "CURRENT_RUN_ABSENT",
        "semantic_extension": None,
        "typed_table_projections": {"payment_schedules": [], "boq_checks": []},
    }
    job = await session.scalar(
        select(JobORM)
        .where(JobORM.dossier_id == dossier.id, JobORM.tenant_id == dossier.tenant_id)
        .order_by(JobORM.created_at.desc(), JobORM.id.desc())
        .limit(1)
    )
    if job is None or not job.current_run_id:
        return result
    result.update(run_id=job.current_run_id, state="NOT_READY", reason="CURRENT_RESULT_NOT_READY")
    run = await session.get(PipelineRunORM, job.current_run_id)
    if run is None or (run.tenant_id, run.dossier_id, run.job_id) != (
        dossier.tenant_id,
        dossier.id,
        job.id,
    ):
        raise HTTPException(409, detail={"code": "CURRENT_RUN_SCOPE_CONFLICT"})
    if not run.ai2_result_json:
        reason = _no_semantic_result_coming(run)
        if reason is not None:
            # No semantic result will ever land on this run: answer through
            # AI2 as before instead of blocking every question.
            result.update(state="NOT_MEASURED", reason=reason)
        return result
    try:
        loaded = await load_ai2_read_model(session, tenant_id=dossier.tenant_id, run_id=run.id)
        digest = hashlib.sha256(
            json.dumps(
                loaded.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        if digest != run.ai2_result_digest:
            raise ValueError("persisted result digest mismatch")
        result["result_digest"] = digest
        loaded_result = loaded.payload.get("result", {})
        typed = (
            loaded_result.get("index_contribution", {})
            .get("coverage", {})
            .get("typed_table_projections", {})
        )
        if isinstance(typed, dict):
            result["typed_table_projections"] = {
                "payment_schedules": [
                    item for item in typed.get("payment_schedules", []) if isinstance(item, dict)
                ],
                "boq_checks": [
                    item for item in typed.get("boq_checks", []) if isinstance(item, dict)
                ],
            }
        raw = loaded_result.get("semantic_extension")
        if raw is None:
            result.update(state="NOT_MEASURED", reason="LEGACY_EXTENSION_ABSENT")
            return result
        # Validate the persisted payload, then return the wire shape as stored.
        # ``model_dump`` would materialize optional Pydantic defaults and make
        # the FE see a different semantic result after a reload (for example,
        # omitted pair fields become ``null``/``[]``).  The digest and schema
        # validation above already protect the immutable payload, so preserve
        # its exact optional-field contract here.
        extension = SemanticExtension.model_validate(raw)
        config = json.loads(run.config_snapshot or "{}")
        if (extension.tenant_id, extension.dossier_id) != (
            dossier.tenant_id,
            dossier.id,
        ) or config.get("semantic_profile", {}).get("digest") != extension.profile_digest:
            raise ValueError("semantic owner/profile pin mismatch")
        allowed = await _dossier_document_ids(session, dossier)
        evidence = [
            e
            for frame in extension.frames
            for e in [*frame.evidence, *(e for slot in frame.slots.values() for e in slot.evidence)]
        ]
        evidence.extend(
            e for pair in extension.pairs for e in [*pair.left_evidence, *pair.right_evidence]
        )
        evidence.extend(
            e
            for edge in extension.timeline
            for e in [
                *edge.evidence,
                *(edge.acceptance.evidence if edge.acceptance else []),
                *(edge.proposed_value.evidence if edge.proposed_value else []),
            ]
        )
        if any(
            e.document_id not in allowed or e.citation.source_file_id != e.document_id
            for e in evidence
        ):
            raise ValueError("semantic source outside dossier")
        result.update(state="NEEDS_REVIEW", reason=None, semantic_extension=raw)
    except (ValidationError, ValueError, TypeError, LookupError) as exc:
        raise HTTPException(409, detail={"code": "SEMANTIC_RESULT_INVALID"}) from exc
    return result


def _semantic_query(result: dict[str, Any], query: str) -> dict[str, Any]:
    extension = result["semantic_extension"]
    trace = {
        "code": "PINNED_SEMANTIC_QUERY",
        "run_id": result["run_id"],
        "result_digest": result["result_digest"],
    }
    if extension is None:
        return {
            "state": "BLOCKED",
            "answer": "",
            "citations": [],
            "retrieval_layer": {"selected": "PERSISTED_SEMANTIC", "run_id": result["run_id"]},
            "reasoning_trace": [{**trace, "reason": result["reason"]}],
        }
    tokens = {token for token in re.findall(r"\w+", query.casefold()) if len(token) >= 2}
    selected = [
        frame
        for frame in extension["frames"]
        if any(
            token in " ".join(e["raw"] for e in frame["evidence"]).casefold() for token in tokens
        )
    ]
    evidence = [
        e
        for frame in selected
        for e in frame["evidence"]
        if e["citation"]["validation_status"] == "VALID"
    ]
    return {
        "state": "NEEDS_REVIEW" if evidence else "INSUFFICIENT_EVIDENCE",
        "answer": "\n".join(dict.fromkeys(e["raw"] for e in evidence)),
        "citations": [e["citation"] for e in evidence],
        "retrieval_layer": {
            "selected": "PERSISTED_SEMANTIC",
            "run_id": result["run_id"],
            "profile_digest": extension["profile_digest"],
            "alias_version": extension["alias_version"],
        },
        "reasoning_trace": [trace],
    }


async def _ensure_current_semantic_run(
    session: AsyncSession, dossier: DossierORM, result: dict[str, Any]
) -> None:
    current = await session.scalar(
        select(JobORM.current_run_id)
        .where(JobORM.dossier_id == dossier.id, JobORM.tenant_id == dossier.tenant_id)
        .order_by(JobORM.created_at.desc(), JobORM.id.desc())
        .limit(1)
    )
    if current != result["run_id"]:
        raise HTTPException(409, detail={"code": "CURRENT_RUN_CHANGED"})


@router.get("/{id}/semantic-results", response_model=ApiResponse[dict[str, Any]])
async def semantic_results(
    id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:  # noqa: A002
    dossier = await _acl_check_dossier_access(session, dossier_id=id, user=user)
    if not _acl_allows(user, dossier, AclAction.CITATION_READ):
        raise HTTPException(403, detail={"code": "CITATION_ACCESS_DENIED"})
    result = await _semantic_result(session, dossier)
    await session.refresh(dossier)
    if dossier.deleted_at is not None or not _acl_allows(user, dossier, AclAction.CITATION_READ):
        raise HTTPException(403, detail={"code": "CITATION_ACCESS_DENIED"})
    await _ensure_current_semantic_run(session, dossier, result)
    return ApiResponse(data=result)


async def _run_dossier_query(
    *,
    endpoint: QueryEndpoint,
    dossier_id: str,
    body: DossierQueryRequest,
    session: AsyncSession,
    user: AuthenticatedUser,
) -> DossierQueryResponse:
    dossier = await _acl_check_dossier_access(session, dossier_id=dossier_id, user=user)

    try:
        await enforce_query_limits(session, tenant_id=user.tenant_id, actor_id=user.user_id)
    except QueryLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": exc.code, "message": exc.message},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    metadata = dossier.metadata_json if isinstance(dossier.metadata_json, dict) else {}
    snapshot_digest = str(metadata.get("ai2_snapshot_digest") or dossier.checksum or "").strip()
    ai2_payload: dict[str, Any] = {
        "query": body.query,
        "dossier_id": dossier_id,
        "snapshot_version": _SNAPSHOT_VERSION,
        "snapshot_digest": snapshot_digest,
        "query_contract_version": _QUERY_CONTRACT_VERSION,
        "acl_context": user.user_id,
        "policy_flags": server_query_policy_flags(),
        "tenant_id": user.tenant_id,
        "actor_id": user.user_id,
    }
    trace_fields: dict[str, Any] = {
        "tenant_id": user.tenant_id,
        "dossier_id": dossier_id,
        "actor_id": user.user_id,
        "endpoint": endpoint,
        "query": body.query,
        "snapshot_version": _SNAPSHOT_VERSION,
        "snapshot_digest": snapshot_digest,
        "query_contract_version": _QUERY_CONTRACT_VERSION,
    }

    started = time.monotonic()
    try:
        semantic = await _semantic_result(session, dossier)
        if semantic["semantic_extension"] is not None or semantic["state"] == "NOT_READY":
            ai2_raw = _semantic_query(semantic, body.query)
        else:
            ai2_raw = await query_ai2(ai2_payload)
    except AiAdapterError as exc:
        logger.error("dossiers.query.ai2_failed", dossier_id=dossier_id, error=str(exc))
        await save_query_trace(
            session,
            **trace_fields,
            state=None,
            citations=[],
            acl=None,
            error_code="AI2_QUERY_FAILED",
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "AI2_QUERY_FAILED", "message": str(exc)},
        ) from exc
    latency_ms = int((time.monotonic() - started) * 1000)

    # Access may have been revoked while AI2 was answering.
    await session.refresh(dossier)
    if semantic["semantic_extension"] is not None or semantic["state"] == "NOT_READY":
        await _ensure_current_semantic_run(session, dossier, semantic)
    filtered, acl = enforce_result_acl(
        ai2_raw if isinstance(ai2_raw, dict) else {},
        can_read_citations=dossier.deleted_at is None
        and _acl_allows(user, dossier, AclAction.CITATION_READ),
        allowed_document_ids=await _dossier_document_ids(session, dossier),
    )
    citations = list(filtered.get("citations") or [])
    answer = str(filtered.get("answer") or "")
    trace = await save_query_trace(
        session,
        **trace_fields,
        state=str(filtered.get("state") or "ok"),
        citations=citations,
        acl=acl,
        latency_ms=latency_ms,
    )
    # Same transaction as the trace: history survives restarts with its answer.
    record_query_answer(session, trace, answer)
    if acl.decision != "passed":
        logger.warning(
            "dossiers.query.acl_second_pass",
            dossier_id=dossier_id,
            actor_id=user.user_id,
            decision=acl.decision,
            dropped=acl.dropped,
        )
    return DossierQueryResponse(
        state=str(filtered.get("state") or "ok"),
        answer=answer,
        citations=citations,
        retrieval_layer=dict(filtered.get("retrieval_layer") or {}),
        reasoning_trace=list(filtered.get("reasoning_trace") or []),
        trace_id=trace.id,
        acl_decision=acl.decision,
    )


_QUERY_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"description": "X-Tenant-Id header missing"},
    403: {"description": "ACL denied — tenant mismatch"},
    404: {"description": "Dossier not found"},
    429: {"description": "Rate limit or tenant quota exceeded"},
    502: {"description": "AI2 query failed"},
}


@router.post(
    "/{id}/query",
    status_code=status.HTTP_200_OK,
    response_model=DossierQueryResponse,
    summary="Query dossier via AI2 (ACL + quota + QueryTrace + ACL on citations)",
    responses=_QUERY_RESPONSES,
)
async def query_dossier(
    id: str,  # noqa: A002 — path param name per API contract
    body: DossierQueryRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> DossierQueryResponse:
    return await _run_dossier_query(
        endpoint="query", dossier_id=id, body=body, session=session, user=user
    )


@router.post(
    "/{id}/ask",
    status_code=status.HTTP_200_OK,
    response_model=DossierQueryResponse,
    summary="Ask a question about the dossier (same policy chain as /query)",
    responses=_QUERY_RESPONSES,
)
async def ask_dossier(
    id: str,  # noqa: A002 — path param name per API contract
    body: DossierQueryRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> DossierQueryResponse:
    return await _run_dossier_query(
        endpoint="ask", dossier_id=id, body=body, session=session, user=user
    )


@router.get(
    "/{id}/queries",
    response_model=ApiResponse[list[QueryHistoryItem]],
    summary="Lịch sử hỏi đáp trên hồ sơ (mới nhất trước)",
    responses={
        403: {"description": "No read access, or scope=all without being owner/administrator"},
        404: {"description": "Dossier not found"},
    },
)
async def list_dossier_queries(
    id: str,  # noqa: A002 — path param name per API contract
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    scope: Annotated[Literal["mine", "all"], Query()] = "mine",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[QueryHistoryItem]]:
    """Câu hỏi, câu trả lời và trích dẫn đã lưu.

    Mặc định chỉ lịch sử của chính người gọi. ``scope=all`` (mọi người hỏi trên
    hồ sơ) chỉ cho chủ hồ sơ hoặc ADMINISTRATOR. Cần quyền xem hồ sơ; quyền chia
    sẻ hết hạn thì 403 như mọi API khác.
    """
    dossier = await _acl_check_dossier_access(session, dossier_id=id, user=user)
    actor_filter: str | None = user.user_id
    if scope == "all":
        metadata = dossier.metadata_json if isinstance(dossier.metadata_json, dict) else {}
        if user.role != "ADMINISTRATOR" and metadata.get("created_by") != user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ACL_DENIED",
                    "message": "Chỉ chủ hồ sơ hoặc quản trị viên xem được lịch sử của mọi người.",
                },
            )
        actor_filter = None
    items, total = await list_query_history(
        session,
        tenant_id=user.tenant_id,
        dossier_id=id,
        actor_id=actor_filter,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        data=[QueryHistoryItem.model_validate(item) for item in items],
        meta=ApiMeta(page=(offset // limit) + 1, page_size=limit, total=total),
    )
