"""SQLAlchemy ORM models cho Extraction bounded context.

Tables (DOC-04b/DOC-04c):
    pipeline_run      — 1 lần trigger chạy pipeline qua 11 bước S0..S10
    pipeline_step     — trạng thái từng bước trong run
    page              — 1 trang của document (OCR metadata)
    ocr_line          — 1 dòng OCR với bbox CPS
    clause_node       — node trong cây điều khoản (article|clause|point)
    fact              — thực thể pháp lý trích xuất được
    citation          — trích dẫn có bbox, kèm quote_sha256
    doc_table         — bảng phát hiện được
    table_cell        — 1 cell trong doc_table
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.persistence.base import Base


class PipelineRunORM(Base):
    """1 lần trigger pipeline qua 11 bước (S0..S10)."""

    __tablename__ = "pipeline_run"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(
        Text, ForeignKey("job.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dossier_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="queued"
    )  # queued | running | succeeded | failed | cancelled
    pipeline_version: Mapped[str] = mapped_column(Text, nullable=False, server_default="v1.0.0")
    git_sha: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PipelineStepORM(Base):
    """Trạng thái 1 bước (S0..S10) trong run."""

    __tablename__ = "pipeline_step"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("pipeline_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    step: Mapped[str] = mapped_column(Text, nullable=False)  # S0..S10
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metrics: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSONB
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_pipeline_step_run_step", "run_id", "step"),)


class PageORM(Base):
    """1 trang của document — metadata OCR."""

    __tablename__ = "page"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(
        Text, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    width_pt: Mapped[float] = mapped_column(String, nullable=False)
    height_pt: Mapped[float] = mapped_column(String, nullable=False)
    rotation: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="native")
    render_blob_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_blob_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    features: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSONB
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("uq_page_doc_page", "document_id", "page_no", unique=True),)


class OcrLineORM(Base):
    """1 dòng OCR với bbox CPS."""

    __tablename__ = "ocr_line"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    bbox: Mapped[str] = mapped_column(Text, nullable=False)  # JSON [x0,y0,x1,y1]
    confidence: Mapped[float] = mapped_column(String, nullable=False, server_default="0.0")
    doc_char_start: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    doc_char_end: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (Index("ix_ocr_line_doc_page_line", "document_id", "page_no", "line_no"),)


class ClauseNodeORM(Base):
    """Node trong cây điều khoản."""

    __tablename__ = "clause_node"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(
        Text, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    node_type: Mapped[str] = mapped_column(Text, nullable=False)  # article | clause | point
    label: Mapped[str] = mapped_column(Text, nullable=False)
    number: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(String, nullable=False, server_default="0.0")
    doc_char_start: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    doc_char_end: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    regions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array


class FactORM(Base):
    """Fact (thực thể pháp lý) trích xuất được."""

    __tablename__ = "fact"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(
        Text, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    confidence: Mapped[float] = mapped_column(String, nullable=False, server_default="0.0")
    extractor: Mapped[str] = mapped_column(Text, nullable=False)
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CitationORM(Base):
    """Citation — bằng chứng trích dẫn cho fact."""

    __tablename__ = "citation"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    quote_sha256: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    doc_char_start: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    doc_char_end: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    segments: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array


class DocTableORM(Base):
    """Bảng phát hiện được trong document."""

    __tablename__ = "doc_table"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    rows_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cols_count: Mapped[int] = mapped_column(Integer, nullable=False)
    has_borders: Mapped[bool] = mapped_column(String, nullable=False, server_default="true")
    cells: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array


__all__ = [
    "CitationORM",
    "ClauseNodeORM",
    "DocTableORM",
    "FactORM",
    "OcrLineORM",
    "PageORM",
    "PipelineRunORM",
    "PipelineStepORM",
]
