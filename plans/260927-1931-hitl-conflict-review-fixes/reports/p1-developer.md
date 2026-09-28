# Phase 1 — List Latest — Developer Report

## Tóm tắt
Thêm `review.latest` vào response `GET /conflicts` (và `GET /findings`), sửa
`_latest_actions` sang lateral-join để `action_count` đếm đúng (không nhân dòng
do outerjoin trực tiếp AppUserORM). TDD đầy đủ RED → GREEN, không có deviation
so với phase contract.

## RED — `uv run pytest tests/unit/test_conflict_router.py -q` (trước khi implement)
```
.....FFF                                                                 [100%]
FAILED tests/unit/test_conflict_router.py::TestFindingReviewLatest::test_from_row_passes_latest_through
FAILED tests/unit/test_conflict_router.py::TestFindingReviewLatest::test_from_row_latest_none_when_review_has_no_actions
FAILED tests/unit/test_conflict_router.py::TestFindingReviewLatest::test_endpoint_returns_latest_keys
3 failed, 5 passed, 4 warnings in 3.44s
```
Nguyên nhân fail đúng như dự kiến trong phase file:
- `test_from_row_passes_latest_through`: `AttributeError: 'FindingReviewDTO' object has no
  attribute 'latest'` — model chưa có field `latest`.
- `test_from_row_latest_none_when_review_has_no_actions`: cùng nguyên nhân (thiếu field).
- `test_endpoint_returns_latest_keys`: `KeyError: 'latest'` — JSON response chưa có key
  `latest` trong `review`.

## GREEN — `uv run pytest tests/unit/test_conflict_router.py -q` (sau khi implement)
```
........                                                                 [100%]
8 passed, 3 warnings in 1.75s
```
Chạy thêm regression trên module liên quan để chắc không vỡ contract layer trên:
```
uv run pytest tests/unit/test_conflict_router.py tests/unit/application/test_conflict_service.py -q
11 passed, 3 warnings in 1.77s
```
(3 warning là `PytestWarning` về `@pytest.mark.asyncio` gắn qua `pytestmark` module-level
cho 2 test đồng bộ mới — pattern đã tồn tại từ trước ở các file test khác trong repo, không
phải regression do phase này gây ra, không ảnh hưởng pass/fail.)

## Files Modified
- `backend/src/contract_intelligence/conflict/application/dtos/finding_dtos.py`
  - Thêm `FindingReviewLatestDTO(BaseModel)` với `ConfigDict(extra="forbid")`, đúng 7
    field: `action: str`, `comment: str | None = None`, `reviewer_id: str | None = None`,
    `reviewer_name: str | None = None`, `reviewer_email: str | None = None`,
    `reviewed_at: str | None = None`, `action_count: int = 0` (dòng 24–33).
  - Gắn `latest: FindingReviewLatestDTO | None = None` vào `FindingReviewDTO` (dòng 42).
  - `from_row` build `latest` từ `review_raw.get("latest")` — nếu là `dict` thì
    `FindingReviewLatestDTO(**latest_raw)`, nếu không → `None` (dòng 92–99).
  - Cập nhật `__all__` thêm `"FindingReviewLatestDTO"` (dòng 121).
- `backend/src/contract_intelligence/conflict/infrastructure/persistence/repository_impl.py`
  - Import thêm `true` từ `sqlalchemy` (dòng 8).
  - `_latest_actions`: thay `.outerjoin(AppUserORM, or_(...))` bằng subquery
    `reviewer = select(AppUserORM.display_name, AppUserORM.email).where(or_(...)).limit(1).lateral()`
    rồi `.outerjoin(reviewer, true())`, đọc `reviewer.c.display_name` / `reviewer.c.email`
    thay cho `AppUserORM.display_name` / `AppUserORM.email` — sao chép đúng pattern ở
    `review/infrastructure/persistence/repository_impl.py:388-401`. Giữ nguyên
    `func.count(ReviewActionORM.id).over(partition_by=ReviewActionORM.review_item_id)`.
- `backend/tests/unit/test_conflict_router.py`
  - Thêm class `TestFindingReviewLatest` với 3 test đúng "Tests Before" trong phase file:
    `test_from_row_passes_latest_through`, `test_from_row_latest_none_when_review_has_no_actions`,
    `test_endpoint_returns_latest_keys` (endpoint `GET /api/v1/dossiers/dos_1/conflicts`
    assert đủ 7 key JSON `latest`).

## Deviation so với phase contract
Không có deviation về requirement/field/pattern. Khác biệt nhỏ ngoài scope-nội-dung:
đặt 3 test mới trong 1 class `TestFindingReviewLatest` riêng (thay vì rải trong các class
có sẵn) để nhóm rõ ràng theo mục tiêu khóa hành vi — không đổi assertion hay ý nghĩa test
mà phase yêu cầu.

## Success Criteria — đối chiếu
- [x] `dto.review.latest` giữ đủ 7 key; `None` khi review không có action.
- [x] `GET /conflicts` JSON chứa `review.latest`.
- [x] `action_count` distinct trên SQL thật: `[ASSUMED]` — pytest unit (mock service, không
      chạm DB thật) không chứng minh window-function trên SQL thật; đúng như phase đã ghi
      nhận (Success mục 3, Risks mục cuối). Gate của phase chỉ khóa DTO + pattern lateral-join
      đúng với code đã kiểm chứng ở `review` BC.
- [x] `uv run pytest tests/unit/test_conflict_router.py` xanh 100% (8 passed).

## Regression Gate
```
uv run pytest tests/unit/test_conflict_router.py
```
→ Xanh 100%. Chưa commit (theo yêu cầu — không commit).
