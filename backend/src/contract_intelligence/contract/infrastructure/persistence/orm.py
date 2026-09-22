"""SQLAlchemy ORM models cho Contract bounded context.

Tables (theo DOC-04b/DOC-04c):
    dossier       — aggregate root
    document      — file PDF thuộc dossier (CONTRACT | ANNEX)
    job           — 1 lần xử lý dossier qua pipeline (Sprint 2 placeholder)
    manifest      — manifest phân loại tài liệu sau preprocessing
    manifest_item — 1 row trong manifest
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.persistence.base import Base


class DossierORM(Base):
    """ORM cho bảng ``dossier`` — aggregate root."""

    __tablename__ = "dossier"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    batch_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="uploaded")
    has_conflicts: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(
        "metadata", JSON, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_dossier_tenant_status", "tenant_id", "status"),)


class DocumentORM(Base):
    """ORM cho bảng ``document`` — file PDF trong dossier."""

    __tablename__ = "document"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(
        Text, ForeignKey("dossier.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)  # CONTRACT | ANNEX
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    blob_uri: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    lang_detected: Mapped[str] = mapped_column(Text, nullable=False, server_default="vi")
    signing_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_document_dossier_order", "dossier_id", "order_index"),
        UniqueConstraint("dossier_id", "sha256", name="uq_document_dossier_sha"),
    )


class JobORM(Base):
    """ORM cho bảng ``job`` — 1 lần chạy dossier qua pipeline.

    Postgres job queue (no Redis/Celery): workers claim rows with
    ``SELECT … FOR UPDATE SKIP LOCKED`` and hold ``lease_expires_at``.
    An async reaper resets rows whose lease has expired back to ``uploaded``.
    """

    __tablename__ = "job"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(
        Text, ForeignKey("dossier.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="uploaded")
    has_conflicts: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    current_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSONB
    lease_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_job_queue_ready", "status", "created_at"),)


class ManifestORM(Base):
    """ORM cho bảng ``manifest`` — kết quả phân loại tài liệu sau preprocessing."""

    __tablename__ = "manifest"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(
        Text, ForeignKey("dossier.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="pending"
    )  # pending | confirmed (legacy: DRAFT | CONFIRMED)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ManifestItemORM(Base):
    """ORM cho bảng ``manifest_item`` — 1 row trong manifest."""

    __tablename__ = "manifest_item"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    manifest_id: Mapped[str] = mapped_column(
        Text, ForeignKey("manifest.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)  # contract | annex | other
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(
        String,
        nullable=False,
        server_default="0.0",  # use String to avoid Float precision issues
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    included: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ManifestRelationORM(Base):
    """ORM cho bảng ``manifest_relation`` — quan hệ giữa documents trong manifest."""

    __tablename__ = "manifest_relation"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    manifest_id: Mapped[str] = mapped_column(
        Text, ForeignKey("manifest.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_document_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_document_id: Mapped[str] = mapped_column(Text, nullable=False)
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)  # annex_of | …
    confirmation: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="unconfirmed"
    )  # unconfirmed | confirmed | rejected
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_manifest_relation_pair",
            "manifest_id",
            "source_document_id",
            "target_document_id",
            "relation_type",
        ),
    )


__all__ = [
    "DocumentORM",
    "DossierORM",
    "JobORM",
    "ManifestItemORM",
    "ManifestORM",
    "ManifestRelationORM",
]
