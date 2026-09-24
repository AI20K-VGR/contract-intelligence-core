from __future__ import annotations

import json
import hashlib
import logging
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.contracts.models import AuthContext, HandoffIssue, JobResult, JobStatus, ReviewItem, ReviewState, ToolEnvelope
from app.contracts.wire import BeAi2ProcessingRequest, job_result_to_wire
from app.compat_legacy import cancel_job as cancel_legacy_job
from app.compat_legacy import create_completed_job, create_failed_job, get_job as get_legacy_job
from app.llm.client import NineRouterClient
from app.llm.embeddings import OpenAICompatibleEmbeddingClient
from app.pipeline.ai1_ingest import ingest_files
from app.pipeline.ai1_snapshot_adapter import (
    SnapshotContractError,
    adapt_ai1_input,
    adapt_ai1_result_v01,
    adapt_be_ai2_processing_request,
)
from app.pipeline.citations import CitationResolver
from app.pipeline.grounding import repair_active_nodes
from app.pipeline.idp import run_idp
from app.pipeline.outline import build_tree, locate
from app.pipeline.ocr_json_demo_adapter import is_ocr_json_demo, normalize_ocr_json
from app.pipeline.runtime import ProcessingRuntime
from app.reasoning.gold import adhoc_tasks, tasks_from_outline
from app.reasoning.query import QueryRouter, classify_ask
from app.reasoning.relations import build_relation_graph
from app.reasoning.stack import FourLayerReasoner
from app.reasoning.vector_recall import VectorRecallService
from app.security.service_envelope import ServiceEnvelopeError, verify_service_envelope
from app.tools.gateway import ToolGateway
from app.tools.jobs import JobNonceReplayConflict, JobOwnershipConflict, JobPayloadConflict, SQLiteJobStore
from app.tools.persist import DATA, load_session, save_session
from app.tools.store import DossierRecord, InMemorySnapshotStore
from fixtures.case_pdf import attach_case_pdf
from fixtures.catalog import load_case
from fixtures.eval_suite import all_eval_cases

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

STATIC = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="VSF AI2 IDP", version="0.1.0")
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

STORE = InMemorySnapshotStore()
logger = logging.getLogger(__name__)
JOBS: dict[str, JobResult] = {}
WIRE_JOBS: dict[str, dict] = {}
WIRE_IDEMPOTENCY: dict[tuple[str, str, int], str] = {}
JOB_STORE = SQLiteJobStore()
LAST_CASE: dict[str, str] = {}
SESSIONS: dict[str, dict] = {}
EMBEDDING_CLIENT = OpenAICompatibleEmbeddingClient()
VECTOR_RECALL = VectorRecallService(embedding_client=EMBEDDING_CLIENT)


def _hydrate_store_from_jobs() -> int:
    """Restore queryable canonical records after an AI2 process restart.

    The durable job store keeps the full Backend -> AI2 request, including
    snapshots.  Rebuilding the in-memory query index from successful jobs
    prevents a restart from turning completed dossiers into false evidence
    gaps.  Jobs are ordered oldest-first so the newest retry wins.
    """

    restored = 0
    for job in JOB_STORE.list_succeeded():
        payload = job.get("request")
        if not isinstance(payload, dict):
            continue
        try:
            _request, adapted = adapt_be_ai2_processing_request(
                payload,
                tenant_id=str(job.get("tenant_id") or ""),
                actor_id=str(
                    (payload.get("service_envelope") or {}).get("actor_id") or "backend"
                ),
            )
        except Exception as exc:  # pragma: no cover - corrupt historical job
            logger.warning(
                "ai2.store_hydration_skipped job_id=%s dossier_id=%s error=%s",
                job.get("job_id"),
                job.get("dossier_id"),
                exc,
            )
            continue
        STORE.put(adapted.record)
        restored += 1
    if restored:
        logger.info("ai2.store_hydrated dossiers=%s", restored)
    return restored


@app.on_event("startup")
def hydrate_canonical_store() -> None:
    _hydrate_store_from_jobs()


class RunBody(BaseModel):
    use_llm: bool = True


class ReasonBody(BaseModel):
    task_id: str
    use_llm: bool = True
    use_vector: bool = False


class AskBody(BaseModel):
    query: str
    use_llm: bool = True
    use_vector: bool = False


class ReviewBody(BaseModel):
    candidate_id: str
    action: str
    reason: str = ""
    overlay_text: str | None = None


class PublishBody(BaseModel):
    confirm: bool = False


def _queued_wire_result(request: BeAi2ProcessingRequest, job_id: str) -> dict:
    return {
        "schema_version": "ai2.be.processing.result.v1",
        "request_id": request.request_id,
        "idempotency_key": request.idempotency_key,
        "attempt": request.attempt,
        "job_id": job_id,
        "status": "QUEUED",
        "review_state": None,
        "input_snapshots": [item.model_dump() for item in request.snapshot_identities],
        "result": None,
        "errors": [],
    }


def _run_wire_job(job_id: str, payload: dict) -> None:
    """Execute one accepted wire request and retain its public result."""

    try:
        service_envelope = verify_service_envelope(payload)
        request, adapted = adapt_be_ai2_processing_request(
            payload,
            tenant_id=service_envelope.tenant_id,
            actor_id=service_envelope.actor_id,
        )
        tenant_id = request.service_envelope.tenant_id
        worker_token = JOB_STORE.claim(
            job_id,
            tenant_id=tenant_id,
            dossier_id=request.dossier_id,
        )
        if worker_token is None:
            return
        queued = WIRE_JOBS.get(job_id) or JOB_STORE.get(job_id)
        if queued is not None:
            wire = dict(queued.get("wire") if "wire" in queued else queued)
            wire["status"] = "RUNNING"
            WIRE_JOBS[job_id] = wire
            JOB_STORE.set_wire(
                job_id,
                tenant_id=tenant_id,
                dossier_id=request.dossier_id,
                worker_token=worker_token,
                status="RUNNING",
                wire=wire,
            )
        llm = None
        if request.policy_flags.egress_allowed:
            candidate = NineRouterClient()
            if candidate.configured():
                llm = candidate
        runtime = ProcessingRuntime(
            egress_allowed=request.policy_flags.egress_allowed,
            use_vector=request.policy_flags.use_vector,
            max_processing_seconds=request.policy_flags.budget_limits.max_processing_seconds,
            max_llm_calls=request.policy_flags.budget_limits.max_llm_calls,
            max_embedding_tokens=request.policy_flags.budget_limits.max_embedding_tokens,
        )
        # The request policy controls whether the configured NineRouter client
        # can be used. The pipeline itself owns retry/fallback accounting.
        result = run_idp(
            adapted.record,
            adapted.envelope,
            llm=llm,
            store=STORE,
            job_id=job_id,
            runtime=runtime,
        )
        JOBS[job_id] = result
        wire = job_result_to_wire(result, request)
        WIRE_JOBS[job_id] = wire
        JOB_STORE.set_wire(
            job_id,
            tenant_id=tenant_id,
            dossier_id=request.dossier_id,
            worker_token=worker_token,
            status=wire["status"],
            wire=wire,
            result=result.model_dump(),
        )
    except SnapshotContractError as exc:
        current = WIRE_JOBS.get(job_id) or {}
        wire = {
            **current,
            "status": "FAILED",
            "review_state": "BLOCKED",
            "result": None,
            "errors": [{"code": exc.code, "message": str(exc), "retryable": False}],
        }
        WIRE_JOBS[job_id] = wire
        if "worker_token" in locals():
            JOB_STORE.set_wire(
                job_id,
                tenant_id=request.service_envelope.tenant_id if "request" in locals() else "",
                dossier_id=request.dossier_id if "request" in locals() else "",
                worker_token=worker_token,
                status="FAILED",
                wire=wire,
            )
    except Exception as exc:  # pragma: no cover - defensive worker boundary
        current = WIRE_JOBS.get(job_id) or {}
        wire = {
            **current,
            "status": "FAILED",
            "review_state": "BLOCKED",
            "result": None,
            "errors": [{"code": "AI2_WORKER_FAILED", "message": str(exc), "retryable": False}],
        }
        WIRE_JOBS[job_id] = wire
        if "worker_token" in locals():
            JOB_STORE.set_wire(
                job_id,
                tenant_id=request.service_envelope.tenant_id if "request" in locals() else "",
                dossier_id=request.dossier_id if "request" in locals() else "",
                worker_token=worker_token,
                status="FAILED",
                wire=wire,
            )


