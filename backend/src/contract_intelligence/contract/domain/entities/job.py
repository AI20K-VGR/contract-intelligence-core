"""Job entity — 1 lần xử lý Dossier qua pipeline.

Tương ứng bảng ``job`` trong DB (xem ``DOC-04b`` §4 + ``DOC-04c`` §4.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class JobStatus(StrEnum):
    """State machine — xem ``backend/CONTEXT.md`` §4.1."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(eq=False)
class Job(BaseEntity[str]):
    """Một lần xử lý — sinh ra 0..n ``pipeline_run``."""

    id: str = field(default_factory=lambda: new_ulid("job_"))
    dossier_id: str = ""
    batch_id: str | None = None
    status: JobStatus = JobStatus.UPLOADED
    has_conflicts: bool = False
    current_run_id: str | None = None
    error_code: str | None = None
    # error_detail lưu JSONB — giữ ở domain dạng dict để không phụ thuộc JSON lib
    error_detail: dict[str, object] = field(default_factory=dict)
