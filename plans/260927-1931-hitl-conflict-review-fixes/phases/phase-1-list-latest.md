---
phase: 1
title: "List Latest"
status: pending
plan: 260927-1931-hitl-conflict-review-fixes
created: 2026-09-27
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 1 — List Latest

## Overview
Cho `GET /conflicts` trả `review.latest` (lần thẩm định gần nhất) và sửa double-count
`action_count`. Phụ thuộc: không. Mở khóa dữ liệu thật cho P2/P3.

## Files
- **Modify** `backend/src/contract_intelligence/conflict/application/dtos/finding_dtos.py`
  — thêm model lồng `latest` + cho `from_row` chuyển `latest` qua.
- **Modify** `backend/src/contract_intelligence/conflict/infrastructure/persistence/repository_impl.py`
  — đổi `_latest_actions` sang lateral-join; thêm import `true`.
- **Modify** `backend/tests/unit/test_conflict_router.py` — thêm test khóa `latest`.

## Requirements
- Thêm model mới `FindingReviewLatestDTO(BaseModel)` với `model_config =
  ConfigDict(extra="forbid")`, đúng 7 field khớp dict repo (`repository_impl.py:233-241`):
  `action: str`, `comment: str | None = None`, `reviewer_id: str | None = None`,
  `reviewer_name: str | None = None`, `reviewer_email: str | None = None`,
  `reviewed_at: str | None = None`, `action_count: int = 0`.
- KHÔNG tái dùng `ClauseReviewEntryDTO` (field required không khớp — `review_dtos.py:166-181`).
- Gắn `latest: FindingReviewLatestDTO | None = None` vào `FindingReviewDTO`
  (`finding_dtos.py:24-28`).
- `from_row` (`finding_dtos.py:80-84`) build `latest` từ `review_raw.get("latest")` khi
  là dict, nếu không → `None` (review item chưa có action → `_latest_actions` không set key,
  `latest` = `None`; xem research §Câu hỏi mở 1). Cập nhật `__all__` (`finding_dtos.py:105`).
- Giữ NGUYÊN 7 JSON key frontend đang đọc (`structure.ts:544-554`): `action`, `comment`,
  `reviewer_id`, `reviewer_name`, `reviewer_email`, `reviewed_at`, `action_count`.
- `_latest_actions` (`repository_impl.py:206-231`): thay `.outerjoin(AppUserORM, or_(...))`
  bằng subquery `reviewer = select(AppUserORM.display_name, AppUserORM.email).where(or_(
  AppUserORM.id == ReviewActionORM.reviewer_id, AppUserORM.keycloak_sub ==
  ReviewActionORM.reviewer_id)).limit(1).lateral()` rồi `.outerjoin(reviewer, true())`,
  đọc `reviewer.c.display_name/email` — sao chép `review/.../repository_impl.py:388-401`.
  Giữ `func.count(ReviewActionORM.id).over(partition_by=...)` (nay đếm đúng vì join không
  nhân dòng). Thêm `true` vào import sqlalchemy (`repository_impl.py:8`).

## TDD

### Tests Before (RED) — khóa gì
Trong `backend/tests/unit/test_conflict_router.py` (helper `_finding()` hiện KHÔNG có key
`"review"` — `:33-62`, nên test cũ an toàn):
- Thêm test dựng `FindingDTO.from_row(base)` với `base["review"] = {"item_id": "ri_1",
  "status": "resolved", "current_version": 2, "latest": {"action": "confirm", "comment":
  None, "reviewer_id": "u1", "reviewer_name": "Admin", "reviewer_email": "a@ci.local",
  "reviewed_at": "2026-09-27T04:15:35Z", "action_count": 1}}`. Assert:
  `dto.review.latest.action == "confirm"` và `dto.review.latest.action_count == 1`.
  **Khóa**: `latest` được from_row chuyển qua, không bị rớt.
- Thêm test endpoint: mock `list_conflicts` trả finding có `review.latest`, `GET
  /api/v1/dossiers/dos_1/conflicts`, assert `body["data"][0]["review"]["latest"]` có đủ 7
  key trên. **Khóa**: JSON hợp đồng giữ nguyên key frontend đọc.
- (Regression) `from_row` với `review` không có `latest` → `dto.review.latest is None`.
  **Khóa**: optional an toàn cho review item chưa có action.
RED vì `FindingReviewDTO` hiện chưa có field `latest` (`extra="forbid"` sẽ raise / thiếu attr).

### Implement → GREEN
Thêm model + gắn field + sửa `from_row` + đổi `_latest_actions` sang lateral-join như
Requirements. Chạy test tới xanh.

### Tests After
- Test mới xanh.
- Test cũ trong file không đổi hành vi (`TestListConflicts.test_returns_conflict_subset:117-125`
  chỉ assert `id`/`total`).

### Regression Gate (lệnh thật)
Từ `backend/`:
```
uv run pytest tests/unit/test_conflict_router.py
```
Xanh 100% → commit phase.

## Success
- [ ] `dto.review.latest` giữ đủ 7 key; `None` khi review không có action.
- [ ] `GET /conflicts` JSON chứa `review.latest`.
- [ ] `action_count` distinct trên SQL thật là `[ASSUMED]`: pytest mock không chứng minh
      window-count. Gate của phase chỉ khóa DTO và việc query dùng lateral `.limit(1)`.
- [ ] `uv run pytest tests/unit/test_conflict_router.py` xanh.

## Risks
- **Quên import `true`** → NameError. Mitigation: sửa import `from sqlalchemy import
  and_, func, or_, select, true` (`repository_impl.py:8`).
- **`extra="forbid"` trên model lồng** chặn key thừa nếu repo thêm field. L: thấp
  (dict repo cố định 7 key). Mitigation: model khớp đúng 7 key đã liệt kê.
- **Double-count không có test cũ bắt** (research §1: `test_conflict_service.py:40` mock
  ở tầng service, không chạm SQL). Test window-function thật cần DB → ngoài scope unit;
  gate hiện dựa trên đúng-pattern đã kiểm chứng ở review BC. Tag `[ASSUMED]` cho hành vi
  SQL runtime cho tới khi có integration test.