@app.get("/")
def index():
    page = STATIC / "index.html"
    if not page.exists():
        raise HTTPException(404, "demo UI missing")
    return FileResponse(page)


def _session_view(sid: str) -> dict:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, sid)
    rec: DossierRecord = s["record"]
    evidence_nodes = rec.evidence_nodes()
    job = s.get("job")
    contrib = None
    if job and job.contribution:
        contrib = job.contribution.model_dump()
        facts = list(contrib.get("facts") or [])
        facts.sort(
            key=lambda f: (
                0 if f.get("item_key") else 1,
                0 if f.get("normalized_value") else 1,
            )
        )
        contrib["facts"] = facts[:80]
        contrib["chunks"] = (contrib.get("chunks") or [])[:40]
        contrib["candidates"] = contrib.get("candidates") or []
    table_coverage_counts: dict[str, int] = {}
    for page in rec.pages:
        key = page.table_coverage.value
        table_coverage_counts[key] = table_coverage_counts.get(key, 0) + 1
    graph = rec.relation_graph
    return {
        "session_id": sid,
        "filename": s["filename"],
        "source": s["source"],
        "step": s["step"],
        "ai1": s["ai1"],
        "files": [f.model_dump() for f in (rec.source_files or [])],
        "has_pdf": bool(s.get("blobs")),
        "dossier_id": rec.dossier_id,
        "tenant_id": rec.tenant_id,
        "lifecycle": rec.lifecycle.value,
        "pins": rec.pins.model_dump(),
        "n_pages": len(rec.pages),
        "n_nodes": len(evidence_nodes),
        "n_raw_nodes": len(rec.nodes),
        "n_tables": len(rec.tables),
        "table_coverage": table_coverage_counts,
        "relation_graph": {
            "n_nodes": len(graph.nodes) if graph else 0,
            "n_edges": len(graph.edges) if graph else 0,
            "n_issues": len(graph.issues) if graph else 0,
        },
        "pages": [
            {
                "page": p.page_number,
                "quality": p.quality,
                "coverage": p.coverage,
                "table_coverage": p.table_coverage.value,
                "text": p.text[:900],
                "page_revision_id": p.page_revision_id,
            }
            for p in rec.pages[:12]
        ],
        "n_pages_hidden": max(0, len(rec.pages) - 12),
        "nodes": [
            {
                "node_id": n.node_id,
                "type": n.type,
                "raw_label": n.raw_label,
                "page_range": n.page_range,
                "structured_key": n.structured_key,
                "structured_value": n.structured_value,
            }
            for n in evidence_nodes[:40]
        ],
        "n_nodes_hidden": max(0, len(evidence_nodes) - 40),
        "tree": build_tree(evidence_nodes),
        "tables": [
            {
                "table_id": t.table_id,
                "title": t.title,
                "n_rows": len(t.rows),
                "header": t.header,
                "first_rows": t.rows[:2],
                "last_rows": t.rows[-2:] if len(t.rows) > 2 else t.rows,
            }
            for t in rec.tables[:8]
        ],
        "extracted": bool(s.get("job")),
        "job": job.model_dump() if job else None,
        "contribution": contrib,
        "used_llm": s.get("used_llm", False),
        "has_gold_tasks": s.get("gold", False),
        "reviews": s.get("reviews") or {},
        "reviews_stale": bool(s.get("reviews_stale")),
        "published": bool(s.get("published")),
        "authoritative_publish_blocked": bool(s.get("authoritative_publish_blocked")),
        "review_queue_status": "NOT_RUN" if job is None else ("EMPTY_QUEUE" if not rec.review_items else "HAS_REVIEW_ITEMS"),
        "review_items": [item.model_dump() for item in rec.review_items[:160]],
        "n_review_items": len(rec.review_items),
        "n_citations": len(rec.citation_index),
        "handoff_issues": [issue.model_dump() for issue in rec.handoff_issues],
        "policy": _policy_view(rec),
    }


def _open_session(
    record: DossierRecord,
    envelope: ToolEnvelope,
    filename: str,
    source: str,
    ai1: dict,
    blobs: dict[str, bytes] | None = None,
    gold: bool = False,
) -> dict:
    sid = uuid4().hex[:12]
    active_nodes, repair_issues = repair_active_nodes(record)
    record.active_nodes = active_nodes
    if repair_issues:
        record.handoff_issues = [*record.handoff_issues, *repair_issues]
    STORE.put(record)
    SESSIONS[sid] = {
        "record": record,
        "envelope": envelope,
        "filename": filename,
        "source": source,
        "step": "reconstruct",
        "ai1": ai1,
        "job": None,
        "used_llm": False,
        "blobs": blobs or {},
        "gold": gold,
        "reviews": {},
        "review_basis": _review_basis(record),
        "reviews_stale": False,
        "published": False,
        "authoritative_publish_blocked": source == "ai1_result" and bool(ai1.get("review_required", True)),
    }
    save_session(sid, SESSIONS[sid], STORE)
    return _session_view(sid)


def _review_basis(record: DossierRecord) -> dict[str, object]:
    """Pin the evidence/profile basis on which review overlays were made."""

    return {
        "source_snapshot_digest": record.pins.source_snapshot_digest,
        "tenant_profile_version": record.pins.tenant_profile_version,
        "policy_version": record.pins.policy_version,
        "extraction_version": record.pins.extraction_version,
    }


def _require_session(session_id: str) -> dict:
    s = SESSIONS.get(session_id)
    if s:
        return s
    loaded = load_session(session_id, STORE)
    if not loaded:
        raise HTTPException(404, session_id)
    SESSIONS[session_id] = loaded
    return loaded


def _vector_service(
    use_vector: bool,
    runtime: ProcessingRuntime | None = None,
) -> VectorRecallService:
    """Build a request-scoped vector service when a runtime budget is present."""

    if not use_vector:
        return VectorRecallService(enabled=False)
    if runtime is None:
        return VECTOR_RECALL
    return VectorRecallService(
        embedding_client=EMBEDDING_CLIENT,
        enabled=VECTOR_RECALL.enabled,
        runtime=runtime,
    )


