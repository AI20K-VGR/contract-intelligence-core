"""Manifest domain entity — membership + relations for dossier confirmation.

Layer: domain. Application uses these dataclasses; ORM stays in infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contract_intelligence.shared.base import BaseEntity


@dataclass(eq=False)
class ManifestItem(BaseEntity[str]):
    """One membership row — document ↔ role / sequence / included flag."""

    id: str = ""
    manifest_id: str = ""
    document_id: str = ""
    filename: str = ""
    doc_type: str = ""  # contract | annex (legacy field name = role)
    sha256: str = ""
    confidence: str = "0"
    order_index: int = 0
    included: bool = True
    page_count: int = 0
    file_size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "manifest_id": self.manifest_id,
            "document_id": self.document_id,
            "filename": self.filename,
            "doc_type": self.doc_type,
            "sha256": self.sha256,
            "confidence": self.confidence,
            "order_index": self.order_index,
            "included": self.included,
            "page_count": self.page_count,
            "file_size_bytes": self.file_size_bytes,
        }


@dataclass(eq=False)
class ManifestRelation(BaseEntity[str]):
    """Directed relation between two documents in a manifest."""

    id: str = ""
    manifest_id: str = ""
    source_document_id: str = ""
    target_document_id: str = ""
    relation_type: str = "annex_of"
    confirmation: str = "unconfirmed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "manifest_id": self.manifest_id,
            "source_document_id": self.source_document_id,
            "target_document_id": self.target_document_id,
            "relation_type": self.relation_type,
            "confirmation": self.confirmation,
        }


@dataclass(eq=False)
class Manifest(BaseEntity[str]):
    """Manifest of a dossier — members + relations, versioned on confirm."""

    id: str = ""
    dossier_id: str = ""
    status: str = "pending"  # pending | confirmed (legacy: DRAFT | CONFIRMED)
    version: int = 1
    items: list[ManifestItem] = field(default_factory=list)
    relations: list[ManifestRelation] = field(default_factory=list)
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "dossier_id": self.dossier_id,
            "status": self.status,
            "version": self.version,
            "items": [it.to_dict() for it in self.items],
            "relations": [r.to_dict() for r in self.relations],
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "confirmed_by": self.confirmed_by,
        }


__all__ = ["Manifest", "ManifestItem", "ManifestRelation"]
