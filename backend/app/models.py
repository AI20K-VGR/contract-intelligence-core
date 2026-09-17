import time

from sqlalchemy import JSON, CheckConstraint, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.domain import uid


class Dossier(Base):
    __tablename__ = "dossiers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[str] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(default=1)
    review_version: Mapped[int] = mapped_column(default=0)
    active_job_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (CheckConstraint("role IN ('contract', 'appendix')"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    dossier_id: Mapped[str] = mapped_column(ForeignKey("dossiers.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int]
    storage_key: Mapped[str] = mapped_column(String(100))


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded','processing','extracted','pending_review','reviewed','approved','failed')"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    dossier_id: Mapped[str] = mapped_column(ForeignKey("dossiers.id"), index=True)
    dossier_revision: Mapped[int]
    status: Mapped[str] = mapped_column(String(24), default="uploaded", index=True)
    manifest: Mapped[dict] = mapped_column(JSON)
    config: Mapped[dict] = mapped_column(JSON)
    failure_code: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("job_id", "task_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    task_key: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[float] = mapped_column(Float, default=0, index=True)
    retry_at: Mapped[float] = mapped_column(Float, default=0)
    output: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(60))


class Attempt(Base):
    __tablename__ = "task_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    number: Mapped[int]
    started_at: Mapped[float] = mapped_column(Float)
    finished_at: Mapped[float | None] = mapped_column(Float)
    error_code: Mapped[str | None] = mapped_column(String(60))


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), unique=True)
    result_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)


class ReviewEvent(Base):
    __tablename__ = "review_events"
    __table_args__ = (
        UniqueConstraint("job_id", "version"),
        CheckConstraint("action IN ('confirm','correct','reject','needs_more_evidence')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    target_id: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(2000))
    correction: Mapped[dict | None] = mapped_column(JSON)
    version: Mapped[int]
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), unique=True)
    dossier_revision: Mapped[int]
    review_version: Mapped[int]
    result_hash: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Idempotency(Base):
    __tablename__ = "idempotency"
    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)


class AnalysisRevision(Base):
    __tablename__ = "analysis_revisions"
    __table_args__ = (UniqueConstraint("job_id", "review_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    review_version: Mapped[int]
    result_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_ids: Mapped[list] = mapped_column(JSON)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    dossier_id: Mapped[str] = mapped_column(ForeignKey("dossiers.id"), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(60))
    object_type: Mapped[str] = mapped_column(String(40))
    object_id: Mapped[str] = mapped_column(String(80))
    request_id: Mapped[str | None] = mapped_column(String(36))
    result: Mapped[str] = mapped_column(String(20), default="success")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
