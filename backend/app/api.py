import time
from contextlib import contextmanager
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.audit import audit_trail, log_event
from app.config import settings
from app.db import Session
from app.domain import DomainError, require, uid
from app.ingestion import ingest
from app.models import Batch, Document, Dossier, Idempotency, Job, Snapshot, Task
from app.orchestration import enqueue
from app.policy import Actor, allowed, authenticate
from app.reporting import batch_summary
from app.review import append_review, approve, effective_result, review_state
from app.storage import ArtifactStore, canonical, digest
from app.tables import build_logical_tables

app = FastAPI(title="Contract Intelligence", version="0.1.0")
REQUESTS = Counter("ci_http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("ci_http_duration_seconds", "HTTP duration", ["route"])


@app.middleware("http")
async def request_context(request, call_next):
    request.state.request_id = uid()
    start = time.monotonic()
    response = await call_next(request)
    route = getattr(request.scope.get("route"), "path", "unmatched")
    REQUESTS.labels(request.method, route, response.status_code).inc()
    LATENCY.labels(route).observe(time.monotonic() - start)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(DomainError)
async def domain_error(request, exc):
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.code,
                "retryable": False,
                "request_id": request.state.request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def internal_error(request, _exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Request failed",
                "retryable": False,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


def store():
    return ArtifactStore(settings.artifact_root)


@contextmanager
def transaction():
    with Session.begin() as db:
        yield db


def mutate(db, actor, key, operation, payload, action):
    require(0 < len(key) <= 120, "INVALID_IDEMPOTENCY_KEY", 422)
    # Serialize the same actor/key across processes, then compare operation + body.
    record_key = digest(canonical([actor.id, key]))
    if db.bind.dialect.name == "postgresql":
        number = int(record_key[:15], 16)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": number})
    request_hash = digest(canonical([operation, payload]))
    old = db.get(Idempotency, record_key)
    if old:
        require(old.request_hash == request_hash, "IDEMPOTENCY_KEY_REUSED")
        return old.response
    response = action()
    db.add(Idempotency(key=record_key, request_hash=request_hash, response=response))
    return response


class CreateDossier(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ReviewBody(BaseModel):
    job_id: str
    target_id: str
    action: Literal["confirm", "correct", "reject", "needs_more_evidence"]
    expected_revision: int = Field(ge=0)
    reason: str = Field(default="", max_length=2000)
    correction: dict | None = None


class ApproveBody(BaseModel):
    expected_revision: int = Field(ge=0)


class BatchBody(BaseModel):
    dossier_ids: list[str] = Field(min_length=1, max_length=100)


@app.get("/api/v1/health/live")
def live():
    return {"status": "alive"}


@app.get("/api/v1/health/ready")
def ready():
    try:
        with transaction() as db:
            revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
            require(revision == "0003", "SCHEMA_NOT_READY", 503)
        import tempfile

        with tempfile.TemporaryFile(dir=store().root) as probe:
            probe.write(b"ready")
        return {"status": "ready"}
    except Exception as exc:
        raise DomainError("NOT_READY", 503) from exc


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type="text/plain; version=0.0.4")


@app.post("/api/v1/dossiers", status_code=201)
def create_dossier(
    body: CreateDossier, request: Request,
    actor: Actor = Depends(authenticate), idempotency_key: str = Header(),
):
    allowed(actor, "operator")
    with transaction() as db:

        def create():
            dossier = Dossier(title=body.title, created_by=actor.id)
            db.add(dossier)
            db.flush()
            log_event(db, dossier.id, actor.id, "dossier.created", "dossier", dossier.id,
                      request.state.request_id)
            return {"id": dossier.id, "revision": dossier.revision}

        return mutate(db, actor, idempotency_key, "dossier.create", body.model_dump(), create)


@app.get("/api/v1/dossiers")
def dossiers(
    actor: Actor = Depends(authenticate),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    with transaction() as db:
        records = list(
            db.scalars(
                select(Dossier)
                .order_by(Dossier.created_at.desc(), Dossier.id)
                .offset(offset)
                .limit(limit + 1)
            )
        )
        items = []
        for d in records[:limit]:
            job = db.get(Job, d.active_job_id) if d.active_job_id else None
            items.append(
                {
                    "id": d.id,
                    "title": d.title,
                    "revision": d.revision,
                    "review_version": d.review_version,
                    "active_job_id": d.active_job_id,
                    "status": job.status if job else "uploaded",
                }
            )
        return {"items": items, "next_offset": offset + limit if len(records) > limit else None}


@app.post("/api/v1/dossiers/{dossier_id}/documents", status_code=201)
def upload(
    dossier_id: str,
    request: Request,
    file: UploadFile = File(),
    role: Literal["contract", "appendix"] = Form(),
    actor: Actor = Depends(authenticate),
    idempotency_key: str = Header(),
):
    allowed(actor, "operator")
    content = file.file.read(settings.max_upload_bytes + 1)
    require(len(content) <= settings.max_upload_bytes, "UPLOAD_TOO_LARGE", 413)
    with transaction() as db:

        def do_upload():
            result = ingest(db, store(), dossier_id, role, content, settings)
            log_event(db, dossier_id, actor.id, "document.uploaded", "document", result["id"],
                      request.state.request_id, detail={"role": role, "page_count": result["page_count"]})
            return result

        return mutate(
            db,
            actor,
            idempotency_key,
            f"{dossier_id}.upload",
            {"sha256": digest(content), "role": role},
            do_upload,
        )


@app.post("/api/v1/dossiers/{dossier_id}/jobs", status_code=202)
def start(
    dossier_id: str, request: Request,
    actor: Actor = Depends(authenticate), idempotency_key: str = Header(),
):
    allowed(actor, "operator")
    with transaction() as db:

        def do_start():
            result = enqueue(db, dossier_id, settings)
            log_event(db, dossier_id, actor.id, "job.enqueued", "job", result["id"],
                      request.state.request_id)
            return result

        return mutate(db, actor, idempotency_key, f"{dossier_id}.start", {}, do_start)


@app.get("/api/v1/jobs/{job_id}")
def job_status(job_id: str, actor: Actor = Depends(authenticate)):
    with transaction() as db:
        job = db.get(Job, job_id)
        require(job is not None, "JOB_NOT_FOUND", 404)
        tasks = list(db.scalars(select(Task).where(Task.job_id == job_id)))
        return {
            "id": job.id,
            "dossier_id": job.dossier_id,
            "status": job.status,
            "failure_code": job.failure_code,
            "stage": "pages" if job.status == "processing" else job.status,
            "progress": {
                "total": len(tasks),
                "completed": sum(t.status == "completed" for t in tasks),
                "failed": sum(t.status == "failed" for t in tasks),
            },
            "attempts": sum(t.attempts for t in tasks),
        }


@app.post("/api/v1/jobs/{job_id}/retry", status_code=202)
def retry(
    job_id: str, request: Request,
    actor: Actor = Depends(authenticate), idempotency_key: str = Header(),
):
    allowed(actor, "operator")
    with transaction() as db:

        def create_retry():
            old = db.get(Job, job_id)
            require(old is not None, "JOB_NOT_FOUND", 404)
            require(old.status == "failed", "JOB_NOT_FAILED")
            dossier = db.get(Dossier, old.dossier_id)
            require(dossier.active_job_id == old.id, "STALE_RUN")
            response = enqueue(db, old.dossier_id, settings)
            new = db.get(Job, response["id"])
            new.config = old.config
            cached = {
                t.task_key: t.output
                for t in db.scalars(
                    select(Task).where(Task.job_id == job_id, Task.status == "completed")
                )
            }
            for task in db.scalars(select(Task).where(Task.job_id == new.id)):
                if task.task_key in cached:
                    task.status, task.output = "completed", cached[task.task_key]
            # A batch tracks the current retry for each fixed dossier slot.
            for batch in db.scalars(select(Batch).with_for_update()):
                if job_id in batch.job_ids:
                    batch.job_ids = [new.id if item == job_id else item for item in batch.job_ids]
            log_event(db, old.dossier_id, actor.id, "job.retried", "job", new.id,
                      request.state.request_id, detail={"previous_job_id": old.id})
            return {**response, "previous_job_id": old.id, "reused_pages": len(cached)}

        return mutate(db, actor, idempotency_key, f"{job_id}.retry", {}, create_retry)


def load_result(db, dossier_id, run_id=None):
    dossier = db.get(Dossier, dossier_id)
    require(dossier is not None, "DOSSIER_NOT_FOUND", 404)
    job_id = run_id or dossier.active_job_id
    job = db.get(Job, job_id) if job_id else None
    require(job is not None and job.dossier_id == dossier_id, "RUN_NOT_FOUND", 404)
    snapshot = db.scalar(select(Snapshot).where(Snapshot.job_id == job.id))
    require(snapshot is not None, "RESULT_NOT_READY")
    return dossier, job, snapshot


@app.get("/api/v1/dossiers/{dossier_id}/results")
def results(dossier_id: str, run_id: str | None = None, actor: Actor = Depends(authenticate)):
    with transaction() as db:
        dossier, job, snapshot = load_result(db, dossier_id, run_id)
        return {
            "machine": snapshot.result,
            "effective": effective_result(db, job, snapshot)[0],
            "effective_result_hash": effective_result(db, job, snapshot)[1],
            "review": review_state(db, job, snapshot),
            "review_version": dossier.review_version,
            "status": job.status,
            "result_hash": snapshot.result_hash,
        }


@app.get("/api/v1/dossiers/{dossier_id}/documents")
def documents(dossier_id: str, actor: Actor = Depends(authenticate)):
    with transaction() as db:
        require(db.get(Dossier, dossier_id) is not None, "DOSSIER_NOT_FOUND", 404)
        docs = list(db.scalars(select(Document).where(Document.dossier_id == dossier_id)))
        return {
            "items": [
                {"id": d.id, "role": d.role, "page_count": d.page_count, "sha256": d.sha256}
                for d in docs
            ]
        }


@app.get("/api/v1/dossiers/{dossier_id}/audit")
def audit(dossier_id: str, actor: Actor = Depends(authenticate)):
    with transaction() as db:
        require(db.get(Dossier, dossier_id) is not None, "DOSSIER_NOT_FOUND", 404)
        return {"items": audit_trail(db, dossier_id)}


@app.get("/api/v1/dossiers/{dossier_id}/{collection}")
def collection(
    dossier_id: str,
    collection: Literal["clauses", "tables", "facts", "findings", "conflicts"],
    run_id: str | None = None,
    view: Literal["machine", "effective"] = "effective",
    actor: Actor = Depends(authenticate),
):
    with transaction() as db:
        _, job, snapshot = load_result(db, dossier_id, run_id)
        result = snapshot.result if view == "machine" else effective_result(db, job, snapshot)[0]
        items = result["findings" if collection == "conflicts" else collection]
        if collection == "conflicts":
            items = [
                f
                for f in items
                if f["disposition"]
                in ("comparable_difference", "candidate_amendment", "insufficient_evidence")
            ]
        response = {"items": items, "run_id": job.id, "is_partial": snapshot.result["is_partial"]}
        if collection == "tables":
            response["logical_items"] = build_logical_tables(items)
            response["reconstruction_version"] = "table-geometry-v1"
        return response


@app.get("/api/v1/documents/{document_id}/file")
def document_file(document_id: str, actor: Actor = Depends(authenticate)):
    with transaction() as db:
        doc = db.get(Document, document_id)
        require(doc is not None, "DOCUMENT_NOT_FOUND", 404)
        return FileResponse(store().path(doc.storage_key), media_type="application/pdf")


@app.get("/api/v1/documents/{document_id}/pages/{number}/text")
def page_text(document_id: str, number: int, run_id: str, actor: Actor = Depends(authenticate)):
    with transaction() as db:
        task = db.scalar(
            select(Task).where(
                Task.job_id == run_id,
                Task.task_key == f"{document_id}:{number}",
                Task.status == "completed",
            )
        )
        require(task is not None and task.output, "PAGE_NOT_FOUND", 404)
        output = task.output
        return {
            "engine": output.get("engine"),
            "status": output.get("status"),
            "issue": output.get("issue"),
            "lines": [
                {"id": line["id"], "text": line["text"], "bbox": line["bbox"]}
                for line in output.get("lines", [])
            ],
        }


@app.get("/api/v1/citations/{citation_id}/resolve")
def resolve(citation_id: str, actor: Actor = Depends(authenticate)):
    with transaction() as db:
        run_id = citation_id.split(":", 1)[0]
        snapshot = db.scalar(select(Snapshot).where(Snapshot.job_id == run_id))
        require(snapshot is not None, "CITATION_NOT_FOUND", 404)
        cit = next((c for c in snapshot.result["citations"] if c["id"] == citation_id), None)
        require(cit is not None, "CITATION_NOT_FOUND", 404)
        doc = db.get(Document, cit["document_id"])
        require(
            digest(store().path(doc.storage_key).read_bytes()) == cit["source_hash"],
            "SOURCE_HASH_MISMATCH",
        )
        return {
            **cit,
            "page_url": f"/api/v1/documents/{doc.id}/pages/{cit['page_number']}?run_id={run_id}",
        }


@app.get("/api/v1/documents/{document_id}/pages/{number}")
def page_image(document_id: str, number: int, run_id: str, actor: Actor = Depends(authenticate)):
    with transaction() as db:
        task = db.scalar(
            select(Task).where(
                Task.job_id == run_id,
                Task.task_key == f"{document_id}:{number}",
                Task.status == "completed",
            )
        )
        require(task is not None and task.output, "PAGE_NOT_FOUND", 404)
        return FileResponse(store().path(task.output["image_key"]), media_type="image/png")


@app.post("/api/v1/review-events", status_code=201)
def review(
    body: ReviewBody, request: Request,
    actor: Actor = Depends(authenticate), idempotency_key: str = Header(),
):
    allowed(actor, "reviewer")
    with transaction() as db:
        return mutate(
            db,
            actor,
            idempotency_key,
            "review",
            body.model_dump(),
            lambda: append_review(db, body, actor, request.state.request_id),
        )


@app.post("/api/v1/dossiers/{dossier_id}/approve", status_code=201)
def approval(
    dossier_id: str,
    body: ApproveBody,
    request: Request,
    actor: Actor = Depends(authenticate),
    idempotency_key: str = Header(),
):
    allowed(actor, "reviewer")
    with transaction() as db:
        return mutate(
            db,
            actor,
            idempotency_key,
            f"{dossier_id}.approve",
            body.model_dump(),
            lambda: approve(db, dossier_id, body.expected_revision, actor, request.state.request_id),
        )


@app.post("/api/v1/batches", status_code=202)
def create_batch(
    body: BatchBody, request: Request,
    actor: Actor = Depends(authenticate), idempotency_key: str = Header(),
):
    allowed(actor, "operator")
    require(len(set(body.dossier_ids)) == len(body.dossier_ids), "DUPLICATE_DOSSIER", 422)
    with transaction() as db:

        def create():
            batch = Batch(
                job_ids=[enqueue(db, item, settings)["id"] for item in sorted(body.dossier_ids)]
            )
            db.add(batch)
            db.flush()
            for dossier_id in body.dossier_ids:
                log_event(db, dossier_id, actor.id, "batch.created", "batch", batch.id,
                          request.state.request_id)
            return {"id": batch.id, "job_ids": batch.job_ids}

        return mutate(db, actor, idempotency_key, "batch", body.model_dump(), create)


@app.get("/api/v1/batches/{batch_id}")
def get_batch(batch_id: str, actor: Actor = Depends(authenticate)):
    with transaction() as db:
        return batch_summary(db, db.get(Batch, batch_id))


@app.get("/api/v1/reports/quality")
def quality(actor: Actor = Depends(authenticate)):
    return {"status": "not_evaluated", "dataset": None, "sample_size": 0, "metrics": None}


@app.get("/api/v1/reports/costs")
def costs(actor: Actor = Depends(authenticate)):
    return {
        "profile": "local_baseline",
        "provider_calls": 0,
        "provider_cost": "0",
        "currency": "USD",
        "compute_cost": None,
        "compute_cost_status": "not_measured",
    }
