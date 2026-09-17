"""AnnexLink — liên kết phụ lục ↔ hợp đồng chính.

Tương ứng bảng ``annex_link`` (xem ``DOC-04c`` §8.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class AnnexLinkStatus(str, Enum):
    LINKED = "linked"
    LINKED_NEEDS_REVIEW = "linked_needs_review"
    UNLINKED = "unlinked"


@dataclass(eq=False)
class AnnexLink(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("alnk_"))
    annex_document_id: str = ""
    contract_document_id: str = ""
    run_id: str = ""
    score: float = 0.0
    status: AnnexLinkStatus = AnnexLinkStatus.UNLINKED
    annex_sequence: int = 1
    effective_date: str | None = None
    citation_id: str | None = None
