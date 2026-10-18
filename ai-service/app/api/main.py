from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import multiprocessing
import multiprocessing.connection
import os
import sys
import threading
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.api.contract_graph_router import router as contract_graph_router
from app.api.processing_trace_router import router as processing_trace_router
from app.compat_legacy import cancel_job as cancel_legacy_job
from app.compat_legacy import create_completed_job, create_failed_job
from app.compat_legacy import get_job as get_legacy_job
from app.contracts.models import (
    AuthContext,
    HandoffIssue,
    JobResult,
    ReviewItem,
    ReviewState,
    ToolEnvelope,
)
from app.contracts.wire import BeAi2ProcessingRequest, job_result_to_wire
from app.db.engine import database_url, ensure_database, get_engine, validate_database_config
from app.llm.client import DeadlineLLM, NineRouterClient, llm_status, query_llm_timeout_seconds
from app.llm.embeddings import OpenAICompatibleEmbeddingClient
from app.ops.memory import release_memory
from app.pipeline.ai1_ingest import ingest_files
from app.pipeline.ai1_snapshot_adapter import (
    SnapshotContractError,
    adapt_ai1_input,
    adapt_ai1_result_v01,
    adapt_be_ai2_processing_request,
    bare_sha256_digest,
    processing_egress_allowed,
)
from app.pipeline.citations import CitationResolver
from app.pipeline.grounding import repair_active_nodes
from app.pipeline.idp import run_idp
from app.pipeline.ocr_json_demo_adapter import is_ocr_json_demo, normalize_ocr_json
from app.pipeline.outline import build_tree, locate
from app.pipeline.runtime import ISSUE_MESSAGES_VI, ProcessingRuntime
from app.reasoning.gold import adhoc_tasks, tasks_from_outline
from app.reasoning.query import QueryRouter, classify_ask
from app.reasoning.relations import build_relation_graph
from app.reasoning.stack import FourLayerReasoner
from app.reasoning.vector_recall import VectorRecallService, query_embedding_token_cap
from app.security.service_envelope import ServiceEnvelopeError, verify_service_envelope
from app.tools.bounded import BoundedDict, env_capacity
from app.tools.gateway import ToolGateway
from app.tools.jobs import (
    JobNonceReplayConflict,
    JobOwnershipConflict,
    JobPayloadConflict,
    SQLiteJobStore,
    job_store_from_env,
)
from app.tools.persist import DATA, load_session, save_session
from app.tools.processing_trace_store import ProcessingTraceStore, ProcessingTraceWriter
from app.tools.query_store import load_query_snapshot
from app.tools.store import DossierRecord, InMemorySnapshotStore
from fixtures.case_pdf import attach_case_pdf
from fixtures.catalog import load_case
from fixtures.eval_suite import all_eval_cases

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

STATIC = Path(__file__).resolve().parent.parent / "static"

JOB_SWEEP_INTERVAL_SECONDS = 1.0
# Lease this process keeps on accepted jobs still waiting for a worker thread;
# renewed on every sweep tick, so it only lapses when the process is gone.
QUEUED_HOLD_MS = 60_000
_HELD_JOB_IDS: set[str] = set()
_HELD_LOCK = threading.Lock()


async def _periodic_job_sweep() -> None:
    while True:
        await asyncio.sleep(JOB_SWEEP_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(_sweep_stale_jobs)
        except Exception:
            logger.exception("ai2.job_sweep_failed")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    validate_database_config()
    if database_url():
        await asyncio.to_thread(ensure_database, get_engine())
    await asyncio.to_thread(hydrate_canonical_store)
    sweeper = asyncio.create_task(_periodic_job_sweep())
    try:
        yield
    finally:
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper


app = FastAPI(title="VSF AI2 IDP", version="0.1.0", lifespan=_lifespan)
app.include_router(contract_graph_router)
app.include_router(processing_trace_router)
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _store_capacity() -> int | None:
    # With Postgres, /query reloads every dossier from ai2.dossier_query_snapshots,
    # so the in-memory store is a cache. Without it the store is the only copy.
    return env_capacity("AI2_STORE_MAX_DOSSIERS", 4 if database_url() else None)


STORE = InMemorySnapshotStore(max_entries=_store_capacity())
logger = logging.getLogger(__name__)
# Job/dispatch timing lines. The app configures no logging, so without a handler of its own
# these INFO lines never reach `docker logs`. propagate stays on so caplog still sees them.
timing_logger = logging.getLogger("ai2.timing")


def _ensure_timing_handler() -> None:
    if timing_logger.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    timing_logger.addHandler(handler)
    timing_logger.setLevel(logging.INFO)


# A spawned job child re-imports this module, so it gets the handler too.
_ensure_timing_handler()


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


# Every job's durable state is in JOB_STORE; these maps only cache recent jobs
# so a long-lived process does not keep every result it ever produced.
JOBS: BoundedDict[str, JobResult] = BoundedDict(env_capacity("AI2_JOBS_CACHE_SIZE", 8))
WIRE_JOBS: BoundedDict[str, dict] = BoundedDict(env_capacity("AI2_WIRE_JOBS_CACHE_SIZE", 256))
WIRE_IDEMPOTENCY: BoundedDict[tuple[str, str, int], str] = BoundedDict(
    env_capacity("AI2_WIRE_JOBS_CACHE_SIZE", 256)
)
# Jobs that run IDP at once. Each holds a whole dossier (and its peak working
# set) in memory; the others wait QUEUED, held by this process (see the sweep).
MAX_CONCURRENT_JOBS = env_capacity("AI2_MAX_CONCURRENT_JOBS", 1) or 1
_JOB_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_JOBS)
JOB_STORE = job_store_from_env()
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
                actor_id=str((payload.get("service_envelope") or {}).get("actor_id") or "backend"),
            )
        except Exception as exc:  # pragma: no cover - corrupt historical job
            logger.warning(
                "ai2.store_hydration_skipped job_id=%s dossier_id=%s error=%s",
                job.get("job_id"),
                job.get("dossier_id"),
                exc,
            )
            continue
        persisted = load_query_snapshot(
            adapted.record.dossier_id, tenant_id=adapted.record.tenant_id
        )
        if persisted:
            STORE.put(persisted[0])
        else:
            STORE.put(adapted.record)
        restored += 1
    if restored:
        logger.info("ai2.store_hydrated dossiers=%s", restored)
    return restored


