"""Citation — quote + bbox. Cốt lõi BR-07/BR-08.

Tương ứng bảng ``citation`` (xem ``DOC-04c`` §7.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contract_intelligence.shared.base import BaseEntity, new_ulid


@dataclass(eq=False)
class Citation(BaseEntity[str]):
    """Trích dẫn từ văn bản gốc — bao gồm quote + bbox segments."""

    id: str = field(default_factory=lambda: new_ulid("cit_"))
    document_id: str = ""
    run_id: str = ""
    quote: str = ""
    quote_sha256: str = ""
    # segments: [{page_no, line_id, char_start, char_end, bbox}]
    segments: list[dict[str, object]] = field(default_factory=list)
    doc_char_start: int = 0
    doc_char_end: int = 0
