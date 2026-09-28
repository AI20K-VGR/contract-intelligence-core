# Báo cáo docs manager — AI2 long-running architecture

Ngày kiểm tra: `2026-09-24`

## Kết quả

Đã cập nhật hai tài liệu để phản ánh current-state codebase và khôi phục nội dung UTF-8:

- `docs/code-standards.md`
- `docs/system-architecture.md`

Đã tạo report này. Không sửa production code, test, plan, artifact hoặc file nào khác; không commit/push.

## Nội dung đã đối chiếu

- P0–P4: canonical projection, state reducer/HITL, SQLite durable primitives, execution boundary và optional ADK protocol.
- P5: `ai-service/app/security/policy.py` là deny-by-default decision/redaction utility; idempotency cache in-process và chưa tự gắn HTTP route.
- P6: `ai-service/app/transport/events.py` có event envelope, ordering/gap classification, AG-UI allowlist, read-only `SseSession`, heartbeat/cursor/state hash; chưa có HTTP SSE endpoint, replay route hoặc live FE client.
- P7: `evals/workflow_gate.py` chỉ tính business accuracy từ ground truth hợp lệ/approved và workflow invariants deterministic; chưa phải load/soak evidence.
- P8: migration/canary boundary có legacy/canary/canonical, parity diff, idempotency, verified-generation publish guard và rollback primitive; chưa wire production traffic/persistence migration.
- P9: `app/ops/readiness.py` là checker cho supplied configuration/evidence, gồm điều kiện `retention_days >= recovery_window_days`; `PASS` không chứng minh deployment, HA, live traffic hoặc recovery thật.
- API thật hiện tại vẫn là `POST /jobs/idp` + `GET /jobs/{job_id}` với signed service envelope, SQLite job store và FastAPI `BackgroundTasks`.

## Checks

- Đã đọc `CLAUDE.md`, `docs/code-standards.md`, `docs/system-architecture.md` trước khi cập nhật.
- Đã đọc reports/artifacts P0–P9, tester final và code-review final; ưu tiên code hiện tại khi report cũ có claim khác.
- Đã đối chiếu các module và test thực tế P0–P9, đặc biệt security, transport, ops, migration và evaluation.
- Kiểm tra phạm vi thay đổi sau cập nhật: chỉ hai docs và report này được chủ động ghi.
- Kiểm tra kích thước: cả `docs/code-standards.md` và `docs/system-architecture.md` đều dưới ngưỡng 800 dòng.

## Ghi chú giới hạn

Các phase artifact/report được giữ như evidence của boundary/test tương ứng, không được nâng thành production fact. Docs không mô tả HITL durable, SSE live, migration cutover, HA, crash recovery hoặc business accuracy là đã triển khai.