def hydrate_canonical_store() -> None:
    _sweep_stale_jobs()
    # Postgres already is the /query read model (ai2.dossier_query_snapshots);
    # replaying every SUCCEEDED job there only costs boot time and memory.
    if not database_url():
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


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


def _query_policy_flags() -> dict[str, bool]:
    """Server-side ``/query`` policy (A8). Request ``policy_flags`` are ignored:
    Backend does not decide AI2 egress, LLM or vector use."""

    return {
        "egress_allowed": _env_flag("AI2_QUERY_EGRESS_ALLOWED", True),
        "use_llm": _env_flag("AI2_QUERY_USE_LLM", True),
        "use_vector": _env_flag("AI2_QUERY_USE_VECTOR", True),
    }


def _queued_wire_result(
    request: BeAi2ProcessingRequest, job_id: str, query_snapshot_digest: str
) -> dict:
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
        "query_snapshot_digest": query_snapshot_digest,
    }


def _known_wire(job_id: str) -> dict:
    """Last wire of ``job_id``: the in-process cache, else the durable store."""

    cached = WIRE_JOBS.get(job_id)
    if cached is not None:
        return cached
    try:
        stored = JOB_STORE.get(job_id)
    except Exception:  # the caller is already handling a failure
        logger.warning("ai2.wire_lookup_failed job_id=%s", job_id, exc_info=True)
        return {}
    if not stored:
        return {}
    return dict(stored.get("wire") if "wire" in stored else stored)


def _run_wire_job(job_id: str, payload: dict) -> None:
    """Execute one accepted wire request; this process stops holding it after.

    Waits for one of ``MAX_CONCURRENT_JOBS`` slots first. Meanwhile the job is
    QUEUED and in ``_HELD_JOB_IDS``, so the sweep renews its lease instead of
    failing it, and the processing budget starts only once it runs.
    """

    entered = time.monotonic()
    slot_wait_ms = run_ms = None
    try:
        with _JOB_SLOTS:
            slot_wait_ms = _elapsed_ms(entered)
            held = time.monotonic()
            try:
                if JOB_ISOLATION == "process":
                    _run_isolated_job(job_id, payload)
                else:
                    _execute_wire_job(job_id, payload)
            finally:
                # The job's records are garbage now; give their pages back
                # before the next job, not at the end of the process.
                release_memory()
                run_ms = _elapsed_ms(held)
    finally:
        with _HELD_LOCK:
            _HELD_JOB_IDS.discard(job_id)
        timing_logger.info(
            "ai2.job_timing scope=dispatch isolation=%s job_id=%s slot_wait_ms=%s run_ms=%s",
            JOB_ISOLATION,
            job_id,
            slot_wait_ms,
            run_ms,
        )


# "process" runs each job in a spawned child: an OOM-kill or a hung job then takes the
# child, not the API answering GET /jobs and /query (#113). Job state lives in JOB_STORE,
# which both processes share. "thread" (default) keeps the in-process worker for tests.
JOB_ISOLATION = os.getenv("AI2_JOB_ISOLATION", "thread").strip().casefold()
_JOB_KILL_GRACE_SECONDS = 60
# Lease slack past the kill: the child claims after spawn, and the parent kills at
# spawn + budget + grace. A lease ending first let the sweep record AI2_WORKER_RESTARTED
# for a hung job instead of PROCESSING_TIMEOUT (PR #125 review 1d).
_LEASE_SLACK_SECONDS = 30


def _job_lease_ms(budget_seconds: float) -> int:
    return int((budget_seconds + _JOB_KILL_GRACE_SECONDS + _LEASE_SLACK_SECONDS) * 1000)


_CLAIM_REPORT = None  # child side of the pipe: (worker_token, tenant_id, dossier_id)


