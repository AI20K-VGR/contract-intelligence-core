"""Review BC repositories — optimistic locking (P0-05)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import exists, func, or_, select, text, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.domain.entities.job import JobStatus
from contract_intelligence.contract.infrastructure.persistence.dossier_status import (
    advance_dossier_status,
)
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.extraction.infrastructure.persistence.orm import (
    ClauseNodeORM,
    OcrLineORM,
)
from contract_intelligence.identity.infrastructure.persistence.orm import AppUserORM
from contract_intelligence.review.domain.entities.review_action import (
    ReviewActionType,
)
from contract_intelligence.review.domain.entities.review_item import (
    ReviewItemStatus,
    ReviewPriority,
)
from contract_intelligence.review.infrastructure.persistence.orm import (
    REVIEW_ACTION_BASE_VERSION_UNIQUE,
    ReviewActionORM,
    ReviewItemORM,
)
from contract_intelligence.shared.audit import add_audit_event
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.exceptions import (
    InvariantViolation,
    NotFoundError,
    ReviewVersionConflict,
)

_DOSSIER_COLUMNS = (
    "ds.tenant_id AS dossier_tenant_id, ds.metadata AS dossier_metadata, ds.is_locked, "
    # Luồng AI1 qua Kafka chỉ tạo job, không tạo pipeline_run.
    "COALESCE("
    "(SELECT r.id FROM pipeline_run r "
    " WHERE r.dossier_id = d.dossier_id AND r.tenant_id = :tenant_id "
    " ORDER BY r.created_at DESC LIMIT 1), "
    "(SELECT j.id FROM job j "
    " WHERE j.dossier_id = d.dossier_id AND j.tenant_id = :tenant_id "
    " ORDER BY j.created_at DESC LIMIT 1)) AS run_id"
)


class ReviewRepositoryImpl:
    """Review item + action repositories."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def list_by_dossier(
        self,
        dossier_id: str,
        *,
        priority: ReviewPriority | None = None,
        status_filter: ReviewItemStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(ReviewItemORM).where(
            ReviewItemORM.dossier_id == dossier_id,
            ReviewItemORM.tenant_id == self._tenant_id,
        )
        if priority:
            stmt = stmt.where(ReviewItemORM.priority == priority.value)
        if status_filter:
            stmt = stmt.where(ReviewItemORM.status == status_filter.value)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        stmt = (
            stmt.order_by(
                ReviewItemORM.priority.asc(),
                ReviewItemORM.created_at.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._item_to_dict(o) for o in result.scalars().all()], total

    async def get_item(self, item_id: str) -> dict[str, Any] | None:
        stmt = select(ReviewItemORM).where(
            ReviewItemORM.id == item_id, ReviewItemORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._item_to_dict(orm) if orm else None

    async def count_open(self, dossier_id: str) -> int:
        stmt = select(func.count()).where(
            ReviewItemORM.dossier_id == dossier_id,
            ReviewItemORM.tenant_id == self._tenant_id,
            ReviewItemORM.status.in_(
                (ReviewItemStatus.OPEN.value, ReviewItemStatus.AWAITING_EVIDENCE.value)
            ),
        )
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)

    async def list_revisions(self, item_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(ReviewActionORM)
            .where(
                ReviewActionORM.review_item_id == item_id,
                ReviewActionORM.tenant_id == self._tenant_id,
            )
            .order_by(ReviewActionORM.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": a.id,
                "review_item_id": a.review_item_id,
                "action": a.action,
                "base_version": a.base_version,
                "corrected_value": a.corrected_value,
                "corrected_bbox": a.corrected_bbox,
                "comment": a.comment,
                "reviewer_id": a.reviewer_id,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in result.scalars().all()
        ]

    async def submit_action(
        self,
        *,
        item_id: str,
        action_type: ReviewActionType,
        base_version: int,
        reviewer_id: str,
        corrected_value: dict[str, Any] | None = None,
        corrected_bbox: list[Any] | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Atomic submit với optimistic lock (P0-05).

        Locks the item row, then share-locks its dossier so approval/lock (which
        take the dossier row for update) cannot interleave with the action.

        Raises:
            ReviewVersionConflict: base_version mismatch (includes current_state).
            InvariantViolation: dossier locked, approved or deleted.
            NotFoundError: item missing.
        """
        stmt = (
            select(ReviewItemORM)
            .where(
                ReviewItemORM.id == item_id,
                ReviewItemORM.tenant_id == self._tenant_id,
            )
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            raise NotFoundError(entity_type="ReviewItem", entity_id=item_id)

        dossier = (
            await self._session.execute(
                select(DossierORM.is_locked, DossierORM.is_approved, DossierORM.deleted_at)
                .where(DossierORM.id == orm.dossier_id, DossierORM.tenant_id == self._tenant_id)
                # Exclusive, not FOR SHARE: two reviewers closing the last two
                # items must see each other's work, or neither would move the
                # dossier to ``reviewed``. Also keeps approval out (it takes
                # the same row lock before counting open items).
                .with_for_update()
            )
        ).one_or_none()
        if dossier is None or dossier.deleted_at is not None:
            raise NotFoundError(entity_type="Dossier", entity_id=orm.dossier_id)
        if dossier.is_locked or dossier.is_approved:
            raise InvariantViolation(
                "Hồ sơ đã khóa hoặc đã phê duyệt, không thể thẩm định thêm.",
                dossier_id=orm.dossier_id,
                review_item_id=item_id,
            )

        if orm.version != base_version:
            raise ReviewVersionConflict(
                review_item_id=item_id,
                expected_version=base_version,
                current_version=orm.version,
                current_state=self._item_to_dict(orm),
            )

        previous_status = orm.status
        dossier_id = orm.dossier_id
        action_orm = ReviewActionORM(
            id=new_ulid("ra_"),
            tenant_id=self._tenant_id,
            review_item_id=item_id,
            target_type=orm.target_type,
            target_id=orm.target_id,
            action=action_type.value,
            base_version=base_version,
            corrected_value=json.dumps(corrected_value) if corrected_value is not None else None,
            corrected_bbox=json.dumps(corrected_bbox) if corrected_bbox is not None else None,
            comment=comment,
            reviewer_id=reviewer_id,
        )
        self._session.add(action_orm)

        new_version = orm.version + 1
        orm.version = new_version
        if action_type in (
            ReviewActionType.CONFIRM,
            ReviewActionType.CORRECT,
            ReviewActionType.REJECT,
        ):
            orm.status = ReviewItemStatus.RESOLVED.value
        elif action_type == ReviewActionType.NEEDS_MORE_EVIDENCE:
            orm.status = ReviewItemStatus.AWAITING_EVIDENCE.value
        orm.updated_at = utcnow()
        add_audit_event(
            self._session,
            tenant_id=self._tenant_id,
            action="review.action_submitted",
            entity_type="review_item",
            entity_id=item_id,
            actor_id=reviewer_id,
            dossier_id=dossier_id,
            run_id=orm.run_id,
            from_state=previous_status,
            to_state=orm.status,
            detail={
                "review_action_id": action_orm.id,
                "action": action_type.value,
                "base_version": base_version,
                "new_version": new_version,
                "target_type": orm.target_type,
                "target_id": orm.target_id,
                "has_correction": corrected_value is not None or corrected_bbox is not None,
            },
        )

        try:
            await self._session.flush()
        except IntegrityError as exc:
            if not _is_base_version_race(exc):
                raise
            # Another action for the same base_version won the race; the ORM
            # instance is expired by the rollback, so read the winner back.
            await self._session.rollback()
            current = await self.get_item(item_id)
            raise ReviewVersionConflict(
                review_item_id=item_id,
                expected_version=base_version,
                current_version=int((current or {}).get("version") or base_version + 1),
                current_state=current,
            ) from exc

        open_remaining = await self.count_open(dossier_id)
        if open_remaining == 0:
            await advance_dossier_status(
                self._session,
                tenant_id=self._tenant_id,
                dossier_id=dossier_id,
                from_status=JobStatus.PENDING_REVIEW,
                to_status=JobStatus.REVIEWED,
                actor_id=reviewer_id,
                detail={"last_review_item_id": item_id, "review_action_id": action_orm.id},
            )
        return {
            "action_id": action_orm.id,
            "review_action_id": action_orm.id,
            "new_version": new_version,
            "current_version": new_version,
            "item_status": orm.status,
            "effective_value": corrected_value,
            "open_items_remaining": open_remaining,
        }

    async def get_clause_context(self, node_id: str) -> dict[str, Any] | None:
        return await self._context(
            "SELECT n.id AS node_id, n.document_id, d.dossier_id, "
            "n.node_type, n.number, n.label, n.text, "
            "(SELECT count(*) FROM clause_node s "
            " WHERE s.document_id = n.document_id AND s.node_type = n.node_type "
            " AND s.number = n.number AND s.label = n.label "
            " AND (s.doc_char_start, s.id) < (n.doc_char_start, n.id)) AS ordinal, "
            f"{_DOSSIER_COLUMNS} "
            "FROM clause_node n "
            "JOIN document d ON d.id = n.document_id "
            "JOIN dossier ds ON ds.id = d.dossier_id "
            "WHERE n.id = :node_id AND n.tenant_id = :tenant_id "
            "AND ds.deleted_at IS NULL",
            {"node_id": node_id},
        )

    async def get_line_anchor_context(
        self, *, document_id: str, page_no: int, line_no: int
    ) -> dict[str, Any] | None:
        """Neo cho nút cây dựng từ dòng OCR: dòng mở nút (OCR lại thì id dòng đổi)."""
        return await self._context(
            "SELECT l.id AS node_id, l.document_id, d.dossier_id, "
            f"{_DOSSIER_COLUMNS} "
            "FROM ocr_line l "
            "JOIN document d ON d.id = l.document_id "
            "JOIN dossier ds ON ds.id = d.dossier_id "
            "WHERE l.document_id = :document_id AND l.page_no = :page_no "
            "AND l.line_no = :line_no AND l.tenant_id = :tenant_id "
            "AND ds.deleted_at IS NULL "
            "ORDER BY l.id LIMIT 1",
            {"document_id": document_id, "page_no": page_no, "line_no": line_no},
        )

    async def _context(self, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
        row = (
            (await self._session.execute(text(sql), {**params, "tenant_id": self._tenant_id}))
            .mappings()
            .first()
        )
        if row is None:
            return None
        data = dict(row)
        meta = data.get("dossier_metadata")
        if isinstance(meta, str):
            try:
                data["dossier_metadata"] = json.loads(meta)
            except json.JSONDecodeError:
                data["dossier_metadata"] = None
        return data

    async def find_item_for_target(
        self, *, target_type: str, target_id: str
    ) -> dict[str, Any] | None:
        stmt = (
            select(ReviewItemORM)
            .where(
                ReviewItemORM.tenant_id == self._tenant_id,
                ReviewItemORM.target_type == target_type,
                ReviewItemORM.target_id == target_id,
            )
            .order_by(ReviewItemORM.created_at.desc())
            .limit(1)
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._item_to_dict(orm) if orm else None

    async def get_or_create_item_for_target(
        self,
        *,
        dossier_id: str,
        run_id: str,
        target_type: str,
        target_id: str,
        reason: str,
        target_snapshot: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Trả (item, created). Advisory lock để hai người mở cùng lúc không tạo hai item."""
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"review_item:{self._tenant_id}:{target_type}:{target_id}"},
        )
        existing = await self.find_item_for_target(target_type=target_type, target_id=target_id)
        if existing is not None:
            return existing, False
        orm = ReviewItemORM(
            id=new_ulid("ri_"),
            tenant_id=self._tenant_id,
            dossier_id=dossier_id,
            run_id=run_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            priority=ReviewPriority.P3.value,
            status=ReviewItemStatus.OPEN.value,
            version=1,
            target_snapshot=json.dumps(target_snapshot) if target_snapshot else None,
        )
        self._session.add(orm)
        await self._session.flush()
        return self._item_to_dict(orm), True

    async def ensure_target_snapshot(self, item_id: str, target_snapshot: dict[str, Any]) -> None:
        """Bổ sung ảnh chụp cho item tạo trước khi có cột này; không ghi đè ảnh đã có."""
        await self._session.execute(
            text(
                "UPDATE review_item SET target_snapshot = :snap "
                "WHERE id = :id AND tenant_id = :tenant_id AND target_snapshot IS NULL"
            ),
            {"snap": json.dumps(target_snapshot), "id": item_id, "tenant_id": self._tenant_id},
        )

    async def get_finding_context(self, finding_id: str) -> dict[str, Any] | None:
        return await self._context(
            "SELECT f.id AS finding_id, f.dossier_id, f.key_or_topic, f.rationale, "
            "ds.tenant_id AS dossier_tenant_id, ds.metadata AS dossier_metadata, ds.is_locked, "
            "COALESCE(f.run_id, "
            "(SELECT r.id FROM pipeline_run r "
            " WHERE r.dossier_id = f.dossier_id AND r.tenant_id = :tenant_id "
            " ORDER BY r.created_at DESC LIMIT 1)) AS run_id "
            "FROM finding f "
            "JOIN dossier ds ON ds.id = f.dossier_id "
            "WHERE f.id = :finding_id AND f.tenant_id = :tenant_id "
            "AND ds.deleted_at IS NULL",
            {"finding_id": finding_id},
        )

    async def list_prior_finding_reviews(
        self, *, dossier_id: str, finding_id: str, topic: str
    ) -> list[dict[str, Any]]:
        """Thẩm định của cùng chủ đề ở finding của lần chạy trước."""
        rows = (
            (
                await self._session.execute(
                    text(
                        "SELECT ri.id, f.run_id, f.rationale, f.key_or_topic "
                        "FROM finding f "
                        "JOIN review_item ri ON ri.target_id = f.id "
                        " AND ri.target_type = 'finding' AND ri.tenant_id = f.tenant_id "
                        "WHERE f.tenant_id = :tenant_id AND f.dossier_id = :dossier_id "
                        "AND f.key_or_topic = :topic AND f.id <> :finding_id "
                        "AND ri.version > 1 "
                        "ORDER BY f.created_at DESC"
                    ),
                    {
                        "tenant_id": self._tenant_id,
                        "dossier_id": dossier_id,
                        "finding_id": finding_id,
                        "topic": topic,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    async def list_orphan_clause_items(self, dossier_id: str) -> list[dict[str, Any]]:
        """Item thẩm định mà điều khoản / dòng OCR neo đã bị thay khi chạy lại phân tích."""
        stmt = (
            select(ReviewItemORM)
            .where(
                ReviewItemORM.tenant_id == self._tenant_id,
                ReviewItemORM.dossier_id == dossier_id,
                ReviewItemORM.target_type == "clause_node",
                ReviewItemORM.target_snapshot.is_not(None),
                ReviewItemORM.version > 1,
                ~exists().where(ClauseNodeORM.id == ReviewItemORM.target_id),
                ~exists().where(OcrLineORM.id == ReviewItemORM.target_id),
            )
            .order_by(ReviewItemORM.updated_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._item_to_dict(o) for o in result.scalars().all()]

    async def list_revisions_with_reviewer(self, item_id: str) -> list[dict[str, Any]]:
        reviewer = (
            select(AppUserORM.display_name, AppUserORM.email)
            .where(
                or_(
                    AppUserORM.id == ReviewActionORM.reviewer_id,
                    AppUserORM.keycloak_sub == ReviewActionORM.reviewer_id,
                )
            )
            .limit(1)
            .lateral()
        )
        stmt = (
            select(ReviewActionORM, reviewer.c.display_name, reviewer.c.email)
            .outerjoin(reviewer, true())
            .where(
                ReviewActionORM.review_item_id == item_id,
                ReviewActionORM.tenant_id == self._tenant_id,
            )
            .order_by(ReviewActionORM.created_at.asc(), ReviewActionORM.id.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "id": a.id,
                "action": a.action,
                "base_version": a.base_version,
                "corrected_value": a.corrected_value,
                "comment": a.comment,
                "reviewer_id": a.reviewer_id,
                "reviewer_name": name,
                "reviewer_email": email,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a, name, email in rows
        ]

    @staticmethod
    def _item_to_dict(orm: ReviewItemORM) -> dict[str, Any]:
        return {
            "id": orm.id,
            "dossier_id": orm.dossier_id,
            "run_id": orm.run_id,
            "target_type": orm.target_type,
            "target_id": orm.target_id,
            "reason": orm.reason,
            "priority": orm.priority,
            "status": orm.status,
            "version": orm.version,
            "source_trace_id": orm.source_trace_id,
            "source_observation_id": orm.source_observation_id,
            "target_snapshot": _load_json_dict(orm.target_snapshot),
            "created_at": orm.created_at.isoformat() if orm.created_at else None,
            "updated_at": orm.updated_at.isoformat() if orm.updated_at else None,
        }


def _is_base_version_race(exc: IntegrityError) -> bool:
    # Postgres names the index; SQLite lists the columns instead.
    message = str(exc.orig)
    return REVIEW_ACTION_BASE_VERSION_UNIQUE in message or (
        "review_action.review_item_id" in message and "review_action.base_version" in message
    )


def _load_json_dict(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


__all__ = ["ReviewRepositoryImpl"]
