"""Dossier Q&A policy: rate limit + tenant quota, second-pass ACL, QueryTrace.

Every FE query path (``/search``, ``/query``, ``/ask``) runs the same sequence:

1. ACL (caller) → :func:`enforce_query_limits` (per-actor rate, per-tenant quota)
2. forward to AI2
3. :func:`enforce_result_acl` re-checks access and strips citations/hits whose
   document is outside the dossier
4. :func:`save_query_trace` persists actor/version/citations
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import DateTime, Integer, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.config.settings import get_settings
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.persistence.base import Base

QueryEndpoint = Literal["search", "query", "ask"]


class QueryTraceORM(Base):
    __tablename__ = "query_trace"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_version: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_contract_version: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    acl_decision: Mapped[str] = mapped_column(Text, nullable=False)
    dropped_citations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class QueryLimitExceeded(Exception):
    def __init__(self, *, code: str, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after_seconds = retry_after_seconds


class SlidingWindowLimiter:
    """Per-key sliding window, process-local."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str, *, limit: int, window_seconds: float) -> float | None:
        """Record one hit; return seconds to wait when ``limit`` is already used."""
        now = time.monotonic()
        with self._lock:
            window = self._hits.setdefault(key, deque())
            while window and now - window[0] >= window_seconds:
                window.popleft()
            if len(window) >= limit:
                return max(0.0, window_seconds - (now - window[0]))
            window.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_limiter = SlidingWindowLimiter()


def get_query_limiter() -> SlidingWindowLimiter:
    return _limiter


async def enforce_query_limits(
    session: AsyncSession | None,
    *,
    tenant_id: str,
    actor_id: str,
) -> None:
    """Raise :class:`QueryLimitExceeded` when the actor rate or tenant quota is spent.

    ``session`` is None only when no database is bound (offline unit tests);
    the rate limit still applies, the durable quota cannot be counted.
    """
    settings = get_settings()
    per_minute = settings.query_rate_limit_per_minute
    if per_minute > 0:
        wait = _limiter.acquire(f"{tenant_id}:{actor_id}", limit=per_minute, window_seconds=60.0)
        if wait is not None:
            raise QueryLimitExceeded(
                code="RATE_LIMITED",
                message=f"Quá {per_minute} câu hỏi/phút. Thử lại sau.",
                retry_after_seconds=max(1, int(wait) + 1),
            )

    daily = settings.query_daily_quota_per_tenant
    if daily > 0 and session is not None:
        since = utcnow() - timedelta(days=1)
        used = await session.scalar(
            select(func.count())
            .select_from(QueryTraceORM)
            .where(QueryTraceORM.tenant_id == tenant_id, QueryTraceORM.created_at >= since)
        )
        if int(used or 0) >= daily:
            raise QueryLimitExceeded(
                code="QUOTA_EXCEEDED",
                message=f"Tenant đã dùng hết {daily} câu hỏi trong 24 giờ.",
                retry_after_seconds=3600,
            )


def server_query_policy_flags() -> dict[str, Any]:
    """AI2 query policy is server configuration; client input never reaches it."""
    settings = get_settings()
    return {
        "egress_allowed": settings.ai2_query_egress_allowed,
        "use_vector": settings.ai2_query_use_vector,
    }


def _document_ref(item: dict[str, Any]) -> str | None:
    raw_nested = item.get("citation")
    nested: dict[str, Any] = raw_nested if isinstance(raw_nested, dict) else {}
    for value in (
        item.get("source_file_id"),
        item.get("document_id"),
        nested.get("source_file_id"),
        nested.get("document_id"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


@dataclass(frozen=True)
class AclSecondPass:
    decision: Literal["passed", "filtered", "denied"]
    dropped: int


def enforce_result_acl(
    payload: dict[str, Any],
    *,
    can_read_citations: bool,
    allowed_document_ids: set[str],
) -> tuple[dict[str, Any], AclSecondPass]:
    """Second ACL pass over the AI2 answer before it reaches the FE (fail-closed).

    - access revoked (or no citation_read grant) → no answer, no evidence, BLOCKED
    - a citation/hit is kept only when it names a document of this dossier; one
      without a document reference cannot be verified and is dropped too
    - when anything is dropped the answer, retrieval layer and reasoning trace
      are withheld, because they may quote the dropped evidence
    """
    result = dict(payload)
    evidence_keys = [key for key in ("citations", "hits") if isinstance(result.get(key), list)]
    total = sum(len(result[key]) for key in evidence_keys)

    if not can_read_citations:
        for key in evidence_keys:
            result[key] = []
        _withhold(result, code="BACKEND_ACL_DENIED", message="Quyền xem bằng chứng đã bị thu hồi.")
        return result, AclSecondPass(decision="denied", dropped=total)

    dropped = 0
    for key in evidence_keys:
        kept: list[Any] = []
        for item in result[key]:
            ref = _document_ref(item) if isinstance(item, dict) else None
            if ref is None or ref not in allowed_document_ids:
                dropped += 1
                continue
            kept.append(item)
        result[key] = kept

    if dropped:
        _withhold(
            result,
            code="BACKEND_ACL_FILTERED",
            message=f"Đã loại {dropped} trích dẫn ngoài phạm vi hồ sơ.",
        )
        return result, AclSecondPass(decision="filtered", dropped=dropped)
    return result, AclSecondPass(decision="passed", dropped=0)


def _withhold(result: dict[str, Any], *, code: str, message: str) -> None:
    result["answer"] = None
    result["text"] = None
    result["state"] = "BLOCKED"
    result["retrieval_layer"] = {}
    result["reasoning_trace"] = [{"code": code, "message": message}]


async def save_query_trace(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    actor_id: str,
    endpoint: QueryEndpoint,
    query: str,
    snapshot_version: str,
    snapshot_digest: str | None,
    query_contract_version: str,
    state: str | None,
    citations: list[Any],
    acl: AclSecondPass | None,
    error_code: str | None = None,
    latency_ms: int | None = None,
) -> QueryTraceORM:
    row = QueryTraceORM(
        id=new_ulid("qtr_"),
        tenant_id=tenant_id,
        dossier_id=dossier_id,
        actor_id=actor_id,
        endpoint=endpoint,
        query=query,
        snapshot_version=snapshot_version,
        snapshot_digest=snapshot_digest or None,
        query_contract_version=query_contract_version,
        state=state,
        citations=json.dumps(citations, ensure_ascii=False, default=str),
        acl_decision=acl.decision if acl else "not_evaluated",
        dropped_citations=acl.dropped if acl else 0,
        error_code=error_code,
        latency_ms=latency_ms,
        created_at=utcnow(),
    )
    session.add(row)
    await session.flush()
    return row


__all__ = [
    "AclSecondPass",
    "QueryLimitExceeded",
    "QueryTraceORM",
    "SlidingWindowLimiter",
    "enforce_query_limits",
    "enforce_result_acl",
    "get_query_limiter",
    "save_query_trace",
    "server_query_policy_flags",
]
