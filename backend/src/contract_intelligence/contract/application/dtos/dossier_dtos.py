"""DTOs for Dossier endpoints — Phase 1 alignment with openapi.yaml.

Schemas match DOC-05-api-spec.yaml components:
    DossierSummary  (lines 1779-1789)   — for list responses
    Dossier         (lines 1761-1778)   — for detail responses
    DossierCreated  (ApiEnvelopeDossierCreated, line 2320) — for POST /dossiers
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.job import JobStatus


class DossierSummaryDTO(BaseModel):
    """Lightweight dossier projection for list endpoints (openapi.yaml: DossierSummary)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    batch_id: str | None = None
    has_conflicts: bool = False
    latest_job_status: JobStatus | None = None
    open_review_items: int = 0
    pending_conflicts: int = 0
    metadata: dict[str, Any] | None = None
    created_at: datetime

    @classmethod
    def from_domain(
        cls,
        dossier: Dossier,
        *,
        latest_job_status: JobStatus | None = None,
        open_review_items: int = 0,
        pending_conflicts: int = 0,
    ) -> DossierSummaryDTO:
        return cls(
            id=dossier.id,
            name=dossier.name,
            batch_id=dossier.batch_id,
            has_conflicts=dossier.has_conflicts,
            latest_job_status=latest_job_status,
            open_review_items=open_review_items,
            pending_conflicts=pending_conflicts,
            metadata=dossier.metadata,
            created_at=dossier.created_at,
        )


class DossierDetailDTO(BaseModel):
    """Full dossier detail (openapi.yaml: Dossier)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    batch_id: str | None = None
    has_conflicts: bool = False
    latest_job_id: str | None = None
    latest_job_status: JobStatus | None = None
    documents: list[DocumentSummaryDTO] = Field(default_factory=list)
    open_review_items: int = 0
    pending_conflicts: int = 0
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        dossier: Dossier,
        *,
        documents: list[Document] | None = None,
        latest_job_id: str | None = None,
        latest_job_status: JobStatus | None = None,
        open_review_items: int = 0,
        pending_conflicts: int = 0,
    ) -> DossierDetailDTO:
        return cls(
            id=dossier.id,
            name=dossier.name,
            batch_id=dossier.batch_id,
            has_conflicts=dossier.has_conflicts,
            latest_job_id=latest_job_id,
            latest_job_status=latest_job_status,
            documents=[DocumentSummaryDTO.from_domain(d) for d in (documents or [])],
            open_review_items=open_review_items,
            pending_conflicts=pending_conflicts,
            metadata=dossier.metadata,
            created_at=dossier.created_at,
            updated_at=dossier.updated_at,
        )


class DocumentSummaryDTO(BaseModel):
    """Document summary embedded in Dossier detail (subset of Document)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    dossier_id: str
    role: DocumentRole
    order_index: int
    filename: str
    sha256: str
    page_count: int = 0
    file_size_bytes: int = 0
    lang_detected: str | None = None

    @classmethod
    def from_domain(cls, doc: Document) -> DocumentSummaryDTO:
        return cls(
            id=doc.id,
            dossier_id=doc.dossier_id,
            role=doc.role,
            order_index=doc.order_index,
            filename=doc.filename,
            sha256=doc.sha256,
            page_count=doc.page_count,
            file_size_bytes=doc.file_size_bytes,
            lang_detected=doc.lang_detected,
        )


class DossierCreatedDTO(BaseModel):
    """Response data for POST /dossiers multipart upload.

    Maps to ApiEnvelopeDossierCreated.data in openapi.yaml (line 2320).
    """

    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    job_id: str | None = None


__all__ = [
    "DossierSummaryDTO",
    "DossierDetailDTO",
    "DocumentSummaryDTO",
    "DossierCreatedDTO",
]
