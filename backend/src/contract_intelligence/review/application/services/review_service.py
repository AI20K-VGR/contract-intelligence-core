"""Review BC — application service (HITL queue + optimistic concurrency)."""

from __future__ import annotations

import hashlib
import re
from typing import Any, NoReturn, Protocol

from contract_intelligence.review.application.dtos.review_dtos import (
    ClauseReviewDTO,
    ClauseReviewEntryDTO,
    ClauseStaleReviewDTO,
    ReviewActionResponseDTO,
    ReviewItemDTO,
    ReviewItemRevisionDTO,
)
from contract_intelligence.review.domain.entities.review_action import ReviewActionType
from contract_intelligence.review.domain.entities.review_item import (
    ReviewItemStatus,
    ReviewPriority,
    ReviewTargetType,
)
from contract_intelligence.shared.exceptions import (
    InvariantViolation,
    NotFoundError,
    ReviewVersionConflict,
    ValidationError,
)


class ReviewRepositoryPort(Protocol):
    """Port used by ReviewService — infrastructure implements this."""

    async def list_by_dossier(
        self,
        dossier_id: str,
        *,
        priority: ReviewPriority | None = None,
        status_filter: ReviewItemStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...

    async def get_item(self, item_id: str) -> dict[str, Any] | None: ...

    async def list_revisions(self, item_id: str) -> list[dict[str, Any]]: ...

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
    ) -> dict[str, Any]: ...

    async def get_clause_context(self, node_id: str) -> dict[str, Any] | None: ...

    async def get_line_anchor_context(
        self, *, document_id: str, page_no: int, line_no: int
    ) -> dict[str, Any] | None: ...

    async def find_item_for_target(
        self, *, target_type: str, target_id: str
    ) -> dict[str, Any] | None: ...

    async def get_or_create_item_for_target(
        self,
        *,
        dossier_id: str,
        run_id: str,
        target_type: str,
        target_id: str,
        reason: str,
        target_snapshot: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]: ...

    async def ensure_target_snapshot(
        self, item_id: str, target_snapshot: dict[str, Any]
    ) -> None: ...

    async def list_orphan_clause_items(self, dossier_id: str) -> list[dict[str, Any]]: ...

    async def list_revisions_with_reviewer(self, item_id: str) -> list[dict[str, Any]]: ...


CLAUSE_REVIEW_REASON = "Thẩm định trích dẫn thủ công"

_CLAUSE_KEY_FIELDS = ("document_id", "node_type", "number", "label", "ordinal")


def clause_snapshot(ctx: dict[str, Any]) -> dict[str, Any]:
    """Khoá nhận diện điều khoản qua các lần phân tích + nội dung lúc thẩm định.

    Số/nhãn không duy nhất trong một tài liệu (danh sách đánh số lồng nhau), nên
    ``ordinal`` = thứ tự của điều khoản trùng số/nhãn đó theo vị trí trong tài liệu.
    """
    body = str(ctx.get("text") or "")
    digest = ctx.get("text_sha256") if not body else None
    return {
        "document_id": ctx["document_id"],
        "node_type": str(ctx.get("node_type") or ""),
        "number": str(ctx.get("number") or ""),
        "label": str(ctx.get("label") or ""),
        "ordinal": int(ctx.get("ordinal") or 0),
        "text_sha256": digest or hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "text": body,
    }


_LINE_NODE_ID = re.compile(r"^[nh]-(\d+)-(\d+)$")


