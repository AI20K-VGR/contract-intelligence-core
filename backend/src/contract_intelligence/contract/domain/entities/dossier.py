"""Dossier — aggregate root cho 1 hợp đồng + 0..n phụ lục.

Tương ứng bảng ``dossier`` trong DB (xem ``DOC-04b`` §3 + ``DOC-04c`` §3.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from contract_intelligence.contract.domain.entities.document import Document
from contract_intelligence.contract.domain.entities.job import Job, JobStatus
from contract_intelligence.shared.base import BaseEntity, new_ulid
from contract_intelligence.shared.exceptions import InvalidStateTransition


@dataclass(eq=False)
class Dossier(BaseEntity[str]):
    """Aggregate root — Dossier = 1 contract + 0..n annex.

    Bất biến về ID; mutable về collection ``documents``/``jobs``.
    Không lưu collection vào DB — chúng chỉ là navigation property
    load qua repository.
    """

    id: str = field(default_factory=lambda: new_ulid("dos_"))
    name: str = ""
    batch_id: str | None = None
    has_conflicts: bool = False
    metadata: dict[str, Any] | None = None
    checksum: str | None = None

    # Navigation (không persist)
    documents: list[Document] = field(default_factory=list, repr=False)
    jobs: list[Job] = field(default_factory=list, repr=False)

    # ----- Behavior -----------------------------------------------------------
    def latest_job(self) -> Job | None:
        """Trả về job mới nhất — dùng cho status display."""
        if not self.jobs:
            return None
        return max(self.jobs, key=lambda j: j.created_at)

    def ensure_can_transition_to(self, target: JobStatus) -> None:
        """Validate state machine ở domain — application service gọi trước khi UPDATE.

        Rule đầy đủ xem ``backend/CONTEXT.md`` §4.1.
        """
        current = self.latest_job()
        if current is None:
            if target is not JobStatus.UPLOADED:
                raise InvalidStateTransition(
                    from_state="<none>",
                    to_state=target.value,
                    entity="Dossier",
                )
            return
        if not _ALLOWED_TRANSITIONS[current.status].__contains__(target):
            raise InvalidStateTransition(
                from_state=current.status.value,
                to_state=target.value,
                entity="Dossier",
            )


# -----------------------------------------------------------------------------
# State machine
# -----------------------------------------------------------------------------
_ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.UPLOADED: frozenset({JobStatus.PROCESSING, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.PROCESSING: frozenset(
        {
            JobStatus.EXTRACTED,
            JobStatus.PENDING_REVIEW,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.EXTRACTED: frozenset({JobStatus.PENDING_REVIEW, JobStatus.FAILED}),
    JobStatus.PENDING_REVIEW: frozenset(
        {JobStatus.REVIEWED, JobStatus.FAILED, JobStatus.PROCESSING}
    ),
    JobStatus.REVIEWED: frozenset({JobStatus.APPROVED, JobStatus.FAILED}),
    JobStatus.APPROVED: frozenset(),  # trạng thái cuối
    JobStatus.FAILED: frozenset({JobStatus.PROCESSING}),  # retry
    JobStatus.CANCELLED: frozenset(),  # terminal after dossier delete
}
