"""Document entity — 1 file PDF thuộc Dossier.

Tương ứng bảng ``document`` trong DB (xem ``DOC-04b`` §3 + ``DOC-04c`` §3.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class DocumentRole(StrEnum):
    """Vai trò của document trong dossier."""

    CONTRACT = "contract"
    ANNEX = "annex"


@dataclass(eq=False)
class Document(BaseEntity[str]):
    """Một file PDF — contract hoặc annex."""

    id: str = field(default_factory=lambda: new_ulid("doc_"))
    dossier_id: str = ""
    role: DocumentRole = DocumentRole.CONTRACT
    order_index: int = 0
    filename: str = ""
    sha256: str = ""
    blob_uri: str = ""
    page_count: int = 0
    lang_detected: str = "vi"
    # Denormalized ngày — cập nhật bởi bước S7 của extraction pipeline
    signing_date: str | None = None  # ISO date "YYYY-MM-DD"
    effective_date: str | None = None