def _policy_view(rec: DossierRecord) -> dict:
    gates = []
    if rec.processing_budget_hit():
        gates.append({
            "code": "PROCESSING_BUDGET_EXCEEDED",
            "operation": "external_processing",
            "deterministic_action": "ALLOW_PARTIAL_REVIEW",
        })
    if rec.embedding_budget_hit():
        gates.append({
            "code": "EMBEDDING_BUDGET_EXCEEDED",
            "operation": "embedding_vector_recall",
            "deterministic_action": "ALLOW_WITHOUT_VECTOR",
        })
    if not rec.egress_approved:
        gates.append({
            "code": "EGRESS_DENIED",
            "operation": "llm_or_embedding",
            "deterministic_action": "ALLOW_LOCAL_ONLY",
        })
    if rec.index_status == "LEASED":
        gates.append({
            "code": "INDEX_LEASED",
            "operation": "publish_or_index_write",
            "deterministic_action": "BLOCK",
        })
    return {
        "deterministic": "ALLOW" if rec.index_status != "LEASED" else "BLOCKED",
        "external": "BLOCKED" if gates else "ALLOWED",
        "gates": gates,
    }


def _reason_output(
    rec: DossierRecord,
    env: ToolEnvelope,
    task: dict,
    *,
    use_llm: bool,
    use_vector: bool,
    runtime: ProcessingRuntime | None = None,
) -> dict:
    policy = _policy_view(rec)
    llm_gate = rec.index_status == "LEASED" or rec.processing_budget_hit() or not rec.egress_approved
    if use_llm and llm_gate:
        return {
            "review_state": ReviewState.BLOCKED.value,
            "answer": None,
            "citations": [],
            "layers_used": ["POLICY"],
            "relation_edges": [],
            "relation_issues": [],
            "retrieval_trace": {"vector_status": "NOT_REQUESTED"},
            "locations": [],
            "used_llm": False,
            "use_vector": use_vector,
            "policy": policy,
            "blocked_reason": "external policy gate is not satisfied",
        }
    llm = NineRouterClient() if use_llm else None
    if llm and not llm.configured():
        llm = None
    llm_trace_count = len(llm.traces) if llm is not None else 0
    gw = ToolGateway(STORE)
    out = FourLayerReasoner(
        gw,
        llm,
        vector_recall=_vector_service(use_vector, runtime),
    ).run(env, task)
    # Reasoning resolves citations through the active tree, while an AI1
    # result also has a source citation registry with quote/hash validation.
    # Join the two here so every answer can expose the stable citation_id and
    # the UI can verify the exact source line instead of displaying a
    # best-effort node location only.
    out["citations"] = _enrich_citations(out.get("citations") or [], rec)
    trace = dict(out.get("retrieval_trace") or {})
    if not use_vector:
        trace["vector_status"] = "NOT_REQUESTED"
    out["retrieval_trace"] = trace
    locations = []
    for citation in out.get("citations") or []:
        node_id = citation.get("node_id") if isinstance(citation, dict) else None
        if node_id:
            loc = locate(rec.evidence_nodes(), rec.pages, node_id)
            if loc:
                locations.append(loc)
    return {
        **out,
        "locations": locations,
        # ``use_llm`` enables the client; ``used_llm`` means that at least
        # one completion was actually sent. L0-only questions must not claim
        # that a model answered them.
        "used_llm": bool(llm and len(llm.traces) > llm_trace_count),
        "use_vector": use_vector,
        "policy": policy,
    }


def _enrich_citations(citations: list[dict], rec: DossierRecord) -> list[dict]:
    by_node: dict[str, list] = {}
    for citation in rec.citation_index.values():
        by_node.setdefault(citation.node_id, []).append(citation)

    metadata_defaults = {"citation_id", "source_hash", "quote_sha256", "validation_status"}
    enriched: list[dict] = []
    for raw in citations:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("node_id") or raw.get("id") or "")
        candidates = by_node.get(node_id, [])
        chosen = None
        supplied_span = str(raw.get("text_span") or "")
        for candidate in candidates:
            if supplied_span and supplied_span in candidate.text_span:
                chosen = candidate
                break
        if chosen is None and len(candidates) == 1:
            chosen = candidates[0]
        if chosen is None and candidates:
            chosen = candidates[0]
        merged = chosen.model_dump() if chosen is not None else {}
        for key, value in raw.items():
            # Do not overwrite a verified registry value with the default
            # UNVERIFIED value emitted by the generic tree resolver.
            if key in metadata_defaults and value in (None, "", [], "UNVERIFIED") and key in merged:
                continue
            # A registered citation ID is the stable provenance handle. The
            # generic tree resolver may use a normalized/derived span, so it
            # must not replace the registry's source hash, quote digest, or
            # validation result when the IDs match.
            if (
                chosen is not None
                and key in metadata_defaults
                and chosen.validation_status == "VALID"
                and (
                    not raw.get("citation_id")
                    or raw.get("citation_id") == chosen.citation_id
                )
            ):
                continue
            merged[key] = value
        if node_id:
            merged["node_id"] = node_id
        enriched.append(merged)
    return enriched


def _case_pack(case_id: str):
    try:
        return all_eval_cases()[case_id]
    except KeyError:
        raise HTTPException(404, case_id)


def _graph_view(rec: DossierRecord) -> dict:
    graph = rec.relation_graph
    if graph is None:
        return {"graph_id": None, "nodes": [], "edges": [], "issues": [], "truncated": False}
    return {
        "graph_id": graph.graph_id,
        "source_snapshot_digest": graph.source_snapshot_digest,
        "nodes": [node.model_dump() for node in graph.nodes[:160]],
        "edges": [edge.model_dump() for edge in graph.edges[:240]],
        "issues": [issue.model_dump() for issue in graph.issues[:120]],
        "truncated": len(graph.nodes) > 160 or len(graph.edges) > 240 or len(graph.issues) > 120,
    }


def _table_view(rec: DossierRecord, table_id: str, offset: int, limit: int) -> dict:
    table = next((item for item in rec.tables if item.table_id == table_id), None)
    if table is None:
        raise HTTPException(404, table_id)
    safe_offset = max(0, offset)
    safe_limit = min(max(1, limit), 100)
    citation_rows = {}
    for key, value in table.cell_citations.items():
        parts = key.split(":")
        row_index = -1
        for part in reversed(parts):
            candidate = part[1:] if part[:1].lower() == "r" else part
            if candidate.isdigit():
                row_index = int(candidate)
                break
        if safe_offset <= row_index < safe_offset + safe_limit:
            citation_rows[key] = value.model_dump()
    return {
        "table_id": table.table_id,
        "title": table.title,
        "header": table.header,
        "continuation": table.continuation,
        "n_rows": len(table.rows),
        "offset": safe_offset,
        "limit": safe_limit,
        "rows": table.rows[safe_offset : safe_offset + safe_limit],
        "cells": [cell.model_dump() for cell in table.cells if safe_offset <= cell.row_index < safe_offset + safe_limit],
        "cell_citations": citation_rows,
        "has_geometry": bool(table.cells or table.cell_citations),
    }


@app.get("/health")
def health() -> dict:
    llm = NineRouterClient()
    if os.getenv("AI2_EMBEDDING_DISCOVERY_ENABLED", "false").casefold() in {"1", "true", "yes", "on"}:
        embedding = EMBEDDING_CLIENT.discover(egress_approved=True).as_dict()
    else:
        embedding = {"status": "NOT_RUN", "models": [], "selected_model": None, "dimensions": None}
    return {
        "status": "ok",
        "llm": "ready" if llm.configured() else "off",
        "model": llm.model if llm.configured() else "",
        "persist": str(DATA),
        "embedding": embedding,
    }


