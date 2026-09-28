# Báo cáo developer — P2 Evidence Pipeline

## Implementation

- Mở rộng citation resolver với page revision, source scope, node scope, table/cell scope, exact quote hash và trạng thái `UNVERIFIED` cho cell có geometry `CLAIMED`.
- Bắt buộc mọi đường trả lời `ANSWERED` đi qua grounding finalization; `ANSWERED` chỉ hợp lệ khi `grounded=true` và claim có citation usable.
- Giới hạn retrieval theo selected member, sửa structure duplicate/parent/order theo hướng review-safe, và giữ độc lập giữa các document.
- Bổ sung citation cho party/annex/table và sửa fixture happy bằng hash từ raw text cùng line ID deterministic; không bịa provenance.

## TDD evidence

- Intentional RED: resolver thiếu node registry và retrieval chưa giới hạn selected member.
- Năm hồi quy legacy ban đầu đỏ vì fixture thiếu provenance; đã GREEN bằng source-derived provenance, không nới resolver.
- Targeted P2: `33 passed, 1 warning`.
- Năm test hồi quy: `5 passed`.
- Full offline gate: `215 passed, 6 deselected, 1 warning`.
- Contract registry: `Contract registry OK (5 schemas)`.
- `git diff --check`: PASS.
- Kiểm tra UTF-8/U+FFFD/mojibake trên file thay đổi: PASS.

## Main review

- Chạy lại độc lập targeted P2 và full offline suite với `--basetemp` trong workspace.
- Xác nhận citation không hợp lệ không thể nâng trạng thái thành `ANSWERED`; raw evidence không bị sửa.
- Xác nhận cell geometry `CLAIMED` vẫn giữ raw value nhưng không được xem là citation đã verify.
- Không claim accuracy nghiệp vụ hoặc live-provider behavior.

## Files

- Thay đổi nằm trong resolver, grounding, structure/reasoning, fixture provenance và test coverage của P2; không sửa `plan.md`/phase file và không commit.