def _job_process_entry(job_id: str, payload: dict, conn) -> None:
    global _CLAIM_REPORT
    _CLAIM_REPORT = conn
    _execute_wire_job(job_id, payload)


def _payload_budget_seconds(payload: dict) -> float:
    try:
        return float(payload["policy_flags"]["budget_limits"]["max_processing_seconds"])
    except (KeyError, TypeError, ValueError):
        return 900.0


def _read_claim(receiver) -> tuple | None:
    try:
        # On Linux a killed child leaves the pipe readable at EOF: poll() is True, recv() raises.
        return receiver.recv() if receiver.poll() else None
    except (EOFError, OSError):
        return None


def _await_claim(receiver, child, limit: float) -> tuple[tuple | None, bool]:
    """Wait up to ``limit`` s for the child's claim: (claim or None, limit expired first)."""
    deadline = time.monotonic() + limit
    while child.is_alive():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, True
        ready = multiprocessing.connection.wait([receiver, child.sentinel], remaining)
        if receiver in ready:
            return _read_claim(receiver), False
    return None, False


def _run_isolated_job(job_id: str, payload: dict, *, target=_job_process_entry) -> None:
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    child = ctx.Process(target=target, args=(job_id, payload, sender), daemon=True)
    child.start()
    sender.close()
    limit = _payload_budget_seconds(payload) + _JOB_KILL_GRACE_SECONDS
    # The job budget starts in the child after import, envelope check and adapt; a 200-page
    # snapshot spends ~70 s there. The child reports its claim (budget start) over the pipe
    # and the kill deadline counts from that moment; the same limit bounds a child that
    # never claims (PR #125 review round 2).
    claim, expired = _await_claim(receiver, child, limit)
    # After a claim the full limit runs from now; without one only a short reap remains.
    child.join(0 if expired else limit if claim is not None else 5)
    timed_out = child.is_alive()
    if timed_out:
        child.kill()
        child.join(5)
    if claim is None:
        claim = _read_claim(receiver)
    receiver.close()
    if child.exitcode == 0:
        WIRE_JOBS.pop(job_id, None)
        _refresh_query_store(job_id)
        return
    code = "PROCESSING_TIMEOUT" if timed_out else "AI2_WORKER_CRASHED"
    logger.warning(
        "ai2.job_process_ended job_id=%s exitcode=%s code=%s", job_id, child.exitcode, code
    )
    update = {
        "status": "FAILED",
        "review_state": "BLOCKED",
        "result": None,
        "errors": [{"code": code, "message": ISSUE_MESSAGES_VI[code], "retryable": True}],
    }
    wire = {**_known_wire(job_id), **update}
    WIRE_JOBS.pop(job_id, None)
    if claim is None:
        JOB_STORE.fail_unclaimed(job_id, update)
    else:
        worker_token, tenant_id, dossier_id = claim
        JOB_STORE.set_wire(
            job_id,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            worker_token=worker_token,
            status="FAILED",
            wire=wire,
        )
    try:
        ProcessingTraceStore(JOB_STORE).finalize_stale_job(job_id)
    except Exception as exc:
        logger.warning(
            "ai2.processing_trace_finalize_failed job_id=%s code=%s", job_id, type(exc).__name__
        )


def _refresh_query_store(job_id: str) -> None:
    """The child wrote the query snapshot; this process drops or reloads its cached copy."""
    stored = JOB_STORE.get(job_id) or {}
    tenant_id, dossier_id = stored.get("tenant_id"), stored.get("dossier_id")
    if not tenant_id or not dossier_id:
        return
    if database_url():
        STORE.discard(tenant_id, dossier_id)
        return
    persisted = load_query_snapshot(dossier_id, tenant_id=tenant_id)
    if persisted is not None:
        STORE.put(persisted[0])


_PROGRESS_MIN_INTERVAL_SECONDS = 1.0


def _progress_writer(job_id: str, tenant_id: str, dossier_id: str, worker_token: str):
    """Persist in-step progress on the RUNNING wire (#116): every step change, else at most once a second."""
    last = {"step": None, "at": 0.0}

    def write(progress: dict) -> None:
        now = time.monotonic()
        if progress["step"] == last["step"] and now - last["at"] < _PROGRESS_MIN_INTERVAL_SECONDS:
            return
        last.update(step=progress["step"], at=now)
        wire = {**_known_wire(job_id), "status": "RUNNING", "progress": progress}
        WIRE_JOBS[job_id] = wire
        JOB_STORE.set_wire(
            job_id,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            worker_token=worker_token,
            status="RUNNING",
            wire=wire,
        )

    return write


def _attach_job_timing(result: JobResult, timing: dict) -> None:
    # Written before persist, so it carries what was measured up to the end of run_idp.
    if result.contribution is None:
        return
    result.contribution.coverage = {
        **result.contribution.coverage,
        "job_timing": {key: timing[key] for key in ("snapshot_load_ms", "claim_ms", "pipeline_ms")},
    }