@app.get("/healthz")
def healthz() -> dict:
    """Legacy Backend health contract."""

    return {"status": "ok"}


@app.post("/process", status_code=202)
@app.post("/api/v1/process", status_code=202)
def process_from_backend(payload: dict, request: Request) -> dict:
    """Accept the current Backend AI2 handoff without fabricating evidence.

    The Backend adapter currently sends snapshot metadata and relation metadata,
    but not the canonical snapshot content required for citation-grounded AI2
    processing. Keep both the canonical and Backend-prefixed paths available
    while making the evidence gap explicit.
    """

    required = {
        "snapshot_id",
        "snapshot_version",
        "digest",
        "dossier_members",
        "role_relation_map",
        "policy_flags",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise HTTPException(
            status_code=422,
            detail={"code": "AI2_PROCESS_FIELDS_REQUIRED", "missing": missing},
        )
    return {
        "status": "accepted",
        "state": "INSUFFICIENT_EVIDENCE",
        "snapshot_id": str(payload["snapshot_id"]),
        "snapshot_version": str(payload["snapshot_version"]),
        "digest": str(payload["digest"]),
        "facts": [],
        "findings": [],
        "evidence_gaps": [
            {
                "code": "AI2_SNAPSHOT_CONTENT_REQUIRED",
                "severity": "high",
                "message": (
                    "Backend handoff contains metadata but no canonical "
                    "snapshot content/citations"
                ),
            }
        ],
        "ai2": {"service": "ai2", "tenant_id": request.headers.get("X-Tenant-Id", "")},
    }


@app.post("/query")
@app.post("/api/v1/query")
def query_from_backend(payload: dict) -> dict:
    """Answer against the canonical record received through ``/jobs/idp``."""

    try:
        service_envelope = verify_service_envelope(payload, required_scope="ai2.query")
    except ServiceEnvelopeError as exc:
        # The unsigned compatibility lane remains fail-closed. Only a signed
        # backend query may read the authoritative dossier record.
        if not isinstance(payload.get("service_envelope"), dict):
            service_envelope = None
        else:
            raise HTTPException(
                status_code=401,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc

    query = str(payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=422, detail={"code": "QUERY_REQUIRED"})
    dossier_id = str(payload.get("dossier_id") or "")
    if not dossier_id:
        raise HTTPException(status_code=422, detail={"code": "DOSSIER_ID_REQUIRED"})
    requested_digest = str(payload.get("snapshot_digest") or "").strip()
    query_contract_version = str(payload.get("query_contract_version") or "").strip()
    if service_envelope is not None:
        record = STORE.get(service_envelope.tenant_id, dossier_id)
        if record is not None:
            expected_digest = str(record.pins.source_snapshot_digest or "")
            # The versioned Backend contract must bind the query to the
            # current canonical snapshot. Keep the older signed compatibility
            # lane readable for existing callers that predate this field.
            requires_evidence_context = query_contract_version == "ai2.query.v1" or bool(
                requested_digest
            )
            if requires_evidence_context and (
                not requested_digest or requested_digest != expected_digest
            ):
                return {
                    "state": "INSUFFICIENT_EVIDENCE",
                    "answer": None,
                    "citations": [],
                    "retrieval_layer": {
                        "dossier_id": dossier_id,
                        "snapshot_digest": requested_digest or None,
                    },
                    "reasoning_trace": [
                        {
                            "code": "AI2_QUERY_EVIDENCE_CONTEXT_REQUIRED",
                            "message": "Query scope phải bind tenant, dossier và snapshot digest hiện hành.",
                        }
                    ],
                }
            member_ids = [source.file_id for source in record.source_files if source.file_id]
            envelope = ToolEnvelope(
                auth=AuthContext(
                    actor_id=service_envelope.actor_id,
                    tenant_id=service_envelope.tenant_id,
                    dossier_id=dossier_id,
                    acl_revision=record.acl_revision,
                    permissions=record.permissions_by_actor.get(
                        service_envelope.actor_id, ["READ_CONTENT"]
                    ),
                    member_ids=member_ids,
                    member_documents={},
                    lifecycle=record.lifecycle,
                ),
                pins=record.pins,
            )
            result = QueryRouter(STORE, ToolGateway(STORE)).query(
                envelope,
                query,
                classify_ask(query),
            )
            citations = _enrich_citations(result.get("citations") or [], record)
            answer = result.get("answer")
            if answer is not None and not isinstance(answer, str):
                answer = json.dumps(answer, ensure_ascii=False)
            return {
                "state": result.get("review_state") or result.get("state") or "INSUFFICIENT_EVIDENCE",
                "answer": answer,
                "citations": citations,
                "retrieval_layer": {
                    "dossier_id": dossier_id,
                    "snapshot_version": payload.get("snapshot_version"),
                    "snapshot_digest": expected_digest,
                    "source": "ai2.canonical.store",
                },
                "reasoning_trace": result.get("steps") or [],
            }
    return {
        "state": "INSUFFICIENT_EVIDENCE",
        "answer": "AI2 chưa nhận được snapshot/citation có thẩm quyền cho hồ sơ này.",
        "citations": [],
        "retrieval_layer": {
            "dossier_id": dossier_id,
            "snapshot_version": payload.get("snapshot_version"),
            "snapshot_digest": requested_digest or None,
        },
        "reasoning_trace": [
            {
                "code": "AI2_QUERY_EVIDENCE_REQUIRED",
                "message": (
                    "Query chỉ được trả lời sau khi AI2 nhận canonical snapshot "
                    "và citation map"
                ),
            }
        ],
    }


@app.post("/api/v1/jobs/ocr", status_code=501)
def legacy_ocr_not_supported() -> dict:
    """AI2 must not impersonate AI1/OCR."""

    raise HTTPException(
        status_code=501,
        detail={
            "code": "AI2_OCR_NOT_SUPPORTED",
            "message": "OCR belongs to AI1; send an AI1 snapshot to AI2 instead",
        },
    )


@app.post("/api/v1/jobs/reocr", status_code=501)
def legacy_reocr_not_supported() -> dict:
    """AI2 must not impersonate AI1/re-OCR."""

    raise HTTPException(
        status_code=501,
        detail={
            "code": "AI2_REOCR_NOT_SUPPORTED",
            "message": "re-OCR belongs to AI1; send the revised snapshot to AI2 instead",
        },
    )


@app.post("/api/v1/jobs/extract", status_code=202)
def legacy_extract(payload: dict, request: Request) -> dict:
    """Accept the old extraction shape without fabricating evidence.

    The old request contains text but no canonical page/line citation map.
    Therefore the compatibility result intentionally contains no facts and an
    explicit evidence gap.  The canonical ``/jobs/idp`` endpoint remains the
    path for authoritative extraction.
    """

    document_id = str(payload.get("document_id") or "")
    if not document_id:
        raise HTTPException(status_code=422, detail={"code": "DOCUMENT_ID_REQUIRED"})
    result = {
        "schema_version": "ai2.extraction.v2",
        "document_id": document_id,
        "facts": [],
        "evidence_gaps": [
            {
                "page_no": 1,
                "crop_bbox": [0.0, 0.0, 1.0, 1.0],
                "reason": "legacy extract request has no canonical page/line citation evidence",
                "severity": "high",
                "suggested_profile": "ai1.snapshot.v1",
            }
        ],
    }
    return create_completed_job(
        kind="extract",
        result=result,
        tenant_id=request.headers.get("X-Tenant-Id", ""),
    )


@app.post("/api/v1/jobs/compare", status_code=202)
def legacy_compare(payload: dict, request: Request) -> dict:
    """Fail closed because the old compare shape has no authoritative citations."""

    if not payload.get("dossier_id"):
        raise HTTPException(status_code=422, detail={"code": "DOSSIER_ID_REQUIRED"})
    return create_failed_job(
        kind="compare",
        code="INSUFFICIENT_EVIDENCE",
        message=(
            "legacy compare request has facts without canonical source citations; "
            "use /jobs/idp with ai1.snapshot.v1"
        ),
        tenant_id=request.headers.get("X-Tenant-Id", ""),
    )


@app.get("/api/v1/jobs/{job_id}")
def legacy_get_job(job_id: str) -> dict:
    report = get_legacy_job(job_id)
    if report is None:
        raise HTTPException(status_code=404, detail=job_id)
    report.pop("tenant_id", None)
    return report


@app.delete("/api/v1/jobs/{job_id}")
def legacy_cancel_job(job_id: str) -> dict:
    report = cancel_legacy_job(job_id)
    if report is None:
        raise HTTPException(status_code=404, detail=job_id)
    report.pop("tenant_id", None)
    return report


@app.post("/api/workspace/sample")
def workspace_sample() -> dict:
    contracts = ROOT / "fixtures" / "contracts"
    body_pdf = contracts / "HD-TONG-HOP.body.pdf"
    annex_pdf = contracts / "HD-TONG-HOP.annex.pdf"
    items: list[tuple[str, bytes, str]] = []
    if body_pdf.exists() and annex_pdf.exists():
        items.append((body_pdf.name, body_pdf.read_bytes(), "body"))
        items.append((annex_pdf.name, annex_pdf.read_bytes(), "annex"))
    else:
        md = (contracts / "HD-TONG-HOP.vi.md").read_text(encoding="utf-8")
        head, _, tail = md.partition("## PHẦN 5")
        items.append(("HD-TONG-HOP.body.md", head.encode("utf-8"), "body"))
        items.append(("HD-TONG-HOP.annex.md", ("## PHẦN 5" + tail).encode("utf-8"), "annex"))
    rec, env, meta, blobs = ingest_files(items)
    return _open_session(rec, env, "HĐ + phụ lục (mẫu)", "sample", meta, blobs=blobs, gold=False)


@app.post("/api/workspace/sample-compare")
def workspace_sample_compare() -> dict:
    contracts = ROOT / "fixtures" / "contracts"
    pdf = contracts / "SALE-BRD.sample.pdf"
    md = contracts / "SALE-BRD.vi.md"
    if pdf.exists():
        items = [(pdf.name, pdf.read_bytes(), "body")]
    elif md.exists():
        items = [("SALE-BRD.sample.md", md.read_text(encoding="utf-8").encode("utf-8"), "body")]
    else:
        raise HTTPException(404, "SALE-BRD sample missing")
    rec, env, meta, blobs = ingest_files(items)
    view = _open_session(rec, env, "HĐ đối chiếu SALE/SERVICE (mẫu)", "compare", meta, blobs=blobs)
    sid = view["session_id"]
    s = SESSIONS[sid]
    result = run_idp(rec, env, llm=None, store=STORE)
    JOBS[result.job_id] = result
    s["job"] = result
    s["used_llm"] = False
    s["step"] = "extract"
    rec2 = STORE.get(rec.tenant_id, rec.dossier_id)
    if rec2:
        s["record"] = rec2
    save_session(sid, s, STORE)
    return _session_view(sid)


@app.post("/api/workspace/ai1-snapshot")
def workspace_ai1_snapshot(snapshot: dict) -> dict:
    """Open the snapshot/legacy workspace lane, never the AI1 result lane."""
    machine = snapshot.get("machine") if isinstance(snapshot, dict) else None
    if isinstance(machine, dict) and str(machine.get("schema_version")) == "0.1":
        raise HTTPException(
            422,
            {
                "code": "WRONG_INPUT_LANE",
                "message": "ai1.result.v0.1 must be sent to /api/workspace/ai1-result",
            },
        )
    demo_meta: dict = {}
    input_payload = snapshot
    if is_ocr_json_demo(snapshot):
        source_digest = hashlib.sha256(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        try:
            input_payload, demo_meta = normalize_ocr_json(snapshot, source_digest=source_digest)
        except ValueError as exc:
            raise HTTPException(422, {"code": "OCR_JSON_DEMO_INVALID", "message": str(exc)}) from exc
    try:
        adapted = adapt_ai1_input(input_payload)
        if demo_meta:
            adapted.meta.update({"source": "ocr_json_data_meta_demo", "demo_adapter": demo_meta})
    except SnapshotContractError as exc:
        raise HTTPException(422, {"code": exc.code, "message": str(exc)}) from exc
    return _open_session(
        adapted.record,
        adapted.envelope,
        "AI1 OCR snapshot (data/meta demo adapter)" if demo_meta else "AI1 OCR snapshot",
        "ai1_snapshot",
        adapted.meta,
    )


@app.post("/api/workspace/ai1-result")
async def workspace_ai1_result(request: Request, dossier_id: str | None = None, scope_id: str | None = None) -> dict:
    """Open the current AI1 result envelope without confusing it with the canonical v1 snapshot.

    JSON is sufficient. A multipart request may additionally carry the source
    PDF as ``pdf`` for hash checking and PDF.js display; AI2 still reasons from
    the JSON handoff and never re-runs OCR on the PDF.
    """

    content_type = (request.headers.get("content-type") or "").casefold()
    payload: dict
    filename = "AI1 result v0.1.json"
    pdf_bytes: bytes | None = None
    if "multipart/form-data" in content_type:
        form = await request.form()
        artifact = form.get("artifact") or form.get("file") or form.get("json")
        if hasattr(artifact, "read"):
            filename = artifact.filename or filename
            raw = await artifact.read()
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise HTTPException(422, {"code": "RESULT_JSON_INVALID", "message": str(exc)}) from exc
        elif isinstance(artifact, str):
            try:
                payload = json.loads(artifact)
            except json.JSONDecodeError as exc:
                raise HTTPException(422, {"code": "RESULT_JSON_INVALID", "message": str(exc)}) from exc
        else:
            raise HTTPException(400, "multipart request requires artifact JSON")
        pdf = form.get("pdf")
        if hasattr(pdf, "read"):
            pdf_bytes = await pdf.read()
    else:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(422, {"code": "RESULT_JSON_INVALID", "message": str(exc)}) from exc
    if not isinstance(payload, dict):
        raise HTTPException(422, {"code": "RESULT_CONTRACT_INVALID", "message": "result root must be an object"})
    machine = payload.get("machine")
    if not isinstance(machine, dict) or str(machine.get("schema_version")) != "0.1":
        raise HTTPException(
            422,
            {
                "code": "WRONG_INPUT_LANE",
                "message": "this endpoint accepts ai1.result.v0.1 only; use the snapshot lane for ai1.snapshot.v1",
            },
        )
    try:
        adapted = adapt_ai1_result_v01(
            payload,
            dossier_id=dossier_id,
            scope_id=scope_id,
        )
    except SnapshotContractError as exc:
        raise HTTPException(422, {"code": exc.code, "message": str(exc)}) from exc

    blobs: dict[str, bytes] = {}
    if pdf_bytes:
        source_hashes = {
            str(source.digest).removeprefix("sha256:").lower()
            for source in adapted.record.source_files
            if source.digest
        }
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest().lower()
        if source_hashes and pdf_hash not in source_hashes:
            adapted.record.handoff_issues.append(
                HandoffIssue(
                    code="PDF_HASH_MISMATCH",
                    message=f"optional PDF hash {pdf_hash} does not match AI1 source hash",
                    review_state=ReviewState.BLOCKED,
                )
            )
            adapted.record.review_items.append(
                ReviewItem(
                    review_item_id="review:PDF_HASH_MISMATCH",
                    kind="PDF_HASH_MISMATCH",
                    reason="Optional PDF was not attached because its hash differs from AI1 source",
                    review_state=ReviewState.BLOCKED,
                    proposed_action="FIX_INPUT",
                )
            )
        elif adapted.record.source_files:
            blobs[adapted.record.source_files[0].file_id] = pdf_bytes
    return _open_session(
        adapted.record,
        adapted.envelope,
        filename,
        "ai1_result",
        adapted.meta,
        blobs=blobs,
    )


@app.post("/api/workspace/case/{case_id}")
def workspace_case(case_id: str) -> dict:
    """Open an evaluation fixture in the same workspace UI as a real upload."""

    pack = _case_pack(case_id)
    # Evaluation fixtures are AI2 handoff records and historically had no
    # source artifact. Attach a generated, document-backed PDF so the demo
    # renders the same pages/tables that AI2 is reasoning over.
    blobs, _pdf_path = attach_case_pdf(pack)
    return _open_session(
        pack.record,
        pack.envelope,
        f"Case {pack.case_id}: {pack.title}",
        "eval_case",
        {
            "source": "eval_case",
            "case_id": pack.case_id,
            "title": pack.title,
            "scenario": pack.notes,
            "expected_state": pack.expected_state,
            "input_kind": "synthetic_fixture" if "synthetic" in pack.tags else "catalog_fixture",
            "query": pack.query,
        },
        blobs=blobs,
        gold=pack.case_id == "HD-TONG-HOP",
    )


@app.post("/api/workspace/upload")
async def workspace_upload(request: Request) -> dict:
    form = await request.form()
    uploads: list[UploadFile] = []
    for key in ("files", "file"):
        for item in form.getlist(key):
            if hasattr(item, "read"):
                uploads.append(item)  # type: ignore[arg-type]
    items: list[tuple[str, bytes, str]] = []
    for i, f in enumerate(uploads):
        data = await f.read()
        if not data:
            continue
        if len(data) > 12 * 1024 * 1024:
            raise HTTPException(400, "file too large")
        name = f.filename or f"file_{i}.bin"
        role = "annex" if (i > 0 or "annex" in name.lower() or "phu" in name.lower() or "phụ" in name.lower()) else "body"
        if len(uploads) == 1:
            role = "annex" if any(x in name.lower() for x in ("annex", "phu", "phụ")) else "body"
        items.append((name, data, role))
    if not items:
        raise HTTPException(400, "empty file")
    rec, env, meta, blobs = ingest_files(items)
    names = ", ".join(n for n, _, _ in items)
    return _open_session(rec, env, names, "upload", meta, blobs=blobs)


@app.get("/api/workspace/{session_id}/files/{file_id}")
def workspace_file(session_id: str, file_id: str):
    s = _require_session(session_id)
    blob = (s.get("blobs") or {}).get(file_id)
    if not blob:
        raise HTTPException(404, file_id)
    rec: DossierRecord = s["record"]
    src = next((f for f in rec.source_files if f.file_id == file_id), None)
    name = src.filename if src else f"{file_id}.pdf"
    media = "application/pdf" if name.lower().endswith(".pdf") else "application/octet-stream"
    return Response(content=blob, media_type=media, headers={"Content-Disposition": f'inline; filename="{name}"'})


@app.get("/api/workspace/{session_id}")
def workspace_get(session_id: str) -> dict:
    return _session_view(session_id)


@app.get("/api/workspace/{session_id}/tree")
def workspace_tree(session_id: str) -> dict:
    s = _require_session(session_id)
    rec: DossierRecord = s["record"]
    nodes = rec.evidence_nodes()
    return {"session_id": session_id, "tree": build_tree(nodes), "n_nodes": len(nodes), "n_raw_nodes": len(rec.nodes)}


@app.get("/api/workspace/{session_id}/locate/{node_id}")
def workspace_locate(session_id: str, node_id: str) -> dict:
    s = _require_session(session_id)
    rec: DossierRecord = s["record"]
    found = locate(rec.evidence_nodes(), rec.pages, node_id)
    if found is None:
        raise HTTPException(404, node_id)
    return found


@app.get("/api/workspace/{session_id}/page/{n}")
def workspace_page(session_id: str, n: int) -> dict:
    s = _require_session(session_id)
    rec: DossierRecord = s["record"]
    page = next((p for p in rec.pages if p.page_number == n), None)
    if page is None:
        raise HTTPException(404, str(n))
    return {
        "page": page.page_number,
        "quality": page.quality,
        "text": page.text[:6000],
        "page_revision_id": page.page_revision_id,
        "n_pages": len(rec.pages),
    }


@app.get("/api/workspace/{session_id}/page/{n}/image")
def workspace_page_image(session_id: str, n: int) -> dict:
    """Return source image metadata when AI1 supplied an image key.

    The demo uses the optional source PDF for actual rendering. Without that
    file, this endpoint deliberately returns metadata and never fabricates a
    page image or bbox.
    """

    s = _require_session(session_id)
    rec: DossierRecord = s["record"]
    page = next((p for p in rec.pages if p.page_number == n), None)
    if page is None:
        raise HTTPException(404, str(n))
    return {
        "page": n,
        "image_key": page.image_key,
        "available": bool(page.image_key and s.get("blobs")),
        "has_pdf": bool(s.get("blobs")),
        "coordinate_system": "normalized_top_left_rendered_page",
    }


@app.get("/api/workspace/{session_id}/review-items")
def workspace_review_items(session_id: str) -> dict:
    s = _require_session(session_id)
    rec: DossierRecord = s["record"]
    return {
        "session_id": session_id,
        "status": "NOT_RUN" if s.get("job") is None else ("EMPTY_QUEUE" if not rec.review_items else "HAS_REVIEW_ITEMS"),
        "items": [item.model_dump() for item in rec.review_items],
    }


@app.post("/api/workspace/{session_id}/citations/{citation_id}/verify")
def verify_workspace_citation(session_id: str, citation_id: str) -> dict:
    s = _require_session(session_id)
    rec: DossierRecord = s["record"]
    citation = rec.citation_index.get(citation_id)
    if citation is None:
        raise HTTPException(404, citation_id)
    check = CitationResolver(rec.pages, rec.tables).verify(citation)
    page = check.page
    citation.validation_status = check.status
    line_text = page.line_texts.get(citation.line_ids[0], "") if page and citation.line_ids else ""
    valid = check.valid
    return {
        "citation_id": citation_id,
        "valid": valid,
        "status": citation.validation_status,
        "reason": check.reason,
        "citation": citation.model_dump(),
        "source_text": line_text or (page.text if page else ""),
        "page": citation.page,
        "page_revision_id": citation.page_revision_id,
    }


@app.get("/api/workspace/{session_id}/relation-graph")
def workspace_relation_graph(session_id: str) -> dict:
    s = _require_session(session_id)
    return {"session_id": session_id, **_graph_view(s["record"])}


@app.get("/api/workspace/{session_id}/tables/{table_id}")
def workspace_table(session_id: str, table_id: str, offset: int = 0, limit: int = 50) -> dict:
    s = _require_session(session_id)
    return {"session_id": session_id, **_table_view(s["record"], table_id, offset, limit)}


@app.post("/api/workspace/{session_id}/extract")
def workspace_extract(session_id: str, body: RunBody) -> dict:
    s = _require_session(session_id)
    rec: DossierRecord = s["record"]
    env: ToolEnvelope = s["envelope"]
    llm = NineRouterClient() if body.use_llm else None
    if llm and not llm.configured():
        llm = None
    result = run_idp(rec, env, llm=llm, store=STORE)
    JOBS[result.job_id] = result
    s["job"] = result
    s["used_llm"] = bool(llm)
    s["step"] = "extract"
    rec2 = STORE.get(rec.tenant_id, rec.dossier_id)
    if rec2:
        s["record"] = rec2
    old_basis = s.get("review_basis") or {}
    new_basis = _review_basis(s["record"])
    if s.get("reviews") and old_basis != new_basis:
        s["reviews_stale"] = True
        for rev in s["reviews"].values():
            rev["stale"] = True
    s["review_basis"] = new_basis
    save_session(session_id, s, STORE)
    return _session_view(session_id)


@app.post("/api/workspace/{session_id}/review")
def workspace_review(session_id: str, body: ReviewBody) -> dict:
    s = _require_session(session_id)
    action = body.action.lower().strip()
    if action not in {"confirm", "correct", "reject"}:
        raise HTTPException(400, "action must be confirm|correct|reject")
    if action == "reject" and not (body.reason or "").strip():
        raise HTTPException(400, "reject requires reason")
    job = s.get("job")
    candidate_ids = {
        c.candidate_id
        for c in (job.contribution.candidates if job and job.contribution else [])
    }
    if body.candidate_id not in candidate_ids:
        raise HTTPException(404, "candidate not found in current contribution")
    reviews = s.setdefault("reviews", {})
    prev = reviews.get(body.candidate_id) or {}
    rev = int(prev.get("revision") or 0) + 1
    reviews[body.candidate_id] = {
        "candidate_id": body.candidate_id,
        "action": action,
        "reason": body.reason,
        "overlay_text": body.overlay_text,
        "revision": rev,
        "stale": False,
        "basis": _review_basis(s["record"]),
    }
    s["reviews_stale"] = any(bool(item.get("stale")) for item in reviews.values())
    save_session(session_id, s, STORE)
    return _session_view(session_id)


@app.post("/api/workspace/{session_id}/publish")
def workspace_publish(session_id: str, body: PublishBody) -> dict:
    s = _require_session(session_id)
    if not body.confirm:
        raise HTTPException(400, "confirm required")
    job = s.get("job")
    if not job or not job.contribution:
        raise HTTPException(400, "no contribution")
    if s.get("authoritative_publish_blocked"):
        raise HTTPException(409, "AI1 result is pending review; authoritative publish is blocked")
    if s.get("reviews_stale"):
        raise HTTPException(409, "review overlays are stale after processing changes")
    s["published"] = True
    save_session(session_id, s, STORE)
    return _session_view(session_id)


@app.get("/api/workspace/{session_id}/tasks")
def workspace_tasks(session_id: str) -> list[dict]:
    s = _require_session(session_id)
    rec: DossierRecord = s["record"]
    nodes = rec.evidence_nodes()
    if s["source"] == "sample" or s.get("gold"):
        return tasks_from_outline(nodes, _load_hd_tasks())
    return adhoc_tasks(nodes)


@app.post("/api/workspace/{session_id}/reason")
def workspace_reason(session_id: str, body: ReasonBody) -> dict:
    s = _require_session(session_id)
    rec: DossierRecord = s["record"]
    env: ToolEnvelope = s["envelope"]
    tasks = {t["id"]: t for t in workspace_tasks(session_id)}
    task = tasks.get(body.task_id)
    if not task:
        raise HTTPException(404, body.task_id)
    if s.get("job") is None:
        workspace_extract(session_id, RunBody(use_llm=False))
        rec = SESSIONS[session_id]["record"]
    s["step"] = "reason"
    return {"task_id": task["id"], **_reason_output(rec, env, task, use_llm=body.use_llm, use_vector=body.use_vector)}


@app.post("/api/workspace/{session_id}/ask")
def workspace_ask(session_id: str, body: AskBody) -> dict:
    s = _require_session(session_id)
    q = (body.query or "").strip()
    if not q:
        raise HTTPException(400, "empty query")
    rec: DossierRecord = s["record"]
    env: ToolEnvelope = s["envelope"]
    STORE.put(rec)
    task = classify_ask(q)
    s["step"] = "reason"
    out = _reason_output(rec, env, task, use_llm=body.use_llm, use_vector=body.use_vector)
    return {"query": q, "task": task, **out}


@app.get("/api/cases")
def list_cases() -> list[dict]:
    items = []
    for pack in all_eval_cases().values():
        items.append(
            {
                "case_id": pack.case_id,
                "title": pack.title,
                "expected_state": pack.expected_state,
                "tags": pack.tags,
                "n_pages": len(pack.record.pages),
                "n_nodes": len(pack.record.nodes),
                "n_tables": len(pack.record.tables),
                "input_kind": "synthetic_fixture" if "synthetic" in pack.tags else "catalog_fixture",
                "scenario": pack.notes,
                "query": pack.query,
            }
        )
    return items


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> dict:
    pack = _case_pack(case_id)
    rec = pack.record
    tables = []
    for t in rec.tables:
        tables.append(
            {
                "table_id": t.table_id,
                "title": t.title,
                "header": t.header,
                "n_rows": len(t.rows),
                "continuation": t.continuation,
                "first_rows": t.rows[:2],
                "last_rows": t.rows[-2:] if len(t.rows) > 2 else t.rows,
            }
        )
    return {
        **pack.to_meta(),
        "notes": pack.notes,
        "query": pack.query,
        "expected_no_claims": pack.expected_no_claims,
        "lifecycle": rec.lifecycle.value,
        "tenant_id": rec.tenant_id,
        "envelope_tenant": pack.envelope.auth.tenant_id,
        "pages": [{"page": p.page_number, "quality": p.quality, "text": p.text[:400]} for p in rec.pages[:8]],
        "n_pages_hidden": max(0, len(rec.pages) - 8),
        "nodes": [
            {
                "node_id": n.node_id,
                "type": n.type,
                "raw_label": n.raw_label,
                "text": n.text[:240],
                "structured_key": n.structured_key,
            }
            for n in rec.nodes[:24]
        ],
        "n_nodes_hidden": max(0, len(rec.nodes) - 24),
        "tables": tables,
        "input_kind": "synthetic_fixture" if "synthetic" in pack.tags else "catalog_fixture",
        "scenario": pack.notes,
        "policy": _policy_view(rec),
    }


@app.get("/api/cases/{case_id}/relation-graph")
def case_relation_graph(case_id: str) -> dict:
    pack = _case_pack(case_id)
    rec = STORE.get(pack.record.tenant_id, pack.record.dossier_id) or pack.record
    if rec.relation_graph is None:
        rec.relation_graph = build_relation_graph(rec)
    return {"case_id": case_id, **_graph_view(rec)}


@app.get("/api/cases/{case_id}/tables/{table_id}")
def case_table(case_id: str, table_id: str, offset: int = 0, limit: int = 50) -> dict:
    pack = _case_pack(case_id)
    rec = STORE.get(pack.record.tenant_id, pack.record.dossier_id) or pack.record
    return {"case_id": case_id, **_table_view(rec, table_id, offset, limit)}


@app.post("/api/cases/{case_id}/run")
def run_case(case_id: str, body: RunBody) -> dict:
    pack = _case_pack(case_id)
    rec = pack.record
    STORE.put(rec)
    LAST_CASE["id"] = case_id
    llm = NineRouterClient() if body.use_llm else None
    if llm and not llm.configured():
        llm = None
    result = run_idp(rec, pack.envelope, llm=llm, store=STORE)
    JOBS[result.job_id] = result
    return {
        "case_id": case_id,
        "used_llm": bool(llm),
        "job": result.model_dump(),
    }


@app.post("/api/cases/{case_id}/query")
def query_case(case_id: str, body: AskBody) -> dict:
    pack = _case_pack(case_id)
    rec = STORE.get(pack.record.tenant_id, pack.record.dossier_id) or pack.record
    STORE.put(rec)
    if not rec.chunks:
        run_idp(rec, pack.envelope, llm=None, store=STORE)
        rec = STORE.get(pack.record.tenant_id, pack.record.dossier_id) or rec
        STORE.put(rec)
    task = classify_ask(body.query)
    return {
        "case_id": case_id,
        "query": body.query,
        "task": task,
        **_reason_output(rec, pack.envelope, task, use_llm=body.use_llm, use_vector=body.use_vector),
    }


def _load_hd_tasks() -> list[dict]:
    path = ROOT / "fixtures" / "reasoning" / "hd_tong_hop_tasks.json"
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/cases/HD-TONG-HOP/tasks")
def hd_tasks() -> list[dict]:
    return _load_hd_tasks()


@app.post("/api/cases/HD-TONG-HOP/reason")
def hd_reason(body: ReasonBody) -> dict:
    tasks = {t["id"]: t for t in _load_hd_tasks()}
    task = tasks.get(body.task_id)
    if not task:
        raise HTTPException(404, body.task_id)
    pack = load_case("HD-TONG-HOP")
    rec = STORE.get(pack.record.tenant_id, pack.record.dossier_id)
    if rec is None or not rec.chunks:
        llm = NineRouterClient() if body.use_llm else None
        if llm and not llm.configured():
            llm = None
        run_idp(pack.record, pack.envelope, llm=None, store=STORE)
        rec = STORE.get(pack.record.tenant_id, pack.record.dossier_id) or pack.record
        STORE.put(rec)
    return {"task_id": task["id"], **_reason_output(rec, pack.envelope, task, use_llm=body.use_llm, use_vector=body.use_vector)}


@app.post("/api/cases/{case_id}/reason")
def reason_case(case_id: str, body: ReasonBody) -> dict:
    if case_id != "HD-TONG-HOP":
        raise HTTPException(404, case_id)
    return hd_reason(body)


@app.post("/jobs/idp", status_code=202)
def create_idp_job(payload: dict, background_tasks: BackgroundTasks) -> dict:
    """Accept the stable Backend → AI2 processing contract.

    Processing is asynchronous for the public contract. The local demo uses
    FastAPI background tasks; production may move the same worker function to
    a durable queue without changing the payload or polling response.
    """

    try:
        service_envelope = verify_service_envelope(payload)
    except ServiceEnvelopeError as exc:
        raise HTTPException(status_code=401, detail={"code": exc.code, "message": str(exc)}) from exc

    try:
        request, _ = adapt_be_ai2_processing_request(
            payload,
            tenant_id=service_envelope.tenant_id,
            actor_id=service_envelope.actor_id,
        )
    except SnapshotContractError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc

    queued = _queued_wire_result(request, "pending")
    try:
        stored, created = JOB_STORE.create_or_get(
            tenant_id=service_envelope.tenant_id,
            dossier_id=request.dossier_id,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            attempt=request.attempt,
            request=request.model_dump(),
            wire=queued,
            nonce=service_envelope.nonce,
            request_fingerprint=service_envelope.payload_sha256,
        )
    except (JobOwnershipConflict, JobNonceReplayConflict, JobPayloadConflict) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": (
                    "SERVICE_NONCE_REPLAY"
                    if isinstance(exc, JobNonceReplayConflict)
                    else "IDEMPOTENCY_PAYLOAD_CONFLICT"
                    if isinstance(exc, JobPayloadConflict)
                    else "IDEMPOTENCY_OWNER_CONFLICT"
                ),
                "message": str(exc),
            },
        ) from exc
    job_id = stored["job_id"]
    wire = dict(stored["wire"])
    wire["job_id"] = job_id
    WIRE_IDEMPOTENCY[(service_envelope.tenant_id, request.idempotency_key, request.attempt)] = job_id
    WIRE_JOBS[job_id] = wire
    if created or stored["status"] in {"QUEUED", "RUNNING"}:
        background_tasks.add_task(_run_wire_job, job_id, request.model_dump())
    return wire


