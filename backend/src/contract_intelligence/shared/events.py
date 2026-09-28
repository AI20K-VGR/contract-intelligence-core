"""Domain event — publish/subscribe giữa các bounded context.

Domain event là cách bounded context giao tiếp KHÔNG phụ thuộc trực tiếp
vào nhau (xem ``backend/CONTEXT.md`` §3.3 — Dependency Rule).

Quy ước:
- Event class ở đây là **schema**, dùng Pydantic v2 để serialize an toàn.
- Publisher ở application layer ghi vào outbox/queue; subscriber ở
  bounded context khác listen qua message broker.
- V1 của dự án dùng **polling** qua task queue trong cùng DB — chưa cần broker.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from contract_intelligence.shared.base import utcnow


class DomainEvent(BaseModel):
    """Base class cho mọi domain event.

    Pydantic ở đây OK vì shared kernel được phép dùng Pydantic.
    Domain layer thuần túy (entities/enums) vẫn KHÔNG dùng Pydantic.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:26]}")
    occurred_at: datetime = Field(default_factory=utcnow)
    event_type: str = Field(default="", init=False)
    aggregate_id: str = Field(...)

    def model_post_init(self, _context: Any) -> None:  # noqa: D401
        """Subclass bắt buộc set ``event_type``."""
        if not self.event_type:
            raise ValueError("Subclass phải set class attribute `event_type`")


# -----------------------------------------------------------------------------
# Event catalog (Sprint 1 định nghĩa trước — bounded context tự subscribe)
# -----------------------------------------------------------------------------


class DossierCreated(DomainEvent):
    """Phát ra khi dossier mới được tạo (qua contract upload)."""

    event_type: str = "dossier.created"


class JobStatusChanged(DomainEvent):
    """Phát ra khi job chuyển trạng thái."""

    event_type: str = "job.status_changed"
    from_status: str
    to_status: str


class ReviewItemResolved(DomainEvent):
    """Phát ra khi reviewer resolve một review item."""

    event_type: str = "review.item_resolved"
    target_type: str  # 'fact' | 'finding' | 'annex_link' | …