def _execute_wire_job(job_id: str, payload: dict) -> None:
    """Execute one accepted wire request and retain its public result."""

    timing: dict[str, int | None] = dict.fromkeys(
        ("snapshot_load_ms", "claim_ms", "pipeline_ms", "persist_ms")
    )
    status: str | None = None
    accepted: bool | None = None
    try:
        started = time.monotonic()
        service_envelope = verify_service_envelope(payload)
        request, adapted = adapt_be_ai2_processing_request(
            payload,
            tenant_id=service_envelope.tenant_id,
            actor_id=service_envelope.actor_id,
        )
        timing["snapshot_load_ms"] = _elapsed_ms(started)
        tenant_id = request.service_envelope.tenant_id
        execution_id = uuid4().hex
        if request.semantic_profile is not None:
            from app.pipeline.frame_context import effective_context_bounds

            if os.getenv("AI2_SEMANTIC_ENABLED", "true").strip().casefold() == "true":
                effective_context_bounds(request.semantic_profile.context_bounds)
        started = time.monotonic()
        worker_token = JOB_STORE.claim(
            job_id,
            tenant_id=tenant_id,
            dossier_id=request.dossier_id,
            lease_ms=_job_lease_ms(request.policy_flags.budget_limits.max_processing_seconds),
            execution_id=execution_id,
        )
        if worker_token is None:
            status = "UNCLAIMED"
            return
        if _CLAIM_REPORT is not None:
            _CLAIM_REPORT.send((worker_token, tenant_id, request.dossier_id))
        queued = _known_wire(job_id)
        if queued:
            wire = dict(queued)
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
        timing["claim_ms"] = _elapsed_ms(started)
        egress_allowed = processing_egress_allowed()
        llm = None
        if egress_allowed:
            candidate = NineRouterClient()
            if candidate.configured():
                llm = candidate
        runtime = ProcessingRuntime(
            egress_allowed=egress_allowed,
            use_vector=request.policy_flags.use_vector,
            max_processing_seconds=request.policy_flags.budget_limits.max_processing_seconds,
            max_llm_calls=request.policy_flags.budget_limits.max_llm_calls,
            max_embedding_tokens=request.policy_flags.budget_limits.max_embedding_tokens,
            on_progress=_progress_writer(job_id, tenant_id, request.dossier_id, worker_token),
        )
        query_snapshot_digest = adapted.record.pins.source_snapshot_digest
        trace_writer = ProcessingTraceWriter(
            ProcessingTraceStore(JOB_STORE),
            tenant_id=tenant_id,
            dossier_id=request.dossier_id,
            job_id=job_id,
            snapshot_digest=query_snapshot_digest,
            execution_id=execution_id,
            worker_token=worker_token,
        )
        # AI2_PROCESSING_EGRESS_ALLOWED controls whether the configured client
        # can be used. The pipeline itself owns retry/fallback accounting.
        processing_store = InMemorySnapshotStore()
        started = time.monotonic()
        result = run_idp(
            adapted.record,
            adapted.envelope,
            llm=llm,
            store=processing_store,
            job_id=job_id,
            runtime=runtime,
            trace_writer=trace_writer,
        )
        timing["pipeline_ms"] = _elapsed_ms(started)
        _attach_job_timing(result, timing)
        processed_record = (
            processing_store.get(adapted.record.tenant_id, adapted.record.dossier_id)
            or adapted.record
        )
        wire = job_result_to_wire(result, request, query_snapshot_digest=query_snapshot_digest)
        status = wire["status"]
        started = time.monotonic()
        accepted = JOB_STORE.complete_with_snapshot(
            job_id,
            tenant_id=tenant_id,
            dossier_id=request.dossier_id,
            worker_token=worker_token,
            status=wire["status"],
            wire=wire,
            result=result.model_dump(),
            record=processed_record,
            envelope=adapted.envelope,
        )
        timing["persist_ms"] = _elapsed_ms(started)
        if accepted:
            # The finished wire carries the whole result and JOB_STORE already
            # has it (GET /jobs/{id} reads it there): keep no second copy.
            WIRE_JOBS.pop(job_id, None)
            if database_url():
                # /query reads ai2.dossier_query_snapshots on every call. A cached
                # 200-page record held ~200 MiB for the rest of the process.
                STORE.discard(tenant_id, request.dossier_id)
            else:
                persisted = load_query_snapshot(request.dossier_id, tenant_id=tenant_id)
                if persisted is not None:
                    STORE.put(persisted[0])
    except Exception as exc:  # worker boundary: every failure ends the job
        status = "FAILED"
        code = exc.code if isinstance(exc, SnapshotContractError) else "AI2_WORKER_FAILED"
        update = {
            "status": "FAILED",
            "review_state": "BLOCKED",
            "result": None,
            "errors": [{"code": code, "message": str(exc), "retryable": False}],
        }
        wire = {**_known_wire(job_id), **update}
        WIRE_JOBS[job_id] = wire
        if "worker_token" in locals() and worker_token:
            JOB_STORE.set_wire(
                job_id,
                tenant_id=request.service_envelope.tenant_id,
                dossier_id=request.dossier_id,
                worker_token=worker_token,
                status="FAILED",
                wire=wire,
            )
        else:
            # Failed before claiming: without this the job stays QUEUED forever.
            JOB_STORE.fail_unclaimed(job_id, update)
    finally:
        # Numbers and ids only; a FAILED job logs the marks it reached (the rest are None).
        timing_logger.info(
            "ai2.job_timing scope=worker job_id=%s snapshot_load_ms=%s claim_ms=%s "
            "pipeline_ms=%s persist_ms=%s status=%s accepted=%s",
            job_id,
            timing["snapshot_load_ms"],
            timing["claim_ms"],
            timing["pipeline_ms"],
            timing["persist_ms"],
            status,
            accepted,
        )


