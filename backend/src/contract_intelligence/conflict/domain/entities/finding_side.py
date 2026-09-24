"""FindingSide — 1 phía (a hoặc b) của Finding. BR-14: cả 2 phía đều có citation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from contract_intelligence.shared.base import BaseEntity


class FindingSideEnum(StrEnum):
    A = "a"
    B = "b"


@dataclass(eq=False)
class FindingSide(BaseEntity[str]):
    id: str = ""  # composite (finding_id, side) — dùng làm PK trong DB
    finding_id: str = ""
    side: FindingSideEnum = FindingSideEnum.A
    document_id: str = ""
    fact_id: str | None = None
    clause_node_id: str | None = None
    citation_id: str = ""
    value_snapshot: dict[str, object] | None = None
