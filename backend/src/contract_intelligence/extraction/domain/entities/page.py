"""Page entity — 1 trang vật lý của document.

Tương ứng bảng ``page`` (xem ``DOC-04c`` §5.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class PageKind(str, Enum):
    """Phân loại xử lý trang."""

    NATIVE = "native"  # có text layer — đọc thẳng bằng PyMuPDF
    SCANNED = "scanned"  # ảnh — cần OCR hybrid
    HYBRID = "hybrid"  # một phần text + một phần scan


@dataclass(eq=False)
class Page(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("pg_"))
    document_id: str = ""
    page_no: int = 0
    kind: PageKind = PageKind.NATIVE
    width_pt: float = 0.0
    height_pt: float = 0.0
    rotation: int = 0
    # features & transform lưu JSONB trong DB — domain giữ dict
    features: dict[str, object] = field(default_factory=dict)
    transform: dict[str, object] = field(default_factory=dict)
    render_uri: str = ""
    preview_uri: str = ""