def _sweep_stale_jobs(
    store: SQLiteJobStore | None = None, *, queued_grace_ms: int = 60_000
) -> list[str]:
    """Fail jobs a dead worker left QUEUED/RUNNING so a poll always ends (ST-067)."""

    update = {
        "result": None,
        "errors": [
            {
                "code": "AI2_WORKER_RESTARTED",
                "message": ISSUE_MESSAGES_VI["AI2_WORKER_RESTARTED"],
                "retryable": True,
            }
        ],
    }
    target = store or JOB_STORE
    with _HELD_LOCK:
        held = sorted(_HELD_JOB_IDS)
    # Renew first: a held job waiting for a thread is live, not orphaned (I3).
    target.hold_queued(held, lease_ms=QUEUED_HOLD_MS)
    swept = target.sweep_stale(update, queued_grace_ms=queued_grace_ms)
    if swept:
        trace_store = ProcessingTraceStore(target)
        for job_id in swept:
            try:
                trace_store.finalize_stale_job(job_id)
            except Exception as exc:
                logger.warning(
                    "ai2.processing_trace_finalize_failed job_id=%s code=%s",
                    job_id,
                    type(exc).__name__,
                )
        logger.warning("ai2.jobs_swept count=%s job_ids=%s", len(swept), swept)
    return swept


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
        "review_queue_status": "NOT_RUN"
        if job is None
        else ("EMPTY_QUEUE" if not rec.review_items else "HAS_REVIEW_ITEMS"),
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
        "authoritative_publish_blocked": source == "ai1_result"
        and bool(ai1.get("review_required", True)),
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
        gates.append(
            {
                "code": "PROCESSING_BUDGET_EXCEEDED",
                "operation": "external_processing",
                "deterministic_action": "ALLOW_PARTIAL_REVIEW",
            }
        )
    if rec.embedding_budget_hit():
        gates.append(
            {
                "code": "EMBEDDING_BUDGET_EXCEEDED",
                "operation": "embedding_vector_recall",
                "deterministic_action": "ALLOW_WITHOUT_VECTOR",
            }
        )
    if not rec.egress_approved:
        gates.append(
            {
                "code": "EGRESS_DENIED",
                "operation": "llm_or_embedding",
                "deterministic_action": "ALLOW_LOCAL_ONLY",
            }
        )
    if rec.index_status == "LEASED":
        gates.append(
            {
                "code": "INDEX_LEASED",
                "operation": "publish_or_index_write",
                "deterministic_action": "BLOCK",
            }
        )
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
    task = {
        **task,
        "policy_flags": {
            **(task.get("policy_flags") or {}),
            "use_llm": use_llm,
            "use_vector": use_vector,
            "egress_allowed": rec.egress_approved,
        },
    }
    policy = _policy_view(rec)
    llm_gate = (
        rec.index_status == "LEASED" or rec.processing_budget_hit() or not rec.egress_approved
    )
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
                and (not raw.get("citation_id") or raw.get("citation_id") == chosen.citation_id)
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
        "cells": [
            cell.model_dump()
            for cell in table.cells
            if safe_offset <= cell.row_index < safe_offset + safe_limit
        ],
        "cell_citations": citation_rows,
        "has_geometry": bool(table.cells or table.cell_citations),
    }


# /health and /readyz are polled (deploy.sh, monitors). Each probe used to
# build a new OpenAI client and send a real chat request: with the old 15 s
# Docker healthcheck, ~5,800 paid requests a day. One client is reused while
# the LLM settings stay the same, and a probe result is reused for a while.
_PROBE_LOCK = threading.Lock()
_PROBE_CLIENT: tuple[tuple[str, str, str], NineRouterClient] | None = None
_PROBE_RESULT: tuple[tuple, str, float] | None = None
_PROBE_FAILURE_TTL_SECONDS = 10.0


def _llm_settings_key() -> tuple[str, str, str]:
    api_key = os.getenv("AI2_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    return (
        os.getenv("AI2_LLM_BASE_URL", ""),
        os.getenv("AI2_LLM_MODEL", ""),
        hashlib.sha256(api_key.encode("utf-8")).hexdigest(),
    )


def _probe_client() -> NineRouterClient:
    global _PROBE_CLIENT
    key = _llm_settings_key()
    with _PROBE_LOCK:
        if _PROBE_CLIENT is None or _PROBE_CLIENT[0] != key:
            _PROBE_CLIENT = (key, NineRouterClient())
        return _PROBE_CLIENT[1]


