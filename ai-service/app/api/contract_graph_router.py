"""Signed, bounded internal read API for the persisted contract graph."""

from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import func, or_, select

from app.db.engine import database_url, ensure_database, get_engine
from app.db.tables import (
    contract_edges,
    contract_pair_relations,
    graph_write_receipts,
    jobs,
    query_snapshots,
)
from app.security.service_envelope import ServiceEnvelopeError, verify_service_envelope
from app.tools.contract_graph_read_model import (
    _citation_ref,
    graph_job_status,
    graph_read_status,
    project_operation_edge,
    project_pair_relation,
    validate_graph_cursor,
    validate_graph_kind,
)

router = APIRouter()


@router.get("/internal/contract-graph/{job_id}/evidence")
def read_contract_graph_evidence(
    job_id: str,
    dossier_id: str,
    snapshot_digest: str,
    graph_kind: str,
    node_id: str,
    citation_ref: str,
    x_ai2_service_envelope: str | None = Header(default=None),
) -> dict:
    """Return one citation quote after verifying the same signed graph scope.

    The ordinary graph projection intentionally contains opaque citation handles
    only. This separate endpoint is the narrow, auditable path for the UI to read
    source text after Backend has checked the caller's citation-read permission.
    """
    try:
        kind = validate_graph_kind(graph_kind)
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "GRAPH_KIND_INVALID"}) from exc
    request = {
        "job_id": job_id,
        "dossier_id": dossier_id,
        "snapshot_digest": snapshot_digest,
        "graph_kind": kind,
        "node_id": node_id,
        "citation_ref": citation_ref,
    }
    if not x_ai2_service_envelope:
        raise HTTPException(401, detail={"code": "SERVICE_ENVELOPE_MISSING"})
    try:
        envelope = verify_service_envelope(
            {**request, "service_envelope": json.loads(x_ai2_service_envelope)},
            required_scope="ai2.graph.read",
        )
    except (json.JSONDecodeError, ServiceEnvelopeError) as exc:
        raise HTTPException(401, detail={"code": getattr(exc, "code", "SERVICE_ENVELOPE_INVALID")}) from exc

    if not database_url():
        raise HTTPException(503, detail={"code": "GRAPH_EVIDENCE_UNAVAILABLE"})
    engine = get_engine()
    ensure_database(engine)
    with engine.connect() as cx:
        job = cx.execute(select(jobs).where(
            jobs.c.job_id == job_id,
            jobs.c.tenant_id == envelope.tenant_id,
            jobs.c.dossier_id == dossier_id,
            jobs.c.status == "SUCCEEDED",
        )).mappings().first()
        if job is None:
            raise HTTPException(404, detail={"code": "GRAPH_JOB_NOT_FOUND"})
        latest_job_id = cx.execute(select(jobs.c.job_id).where(
            jobs.c.tenant_id == envelope.tenant_id,
            jobs.c.dossier_id == dossier_id,
            jobs.c.status == "SUCCEEDED",
        ).order_by(jobs.c.created_ms.desc(), jobs.c.job_id.desc()).limit(1)).scalar_one_or_none()
        if latest_job_id != job_id:
            raise HTTPException(409, detail={"code": "AI2_GRAPH_STALE"})
        current_digest = cx.execute(select(query_snapshots.c.snapshot_digest).where(
            query_snapshots.c.tenant_id == envelope.tenant_id,
            query_snapshots.c.dossier_id == dossier_id,
        )).scalar_one_or_none()
        if current_digest != snapshot_digest:
            raise HTTPException(409, detail={"code": "AI2_GRAPH_STALE"})
        receipt = cx.execute(select(graph_write_receipts).where(
            graph_write_receipts.c.tenant_id == envelope.tenant_id,
            graph_write_receipts.c.dossier_id == dossier_id,
            graph_write_receipts.c.job_id == job_id,
            graph_write_receipts.c.graph_kind == kind,
            graph_write_receipts.c.source_snapshot_digest == snapshot_digest,
            graph_write_receipts.c.stage_status == "COMPLETED",
            graph_write_receipts.c.write_status == "COMMITTED",
        )).first()
        if receipt is None:
            raise HTTPException(404, detail={"code": "GRAPH_EVIDENCE_NOT_FOUND"})

        table = contract_edges if kind == "operation" else contract_pair_relations
        rows = cx.execute(select(table).where(
            table.c.tenant_id == envelope.tenant_id,
            table.c.dossier_id == dossier_id,
            table.c.job_id == job_id,
            table.c.source_snapshot_digest == snapshot_digest,
            or_(
                table.c.source_node_id == node_id,
                table.c.target_node_id == node_id,
            ) if kind == "operation" else or_(
                table.c.node_a_id == node_id,
                table.c.node_b_id == node_id,
            ),
        )).mappings().all()
        citation_fields = (
            (("source_node_id", "source_citation_json"), ("target_node_id", "target_citation_json"))
            if kind == "operation"
            else (("node_a_id", "citation_a_json"), ("node_b_id", "citation_b_json"))
        )
        for row in rows:
            for node_field, field in citation_fields:
                if row[node_field] != node_id:
                    continue
                raw = row[field]
                if _citation_ref(raw) != citation_ref:
                    continue
                citation = json.loads(raw)
                quote = citation.get("text_span") or citation.get("quote")
                if not isinstance(quote, str) or not quote.strip():
                    raise HTTPException(404, detail={"code": "GRAPH_EVIDENCE_NOT_FOUND"})
                return {
                    "job_id": job_id,
                    "snapshot_digest": snapshot_digest,
                    "graph_kind": kind,
                    "node_id": node_id,
                    "citation_ref": citation_ref,
                    "quote": quote[:20000],
                    "page": citation.get("page"),
                }
    raise HTTPException(404, detail={"code": "GRAPH_EVIDENCE_NOT_FOUND"})


