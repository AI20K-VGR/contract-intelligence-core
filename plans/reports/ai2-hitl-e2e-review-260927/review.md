# Review HITL đối soát xung đột — 2026-09-27

Verdict: **BLOCKED**

`scope: large · 6524 files · signals: api_contract, auth, ci_infra, config, dependency_manifest, secret → suggested effort: high`

Effort đã chạy: `high` (khớp gợi ý). Preflight đếm 6524 path vì harness và `.sdlc-tools` chưa được track. Review chỉ xét bề mặt sản phẩm HITL: cây, trang đối soát, API review, auth. Orchestration: `inline-Task fallback` (ultracode tắt, người dùng chọn 5 lens inline). Bốn lens `code-reviewer`: `anchor`, `conflict-ui`, `review-api`, `auth`. Probe E2E do phiên này chạy. `in-place: false`.

Dismissal store: fingerprint `564f372b3b8a776d` — 0 bản ghi cũ.

## Critical — xác nhận

`GET /dossiers/{id}/conflicts` tính `review.latest` trong repository rồi vứt ở DTO.

- Repo ghi `latest` vào dict: `backend/src/contract_intelligence/conflict/infrastructure/persistence/repository_impl.py:254-258`
- Service serialize bằng `FindingDTO.from_row`: `backend/src/contract_intelligence/conflict/application/services/conflict_service.py:56`
- DTO chỉ giữ `item_id`, `status`, `current_version` và `extra="forbid"`: `backend/src/contract_intelligence/conflict/application/dtos/finding_dtos.py:24-29` và `:79-84`

Chạy `FindingDTO.from_row` với `review.latest.action = confirm`: `review_keys` là `current_version`, `item_id`, `status`; `has_latest False`.

Frontend đọc đúng khóa đó và nhận `null`: `frontend/src/api/structure.ts:536`. Hệ quả trên UI: badge cây, banner và số “chưa thẩm định” luôn coi xung đột là `open`, kể cả sau khi đã lưu. Trang chi tiết `GET /findings/{id}/review` dùng DTO khác (`review_dtos.py:269` có `latest`), nên ba nút trên thẻ đối soát vẫn thấy lần lưu. Hai đường lệch nhau.

Không có test nào cho `review.latest` trên list conflicts.

## Important — xác nhận

Trang đối soát dựng cây theo `detail.structureMode` (`ClauseConflictPage.tsx:558-565`). Thẩm định trích dẫn được lưu trên cây `'numbered'` (`DossierStructurePage.tsx:202-203`). Với hồ sơ `freeform` hoặc `tables`, `linkedClauses` rỗng hoặc lệch ordinal, dòng thời gian trích dẫn trên thẻ xung đột không khớp lần thẩm định ở search. Hồ sơ đang xem nếu là `numbered` thì chưa trúng lỗi này.

## Đã kiểm và không phải lỗi

- Cùng một file, hai trang: cả hai nút lá được badge, cha đếm finding một lần (`conflictAnchors.ts`, test `same-file anchors`).
- Hồ sơ thật hiện `ConflictFindingReview`; demo giữ nút local; deep-link `?dossier=&finding=` được đọc; một nút trích dẫn vẫn hiện (`>= 1`).
- Auth lưu review lấy `reviewer_id` từ JWT, scope tenant, không tạo user ẩn danh. Không có bypass xác nhận.

## Suggestion — không chặn

- Badge cuộn lên cha luôn màu open (`StructureViewShell.tsx:222`).
- Một finding neo cả cha và con thì `below` đếm thêm một lần (`conflictAnchors.ts:126-132`).
- Số trên badge trực tiếp gồm cả `dismissed`.
- Mục lục văn bản không truyền `collapsed`, marker chỉ-hậu-duệ không hiện.
- Join reviewer trong `_latest_actions` có thể phồng `action_count` nếu một id khớp hai dòng user (`repository_impl.py:213-223`).
- `card.sources` được tính nhưng không render.

## E2E

- `http://localhost:8000/health` → 200
- `http://localhost:5173` → 200
- `GET /api/v1/dossiers/dos_01M3BPQFSXW68FGZJ1RPFMYXTY/conflicts` không token → 401
- Không đăng nhập được nên không bấm badge, ba nút, hai nút trích dẫn trên trình duyệt.
- Biên serialize đã chạy thật: `latest` không có trên payload list.

## Kiến trúc

`docs/system-architecture.md` sha256 `c441d6d9d74169179890f98eb395a0bab47cfc0aab9b9d3b3c30c03cf00dab5e` (bản 2026-09-25) ghi frontend chưa có HITL client. Code hiện đã nối `ConflictFindingReview`. Đó là doc đi sau code, không phải lý do BLOCK. Glob `**/schemas/*.json` của preflight trúng schema harness chưa track, không phải schema sản phẩm.

## Việc cần sửa trước khi gỡ BLOCK

Thêm `latest` vào `FindingReviewDTO` của conflict list và truyền `review_raw["latest"]` trong `from_row`. Thêm một test: row có `latest` thì JSON list còn `action`, tên, email, `reviewed_at`, `action_count`.