@app.get("/jobs/{job_id}")
def get_job(job_id: str, x_ai2_service_envelope: str | None = Header(default=None)) -> dict | JobResult:
    stored = JOB_STORE.get(job_id)
    if stored is None:
        raise HTTPException(404, job_id)
    if not x_ai2_service_envelope:
        raise HTTPException(
            status_code=401,
            detail={"code": "SERVICE_ENVELOPE_MISSING", "message": "polling requires a signed service envelope"},
        )
    try:
        raw_envelope = json.loads(x_ai2_service_envelope)
        envelope = verify_service_envelope(
            {
                "operation": "get_job",
                "job_id": job_id,
                "dossier_id": stored["dossier_id"],
                "service_envelope": raw_envelope,
            }
        )
    except (json.JSONDecodeError, ServiceEnvelopeError) as exc:
        code = exc.code if isinstance(exc, ServiceEnvelopeError) else "SERVICE_ENVELOPE_INVALID"
        raise HTTPException(status_code=401, detail={"code": code, "message": str(exc)}) from exc
    if envelope.tenant_id != stored["tenant_id"] or envelope.dossier_id != stored["dossier_id"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "JOB_OWNER_MISMATCH", "message": "job does not belong to this service principal"},
        )
    wire = dict(stored["wire"])
    wire["job_id"] = job_id
    WIRE_JOBS[job_id] = wire
    return wire


def _same_source_text(quote: str, source: str) -> bool:
    """Compare source evidence without changing the stored raw OCR text."""

    if not quote or not source:
        return False
    normalized_quote = " ".join(quote.split()).casefold()
    normalized_source = " ".join(source.split()).casefold()
    return normalized_quote in normalized_source