@router.get("/internal/contract-graph/{job_id}")
def read_contract_graph(
    job_id: str,
    dossier_id: str,
    snapshot_digest: str,
    graph_kind: str = "operation",
    cursor: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    x_ai2_service_envelope: str | None = Header(default=None),
) -> dict:
    try:
        kind = validate_graph_kind(graph_kind)
        cursor = validate_graph_cursor(cursor, kind)
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "GRAPH_KIND_INVALID"}) from exc
    if not x_ai2_service_envelope:
        raise HTTPException(401, detail={"code": "SERVICE_ENVELOPE_MISSING"})
    try:
        raw_envelope = json.loads(x_ai2_service_envelope)
        envelope = verify_service_envelope(
            {"job_id": job_id, "dossier_id": dossier_id, "snapshot_digest": snapshot_digest,
             "graph_kind": kind, "cursor": cursor, "limit": limit, "service_envelope": raw_envelope},
            required_scope="ai2.graph.read",
        )
    except (json.JSONDecodeError, ServiceEnvelopeError) as exc:
        raise HTTPException(401, detail={"code": getattr(exc, "code", "SERVICE_ENVELOPE_INVALID")}) from exc

    if not database_url():
        return {"status": "UNAVAILABLE", "graph_kind": kind, "edges": [], "total_count": 0,
                "has_more": False, "next_cursor": None, "snapshot_digest": snapshot_digest}

    engine = get_engine()
    ensure_database(engine)
    with engine.connect() as cx:
        job = cx.execute(select(jobs).where(
            jobs.c.job_id == job_id,
            jobs.c.tenant_id == envelope.tenant_id,
            jobs.c.dossier_id == dossier_id,
        )).mappings().first()
        if job is None:
            raise HTTPException(404, detail={"code": "GRAPH_JOB_NOT_FOUND"})
        if job["status"] in {"QUEUED", "RUNNING"}:
            return {"status": "PENDING", "graph_kind": kind, "edges": [], "total_count": 0,
                    "has_more": False, "next_cursor": None, "snapshot_digest": snapshot_digest}
        if job["status"] != "SUCCEEDED":
            return {"status": graph_job_status(job["status"]), "graph_kind": kind, "edges": [], "total_count": 0,
                    "has_more": False, "next_cursor": None, "snapshot_digest": snapshot_digest}
        latest_job_id = cx.execute(select(jobs.c.job_id).where(
            jobs.c.tenant_id == envelope.tenant_id,
            jobs.c.dossier_id == dossier_id,
            jobs.c.status == "SUCCEEDED",
        ).order_by(jobs.c.created_ms.desc(), jobs.c.job_id.desc()).limit(1)).scalar_one_or_none()
        if latest_job_id != job_id:
            return {"status": "STALE", "graph_kind": kind, "edges": [], "total_count": 0,
                    "has_more": False, "next_cursor": None, "snapshot_digest": snapshot_digest}
        current_digest = cx.execute(select(query_snapshots.c.snapshot_digest).where(
            query_snapshots.c.tenant_id == envelope.tenant_id,
            query_snapshots.c.dossier_id == dossier_id,
        )).scalar_one_or_none()
        if current_digest != snapshot_digest:
            return {"status": "STALE", "graph_kind": kind, "edges": [], "total_count": 0,
                    "has_more": False, "next_cursor": None, "snapshot_digest": current_digest}
        receipt = cx.execute(select(graph_write_receipts).where(
            graph_write_receipts.c.tenant_id == envelope.tenant_id,
            graph_write_receipts.c.dossier_id == dossier_id,
            graph_write_receipts.c.job_id == job_id,
            graph_write_receipts.c.graph_kind == kind,
            graph_write_receipts.c.source_snapshot_digest == snapshot_digest,
        )).mappings().first()
        if receipt is None:
            return {"status": "PERSISTENCE_UNKNOWN", "graph_kind": kind, "edges": [], "total_count": 0,
                    "has_more": False, "next_cursor": None, "snapshot_digest": snapshot_digest}

        stage_status = receipt["stage_status"]
        write_status = receipt["write_status"]
        row_count = receipt["row_count"]
        status = graph_read_status(stage_status=stage_status, persistence_status=write_status, row_count=row_count)
        table = contract_edges if kind == "operation" else contract_pair_relations
        id_column = table.c.edge_id if kind == "operation" else table.c.relation_id
        where = (table.c.tenant_id == envelope.tenant_id) & (table.c.dossier_id == dossier_id) & (
            table.c.job_id == job_id) & (table.c.source_snapshot_digest == snapshot_digest)
        actual_count = cx.execute(select(func.count()).select_from(table).where(where)).scalar_one()
        if actual_count != row_count and status == "READY":
            status = "PERSISTENCE_UNKNOWN"
        if status != "READY":
            return {"status": status, "graph_kind": kind, "edges": [], "total_count": row_count,
                    "has_more": False, "next_cursor": None, "snapshot_digest": snapshot_digest,
                    "error_code": receipt["error_code"]}

        if cursor:
            where = where & (id_column > cursor)
        rows = cx.execute(select(table).where(where).order_by(id_column).limit(limit + 1)).mappings().all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        projector = project_operation_edge if kind == "operation" else project_pair_relation
        return {
            "status": status,
            "graph_kind": kind,
            "tenant_id": envelope.tenant_id,
            "dossier_id": dossier_id,
            "job_id": job_id,
            "snapshot_digest": snapshot_digest,
            "edges": [projector(row) for row in rows],
            "total_count": row_count,
            "has_more": has_more,
            "next_cursor": rows[-1]["edge_id" if kind == "operation" else "relation_id"] if has_more else None,
        }
