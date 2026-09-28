# Báo cáo developer — P3 / ST-046

## Kết quả

Query boundary bind `snapshot_digest` với canonical record trước khi chạy FourLayerReasoner. Contract `ai2.query.v1` bắt buộc digest; digest thiếu hoặc stale trả `INSUFFICIENT_EVIDENCE`. Signed legacy caller không có field version vẫn giữ compatibility. Không đổi L0/L1/L2/L3 semantics.

## Verification

- AI2 query/retrieval/grounding targeted suite: `51 passed`, exit code `0`.
- AI2 full suite: `692 passed, 1 skipped, 27 warnings`, exit code `0`.
- Backend AI2/dossier filtered suite: `78 passed, 184 deselected, 7 warnings`, exit code `0`.
- Metadata-only query và stale digest vẫn fail-closed; valid path tiếp tục dùng reasoner hiện tại.

## Kết luận

P3 đã PASS. Lỗi SQLite/PostgreSQL JSON cast và tương thích `viewer_id` đã được xử lý ở lớp repository/service mà không thay đổi semantics của query reasoning.
