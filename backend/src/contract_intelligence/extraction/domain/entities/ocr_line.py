"""OcrLine — 1 dòng OCR kèm bbox CPS.

Tương ứng bảng ``ocr_line`` (xem ``DOC-04c`` §5.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contract_intelligence.shared.base import BaseEntity, new_ulid


@dataclass(eq=False)
class OcrLine(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("ln_"))
    page_id: str = ""
    run_id: str = ""
    line_no: int = 0
    text: str = ""
    # bbox CPS: [x0, y0, x1, y1], 0..1
    bbox: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    confidence: float = 0.0
    doc_char_start: int = 0
    doc_char_end: int = 0
    words: list[dict[str, object]] = field(default_factory=list)
    source: dict[str, object] = field(default_factory=dict)
    flags: dict[str, object] = field(default_factory=dict)