class ReviewService:
    def __init__(
        self,
        *,
        repo: ReviewRepositoryPort,
        tenant_id: str,
    ) -> None:
        self._repo = repo
        self._tenant_id = tenant_id

    async def list_review_items(
        self,
        dossier_id: str,
        *,
        priority: ReviewPriority | None = None,
        status_filter: ReviewItemStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ReviewItemDTO], int]:
        rows, total = await self._repo.list_by_dossier(
            dossier_id,
            priority=priority,
            status_filter=status_filter,
            limit=limit,
            offset=offset,
        )
        return [ReviewItemDTO.from_row(r) for r in rows], total

    async def get_review_item(self, item_id: str) -> ReviewItemDTO:
        item = await self._repo.get_item(item_id)
        if item is None:
            raise NotFoundError(entity_type="ReviewItem", entity_id=item_id)
        return ReviewItemDTO.from_row(item)

    async def list_revisions(self, item_id: str) -> list[ReviewItemRevisionDTO]:
        await self.get_review_item(item_id)
        rows = await self._repo.list_revisions(item_id)
        return [
            ReviewItemRevisionDTO.from_action_row(row, revision_number=idx)
            for idx, row in enumerate(rows, start=1)
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
    ) -> ReviewActionResponseDTO:
        if action_type == ReviewActionType.CORRECT and not corrected_value and not corrected_bbox:
            raise ValidationError(
                "action=correct requires corrected_value or corrected_bbox",
                field="corrected_value",
            )

        result = await self._repo.submit_action(
            item_id=item_id,
            action_type=action_type,
            base_version=base_version,
            reviewer_id=reviewer_id,
            corrected_value=corrected_value,
            corrected_bbox=corrected_bbox,
            comment=comment,
        )
        return ReviewActionResponseDTO(
            review_action_id=str(result.get("review_action_id") or result.get("action_id")),
            item_status=str(result.get("item_status") or "open"),
            new_version=int(result["new_version"]),
            effective_value=result.get("effective_value"),
            machine_value=result.get("machine_value"),
            job_status=result.get("job_status"),
            open_items_remaining=result.get("open_items_remaining"),
            idempotent_replay=bool(result.get("idempotent_replay", False)),
        )

    async def get_clause_context(
        self,
        node_id: str,
        *,
        document_id: str | None = None,
        node: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """``node_id`` là id clause_node, hoặc id nút cây frontend ``n|h-{trang}-{dòng}``.

        Nút frontend không có trong DB: neo vào dòng OCR mở nút, mô tả nút (loại,
        số, nhãn, thứ tự, nội dung hoặc hash nội dung) do client gửi kèm.
        """
        match = _LINE_NODE_ID.match(node_id)
        if match is None:
            ctx = await self._repo.get_clause_context(node_id)
        elif not document_id:
            raise ValidationError("Nút dựng từ dòng OCR cần document_id.", field="document_id")
        else:
            ctx = await self._repo.get_line_anchor_context(
                document_id=document_id,
                page_no=int(match.group(1)),
                line_no=int(match.group(2)),
            )
            if ctx is not None:
                ctx = {**ctx, **{k: v for k, v in (node or {}).items() if v is not None}}
        if ctx is None:
            raise NotFoundError(entity_type="ClauseNode", entity_id=node_id)
        return ctx

    async def get_clause_review(self, ctx: dict[str, Any]) -> ClauseReviewDTO:
        item = await self._repo.find_item_for_target(
            target_type=ReviewTargetType.CLAUSE_NODE.value,
            target_id=ctx["node_id"],
        )
        entries = await self._entries(item["id"]) if item is not None else []
        stale = None if entries else await self._stale_review(ctx)
        return ClauseReviewDTO(
            node_id=ctx["node_id"],
            document_id=ctx["document_id"],
            dossier_id=ctx["dossier_id"],
            review_item_id=item["id"] if item else None,
            run_id=(item or {}).get("run_id") or ctx.get("run_id"),
            version=int(item["version"]) if item else 0,
            status=str(item["status"]) if item and entries else "unreviewed",
            dossier_locked=bool(ctx.get("is_locked")),
            latest=entries[-1] if entries else None,
            history=entries,
            stale=stale,
        )

    async def _entries(self, item_id: str) -> list[ClauseReviewEntryDTO]:
        rows = await self._repo.list_revisions_with_reviewer(item_id)
        return [
            ClauseReviewEntryDTO.from_row(row, revision_number=idx)
            for idx, row in enumerate(rows, start=1)
        ]

    async def _stale_review(self, ctx: dict[str, Any]) -> ClauseStaleReviewDTO | None:
        """Không tự mang sang: chỉ trả thẩm định cũ để người thẩm định xem lại."""
        current = clause_snapshot(ctx)
        if not current["number"] and not current["label"]:
            return None
        for old in await self._repo.list_orphan_clause_items(ctx["dossier_id"]):
            snap = old.get("target_snapshot") or {}
            if any(snap.get(k) != current[k] for k in _CLAUSE_KEY_FIELDS):
                continue
            entries = await self._entries(old["id"])
            if not entries:
                continue
            return ClauseStaleReviewDTO(
                review_item_id=old["id"],
                run_id=old.get("run_id"),
                text_changed=snap.get("text_sha256") != current["text_sha256"],
                reviewed_text=snap.get("text"),
                latest=entries[-1],
                history=entries,
            )
        return None

    async def submit_clause_review(
        self,
        *,
        ctx: dict[str, Any],
        action_type: ReviewActionType,
        base_version: int,
        reviewer_id: str,
        comment: str | None = None,
        corrected_value: dict[str, Any] | None = None,
    ) -> ClauseReviewDTO:
        """Ghi một lượt thẩm định mới cho điều khoản; không ghi đè lượt trước."""
        if ctx.get("is_locked"):
            raise InvariantViolation(
                "Hồ sơ đã khóa, không thể thẩm định thêm.", dossier_id=ctx["dossier_id"]
            )
        comment = (comment or "").strip() or None
        if action_type == ReviewActionType.CORRECT:
            corrected_value = corrected_value or ({"assessment": comment} if comment else None)
            if not corrected_value:
                raise ValidationError("Sửa nhận định cần nội dung nhận định mới.", field="comment")
        else:
            corrected_value = None

        item = await self._repo.find_item_for_target(
            target_type=ReviewTargetType.CLAUSE_NODE.value,
            target_id=ctx["node_id"],
        )
        if item is None:
            if base_version != 0:
                await self._raise_clause_conflict(ctx, "", base_version, 0)
            if not ctx.get("run_id"):
                raise InvariantViolation(
                    "Hồ sơ chưa có lượt phân tích nào.", dossier_id=ctx["dossier_id"]
                )
            item, created = await self._repo.get_or_create_item_for_target(
                dossier_id=ctx["dossier_id"],
                run_id=ctx["run_id"],
                target_type=ReviewTargetType.CLAUSE_NODE.value,
                target_id=ctx["node_id"],
                reason=CLAUSE_REVIEW_REASON,
                target_snapshot=clause_snapshot(ctx),
            )
            if not created:
                await self._raise_clause_conflict(
                    ctx, item["id"], base_version, int(item["version"])
                )
            base_version = int(item["version"])
        elif not item.get("target_snapshot"):
            await self._repo.ensure_target_snapshot(item["id"], clause_snapshot(ctx))

        try:
            await self._repo.submit_action(
                item_id=item["id"],
                action_type=action_type,
                base_version=base_version,
                reviewer_id=reviewer_id,
                corrected_value=corrected_value,
                comment=comment,
            )
        except ReviewVersionConflict as exc:
            await self._raise_clause_conflict(
                ctx,
                item["id"],
                base_version,
                int(exc.details.get("current_version") or 0),
                cause=exc,
            )
        return await self.get_clause_review(ctx)

    async def _raise_clause_conflict(
        self,
        ctx: dict[str, Any],
        item_id: str,
        expected: int,
        current: int,
        *,
        cause: Exception | None = None,
    ) -> NoReturn:
        state = await self.get_clause_review(ctx)
        raise ReviewVersionConflict(
            review_item_id=item_id,
            expected_version=expected,
            current_version=state.version or current,
            current_state=state.model_dump(mode="json"),
        ) from cause


__all__ = ["CLAUSE_REVIEW_REASON", "ReviewRepositoryPort", "ReviewService", "clause_snapshot"]
