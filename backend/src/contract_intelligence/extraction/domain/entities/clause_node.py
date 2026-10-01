"""ClauseNode — node trong cây Điều → Khoản → Điểm.

Tương ứng bảng ``clause_node`` (xem ``DOC-04c`` §6.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class ClauseLevel(StrEnum):
    """Cấp độ trong cây điều khoản."""

    DOCUMENT = "document"
    CHAPTER = "chapter"
    ARTICLE = "article"  # Điều
    CLAUSE = "clause"  # Khoản
    POINT = "point"  # Điểm


@dataclass(eq=False)
class ClauseNode(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("cln_"))
    document_id: str = ""
    run_id: str = ""
    parent_id: str | None = None
    node_type: ClauseLevel = ClauseLevel.ARTICLE
    label: str | None = None
    number: str | None = None
    title: str | None = None
    text: str = ""
    doc_char_start: int = 0
    doc_char_end: int = 0
    line_ids: list[str] = field(default_factory=list)
    page_start: int = 0
    page_end: int = 0
    confidence: float = 0.0
