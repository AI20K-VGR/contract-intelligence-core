"""DTOs for Document endpoints — Phase 1 alignment with openapi.yaml.

Schemas match DOC-05-api-spec.yaml components:
    DocumentListItem  (lines 2493-2512) — for list/detail responses
    DocumentDetail    (lines 2499-2512) — extends DocumentListItem
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from contract_intelligence.contract.domain.entities.document import Document


class DocumentListItemDTO(BaseModel):
    """Document list item (openapi.yaml: DocumentListItem).

    Required: id, dossier_id, role, filename, file_size_bytes, page_count.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    dossier_id: str
    role: str  # CONTRACT | ANNEX (spec uses uppercase)
    filename: str
    file_size_bytes: int
    page_count: int
    signing_date: str | None = None
    document_number: str | None = None
    sha256: str

    @classmethod
    def from_domain(cls, doc: Document) -> DocumentListItemDTO:
        return cls(
            id=doc.id,
            dossier_id=doc.dossier_id,
            role=doc.role.value.upper(),
            filename=doc.filename,
            file_size_bytes=doc.file_size_bytes,
            page_count=doc.page_count,
            signing_date=doc.signing_date,
            document_number=None,  # not stored on entity yet
            sha256=doc.sha256,
        )


class DocumentDetailDTO(DocumentListItemDTO):
    """Document detail (openapi.yaml: DocumentDetail)."""

    model_config = ConfigDict(extra="forbid")

    storage_path: str
    ocr_status: str = "pending"
    created_at: datetime

    @classmethod
    def from_domain(cls, doc: Document) -> DocumentDetailDTO:
        base = DocumentListItemDTO.from_domain(doc)
        return cls(
            **base.model_dump(),
            storage_path=doc.blob_uri,
            ocr_status="pending",
            created_at=doc.created_at,
        )


__all__ = [
    "DocumentListItemDTO",
    "DocumentDetailDTO",
]
