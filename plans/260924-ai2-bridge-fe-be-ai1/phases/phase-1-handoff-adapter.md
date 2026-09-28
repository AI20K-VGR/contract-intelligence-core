# P1 — AI1 snapshot → canonical AI2 handoff adapter

## Mục tiêu

Tạo boundary chuẩn hóa output AI1 hiện tại thành request input mà AI2 hiểu được, không làm mất provenance và không suy diễn metadata thiếu.

## Module/file dự kiến

- Backend: thêm module adapter cạnh `shared/ai/` hoặc package integration mới, theo quyết định ownership ở P0.
- Backend: thêm canonical request DTO/validator và field-level mapper.
- AI2: chỉ sửa compatibility parser nếu P0 chứng minh BE không thể xử lý `ai1.snapshot.v3` mà vẫn giữ evidence.
- Test: adapter, schema, property/negative tests.

## Contract

- Input có nhiều snapshot nhưng cùng `dossier_id`/tenant.
- Mỗi snapshot giữ `document_id`, `snapshot_id`, `source_digest`, pages/blocks/tables/citations.
- `dossier_members` và `role_relation_map` là explicit.
- Thiếu field bắt buộc không được bù; output handoff là rejected hoặc reviewable theo policy.

## Acceptance criteria

- Body+annex được dựng thành một canonical request duy nhất.
- Digest được tính/kiểm tra nhất quán; mismatch bị chặn.
- Không có citation giả được tạo từ `data/meta` thiếu provenance.
- Adapter idempotent và deterministic với cùng input.
- Backward path không bị gọi qua adapter khi flag tắt.

## Test cases

- v3→canonical hợp lệ.
- body-only.
- body+annex explicit relation.
- nhiều annex cùng loại.
- thiếu page/block/table reference.
- duplicate document ID.
- digest mismatch.
- tenant/dossier membership mismatch.
- malformed JSON và schema version không hỗ trợ.

## Verification artifact

Adapter contract test report, canonical JSON fixture diff và “no fabricated evidence” assertion report.

## Risk / rollback

Risk lớn nhất là mapping sai role hoặc làm mất citation. Rollback: flag canonical off; legacy orchestration tiếp tục dùng client cũ.

## Dependency

P0 contract matrix.

