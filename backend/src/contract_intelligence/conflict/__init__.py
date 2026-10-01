"""Bounded context: conflict — phát hiện xung đột giữa hợp đồng ↔ phụ lục.

Aggregate roots:

- ``Finding`` — 1 phát hiện (so sánh hoặc khớp)
- ``FindingSide`` — 2 phía (a, b) của finding
- ``AnnexLink`` — liên kết phụ lục ↔ hợp đồng chính

Context này **lưu** kết quả xung đột từ rule-based hoặc AI Service.
"""

from contract_intelligence.conflict.domain.entities.annex_link import AnnexLink
from contract_intelligence.conflict.domain.entities.finding import Finding
from contract_intelligence.conflict.domain.entities.finding_side import FindingSide, FindingSideEnum

__all__ = ["AnnexLink", "Finding", "FindingSide", "FindingSideEnum"]