def _probe_ttl_seconds() -> float:
    try:
        return max(0.0, float(os.getenv("AI2_READYZ_PROBE_TTL_SECONDS", "60")))
    except ValueError:
        return 60.0


def _cached_llm_status(llm: NineRouterClient) -> str:
    """``llm_status`` of ``llm``, reused for ``AI2_READYZ_PROBE_TTL_SECONDS``
    when ready and for 10 s otherwise, so a recovered provider shows up fast."""

    global _PROBE_RESULT
    ttl = _probe_ttl_seconds()
    key = (_llm_settings_key(), llm_status)
    now = time.monotonic()
    cached = _PROBE_RESULT
    if ttl > 0 and cached is not None and cached[0] == key:
        _, state, at = cached
        if now - at < (ttl if state == "ready" else min(ttl, _PROBE_FAILURE_TTL_SECONDS)):
            return state
    state = llm_status(llm)
    _PROBE_RESULT = (key, state, time.monotonic())
    return state


def _capability_snapshot(*, probe_embedding: bool = False) -> dict:
    """Return provider capability without exposing credentials.

    Liveness stays cheap at /healthz. The explicit readiness route is used by
    runners/deployments before an LLM/vector E2E run so a missing provider is
    visible instead of silently becoming lexical-only behavior.
    """

    llm = _probe_client()
    if probe_embedding or os.getenv("AI2_EMBEDDING_DISCOVERY_ENABLED", "false").casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        embedding = EMBEDDING_CLIENT.discover(egress_approved=True).as_dict()
    else:
        embedding = {"status": "NOT_RUN", "models": [], "selected_model": None, "dimensions": None}
    llm_state = _cached_llm_status(llm)
    return {
        "llm_status": llm_state,
        "llm": llm_state,
        "model": llm.model if llm.configured() else "",
        "persist": str(DATA),
        "embedding": embedding,
    }


@app.get("/health")
def health() -> dict:
    capabilities = _capability_snapshot()
    return {"status": "ok", **capabilities}


@app.get("/readyz")
def readyz() -> dict:
    full_path = all(
        _env_flag(name, False)
        for name in (
            "AI2_SEMANTIC_ENABLED",
            "AI2_PROCESSING_EGRESS_ALLOWED",
            "AI2_QUERY_EGRESS_ALLOWED",
            "AI2_QUERY_USE_LLM",
            "AI2_QUERY_USE_VECTOR",
            "AI2_VECTOR_RECALL_ENABLED",
        )
    )
    capabilities = _capability_snapshot(probe_embedding=full_path)
    llm_ready = str(capabilities["llm_status"]).casefold() == "ready"
    embedding_ready = capabilities["embedding"].get("status") == "READY"
    if full_path and (not llm_ready or not embedding_ready):
        capabilities["status"] = "blocked"
        capabilities["reason"] = "full_llm_vector_capability_not_ready"
        raise HTTPException(status_code=503, detail=capabilities)
    return {"status": "ready", **capabilities}


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
                    "Backend handoff contains metadata but no canonical snapshot content/citations"
                ),
            }
        ],
        "ai2": {"service": "ai2", "tenant_id": request.headers.get("X-Tenant-Id", "")},
    }


def _query_pair_relations(record: Any, digest: str | None) -> list[dict[str, Any]]:
    """Stored pair relations of the snapshot being queried; empty when unavailable."""

    if record.pair_relations:
        return [
            {
                "label": getattr(r.label, "value", r.label),
                "node_a_id": r.node_a_id,
                "node_b_id": r.node_b_id,
            }
            for r in record.pair_relations
        ]
    if not database_url() or not digest:
        return []
    from sqlalchemy import select

    from app.db.engine import get_engine
    from app.db.tables import contract_pair_relations as table

    try:
        with get_engine().connect() as cx:
            rows = (
                cx.execute(
                    select(table.c.label, table.c.node_a_id, table.c.node_b_id).where(
                        table.c.tenant_id == record.tenant_id,
                        table.c.dossier_id == record.dossier_id,
                        table.c.source_snapshot_digest.in_([digest, f"sha256:{digest}"]),
                    )
                )
                .mappings()
                .all()
            )
    except Exception:
        logger.warning("ai2.query_pair_relations_unavailable", exc_info=True)
        return []
    return [dict(row) for row in rows]


