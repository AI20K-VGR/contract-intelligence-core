"""Manifest domain entity — pure dataclass, không phụ thuộc ORM.

Layer: domain. Application layer dùng dataclass này, không bao giờ thấy ORM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contract_intelligence.shared.base import BaseEntity


@dataclass(eq=False)
class ManifestItem(BaseEntity[str]):
    """Một dòng trong manifest — mapping document → role/sequence.

    Concrete ORM (``ManifestItemORM``) chỉ tồn tại trong infrastructure layer.
    """

    id: str = ""
    manifest_id: str = ""
    document_id: str = ""
    filename: str = ""
    doc_type: str = ""
    sha256: str = ""
    confidence: str = "0"
    order_index: int = 0

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
        }


@dataclass(eq=False)
class Manifest(BaseEntity[str]):
    """Manifest của một dossier — danh sách documents được confirm."""

    id: str = ""
    dossier_id: str = ""
    status: str = "DRAFT"
    items: list[ManifestItem] = field(default_factory=list)
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "dossier_id": self.dossier_id,
            "status": self.status,
            "items": [it.to_dict() for it in self.items],
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "confirmed_by": self.confirmed_by,
        }


__all__ = ["Manifest", "ManifestItem"]