@app.post("/query")
@app.post("/api/v1/query")
def query_from_backend(payload: dict) -> dict:
    """Answer against the canonical record received through ``/jobs/idp``."""

    try:
        service_envelope = verify_service_envelope(payload, required_scope="ai2.query")
    except ServiceEnvelopeError as exc:
        # AI2_QUERY_REQUIRE_SIGNATURE=false keeps the unsigned compatibility
        # lane (local compose only); a present but invalid envelope is always
        # rejected.
        unsigned_allowed = not _env_flag("AI2_QUERY_REQUIRE_SIGNATURE", True)
        if unsigned_allowed and not isinstance(payload.get("service_envelope"), dict):
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
    stored_envelope: ToolEnvelope | object | None = None
    tenant_id = (
        service_envelope.tenant_id
        if service_envelope is not None
        else str(payload.get("tenant_id") or "").strip()
    )
    record = STORE.get(tenant_id, dossier_id) if tenant_id else None
    if record is None or database_url() or service_envelope is None:
        hydrated = load_query_snapshot(dossier_id, tenant_id=tenant_id or None)
        if hydrated is not None:
            record, stored_envelope = hydrated
            if database_url():
                # Reloaded per query: caching it only pins memory (and a
                # stale entry must not outlive the newer snapshot).
                STORE.discard(record.tenant_id, record.dossier_id)
            else:
                STORE.put(record)
        elif database_url() or service_envelope is None:
            record = None

    if record is not None:
        expected_digest = bare_sha256_digest(record.pins.source_snapshot_digest)
        if expected_digest:
            # The versioned Backend contract must bind the query to the
            # current canonical snapshot. Keep the older signed compatibility
            # lane readable for existing callers that predate this field.
            requires_evidence_context = query_contract_version == "ai2.query.v1" or bool(
                requested_digest
            )
            if requires_evidence_context and (
                not requested_digest or bare_sha256_digest(requested_digest) != expected_digest
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
            if service_envelope is not None:
                member_ids = [source.file_id for source in record.source_files if source.file_id]
                envelope = ToolEnvelope(
                    auth=AuthContext(
                        actor_id=service_envelope.actor_id,
                        tenant_id=service_envelope.tenant_id,
                        dossier_id=dossier_id,
                        acl_revision=record.acl_revision,
                        # D-5: a valid signed envelope for this tenant/dossier
                        # carries READ_CONTENT; Backend owns per-user ACL.
                        permissions=["READ_CONTENT"],
                        member_ids=member_ids,
                        member_documents={},
                        lifecycle=record.lifecycle,
                    ),
                    pins=record.pins,
                )
            else:
                envelope = stored_envelope
            policy_flags = _query_policy_flags()
            consent = (
                service_envelope is not None
                and payload.get("content_sharing_consent") is True
                and record.content_sharing_consent
            )
            policy_flags["egress_allowed"] = policy_flags["egress_allowed"] and consent
            policy_flags["use_llm"] = policy_flags["use_llm"] and consent
            policy_flags["use_vector"] = policy_flags["use_vector"] and consent
            llm = None
            if policy_flags["egress_allowed"] and policy_flags["use_llm"]:
                timeout = query_llm_timeout_seconds()
                candidate = NineRouterClient(timeout=timeout)
                if candidate.configured():
                    llm = DeadlineLLM(candidate, timeout)
            query_store = InMemorySnapshotStore()
            query_store.put(record)
            task = classify_ask(query)
            task["pair_relations"] = _query_pair_relations(record, expected_digest)
            result = QueryRouter(
                query_store,
                ToolGateway(query_store, signed_principal=service_envelope is not None),
                llm=llm,
                vector_recall=_vector_service(
                    policy_flags["use_vector"],
                    ProcessingRuntime(
                        egress_allowed=policy_flags["egress_allowed"],
                        max_embedding_tokens=query_embedding_token_cap(),
                    ),
                ),
            ).query(
                envelope,
                query,
                task,
                policy_flags=policy_flags,
            )
            citations = _enrich_citations(result.get("citations") or [], record)
            answer = result.get("answer")
            if answer is not None and not isinstance(answer, str):
                answer = json.dumps(answer, ensure_ascii=False)
            review_state = result.get("review_state")
            state = review_state or result.get("state") or "INSUFFICIENT_EVIDENCE"
            return {
                "state": "ANSWERED" if state == "PASS" else state,
                "review_state": review_state,
                "connected": True,
                "answer": answer,
                "citations": citations,
                "retrieval_layer": {
                    **(result.get("retrieval_layer") or {}),
                    **(
                        {"reason_code": "EMBEDDING_BUDGET_EXCEEDED"}
                        if (result.get("retrieval_layer") or {}).get("vector_status")
                        == "BUDGET_EXCEEDED"
                        else {}
                    ),
                    "dossier_id": dossier_id,
                    "snapshot_version": payload.get("snapshot_version"),
                    "snapshot_digest": expected_digest,
                    "source": "ai2.canonical.store",
                },
                "reasoning_trace": result.get("reasoning_trace") or result.get("steps") or [],
                "used_llm": bool(result.get("used_llm", False)),
            }
    return {
        "state": "INSUFFICIENT_EVIDENCE",
        "connected": True,
        "answer": "AI2 chưa nhận được snapshot/citation có thẩm quyền cho hồ sơ này.",
        "citations": [],
        "retrieval_layer": {
            "dossier_id": dossier_id,
            "snapshot_version": payload.get("snapshot_version"),
            "snapshot_digest": requested_digest or None,
        },
        "reasoning_trace": [
            {
                "code": "AI2_QUERY_SNAPSHOT_NOT_FOUND",
                "message": (
                    "Query chỉ được trả lời sau khi AI2 nhận canonical snapshot và citation map"
                ),
            }
        ],
        "used_llm": False,
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
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        try:
            input_payload, demo_meta = normalize_ocr_json(snapshot, source_digest=source_digest)
        except ValueError as exc:
            raise HTTPException(
                422, {"code": "OCR_JSON_DEMO_INVALID", "message": str(exc)}
            ) from exc
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
async def workspace_ai1_result(
    request: Request, dossier_id: str | None = None, scope_id: str | None = None
) -> dict:
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
                raise HTTPException(
                    422, {"code": "RESULT_JSON_INVALID", "message": str(exc)}
                ) from exc
        elif isinstance(artifact, str):
            try:
                payload = json.loads(artifact)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    422, {"code": "RESULT_JSON_INVALID", "message": str(exc)}
                ) from exc
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
        raise HTTPException(
            422, {"code": "RESULT_CONTRACT_INVALID", "message": "result root must be an object"}
        )
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
        role = (
            "annex"
            if (i > 0 or "annex" in name.lower() or "phu" in name.lower() or "phụ" in name.lower())
            else "body"
        )
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
    return Response(
        content=blob,
        media_type=media,
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )


@app.get("/api/workspace/{session_id}")
def workspace_get(session_id: str) -> dict:
    return _session_view(session_id)


@app.get("/api/workspace/{session_id}/tree")
def workspace_tree(session_id: str) -> dict:
    s = _require_session(session_id)
    rec: DossierRecord = s["record"]
    nodes = rec.evidence_nodes()
    return {
        "session_id": session_id,
        "tree": build_tree(nodes),
        "n_nodes": len(nodes),
        "n_raw_nodes": len(rec.nodes),
    }


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
        "status": "NOT_RUN"
        if s.get("job") is None
        else ("EMPTY_QUEUE" if not rec.review_items else "HAS_REVIEW_ITEMS"),
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
        c.candidate_id for c in (job.contribution.candidates if job and job.contribution else [])
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
    return {
        "task_id": task["id"],
        **_reason_output(rec, env, task, use_llm=body.use_llm, use_vector=body.use_vector),
    }


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
                "input_kind": "synthetic_fixture"
                if "synthetic" in pack.tags
                else "catalog_fixture",
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
        "pages": [
            {"page": p.page_number, "quality": p.quality, "text": p.text[:400]}
            for p in rec.pages[:8]
        ],
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
        **_reason_output(
            rec, pack.envelope, task, use_llm=body.use_llm, use_vector=body.use_vector
        ),
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
    return {
        "task_id": task["id"],
        **_reason_output(
            rec, pack.envelope, task, use_llm=body.use_llm, use_vector=body.use_vector
        ),
    }


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
        raise HTTPException(
            status_code=401, detail={"code": exc.code, "message": str(exc)}
        ) from exc

    try:
        request, adapted = adapt_be_ai2_processing_request(
            payload,
            tenant_id=service_envelope.tenant_id,
            actor_id=service_envelope.actor_id,
        )
    except SnapshotContractError as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": str(exc)}
        ) from exc

    queued = _queued_wire_result(request, "pending", adapted.record.pins.source_snapshot_digest)
    try:
        stored, created = JOB_STORE.create_or_get(
            tenant_id=service_envelope.tenant_id,
            dossier_id=request.dossier_id,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            attempt=request.attempt,
            request=copy.deepcopy(payload),
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
    WIRE_IDEMPOTENCY[(service_envelope.tenant_id, request.idempotency_key, request.attempt)] = (
        job_id
    )
    WIRE_JOBS[job_id] = wire
    if created or stored["status"] in {"QUEUED", "RUNNING"}:
        # Hand the worker the exact signed payload: a re-dumped model differs
        # from it (defaults, OCR-lab digest normalization) and would fail the
        # worker's envelope re-verification (payload_sha256).
        with _HELD_LOCK:
            _HELD_JOB_IDS.add(job_id)
        background_tasks.add_task(_run_wire_job, job_id, payload)
    return wire


@app.get("/jobs/{job_id}")
def get_job(
    job_id: str, x_ai2_service_envelope: str | None = Header(default=None)
) -> dict | JobResult:
    stored = JOB_STORE.get(job_id)
    if stored is None:
        raise HTTPException(404, job_id)
    if not x_ai2_service_envelope:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "SERVICE_ENVELOPE_MISSING",
                "message": "polling requires a signed service envelope",
            },
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
            detail={
                "code": "JOB_OWNER_MISMATCH",
                "message": "job does not belong to this service principal",
            },
        )
    wire = dict(stored["wire"])
    wire["job_id"] = job_id
    if str(wire.get("status") or "").upper() in {"QUEUED", "RUNNING"}:
        WIRE_JOBS[job_id] = wire
    else:
        # A finished wire holds the full result; it is served from JOB_STORE.
        WIRE_JOBS.pop(job_id, None)
    return wire


def _same_source_text(quote: str, source: str) -> bool:
    """Compare source evidence without changing the stored raw OCR text."""

    if not quote or not source:
        return False
    normalized_quote = " ".join(quote.split()).casefold()
    normalized_source = " ".join(source.split()).casefold()
    return normalized_quote in normalized_source
