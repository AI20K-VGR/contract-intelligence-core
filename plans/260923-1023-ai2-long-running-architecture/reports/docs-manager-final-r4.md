# Báo cáo docs manager R4 — AI2 long-running architecture

Ngày kiểm tra: `2026-09-24`

## Kết quả

Đã cập nhật đúng hai tài liệu current-state:

- `docs/code-standards.md`
- `docs/system-architecture.md`

Đã tạo report follow-up này tại `plans/260923-1023-ai2-long-running-architecture/reports/docs-manager-final-r4.md`. Không sửa code, test, plan hoặc artifact; không commit/push. Gate decision của R4 không bị thay đổi bởi docs follow-up này.

## Nội dung đối chiếu với source hiện tại

- Approval TTL finite: `issue_approval_grant()` reject TTL không phải số hữu hạn hoặc âm tại `ai-service/app/security/policy.py:272-279`; expiry và one-time consumption nằm trong lock tại `ai-service/app/security/policy.py:321-327`. Consumed registry vẫn process-local/non-durable theo `ai-service/app/security/policy.py:49-50` và docstring `ai-service/app/security/policy.py:174-178`.
- Readiness strict boolean: `_actual_bool()` yêu cầu `type(value) is bool` tại `ai-service/app/ops/readiness.py:45-46`; rollback flags được kiểm tra tại `ai-service/app/ops/readiness.py:291-298`; `OperationalCase.passed` và `required` được kiểm tra tại `ai-service/app/ops/readiness.py:352-359`.
- SseSession normalized immutable bindings: `SseSession` dùng `frozen=True, slots=True` tại `ai-service/app/transport/events.py:217-219`; binding optional được kiểm tra và chuyển về plain `str` tại `ai-service/app/transport/events.py:76-83` và `ai-service/app/transport/events.py:245-254`.
- Actor-bound idempotency: `SecurityPolicy` lưu cache key `(tenant_id, dossier_id, actor_id, idempotency_key)` tại `ai-service/app/security/policy.py:513-514` và `ai-service/app/security/policy.py:563-585`. P5 contract artifact đã aligned tại `plans/260923-1023-ai2-long-running-architecture/artifacts/p5-api-security-contract.json:7-15`.
- Prototype boundary: `issue_trusted_principal()` là prototype seam tại `ai-service/app/security/policy.py:105-110`, `ai-service/app/security/policy.py:142-143`; approval issuer/durable ledger không nằm trong primitive. `SseSession` cũng tự mô tả là read-only và command phải qua HTTP tại `ai-service/app/transport/events.py:217-219`, `ai-service/app/transport/events.py:310-318`.
- Route limitation: route inventory hiện có job HTTP boundary `POST /jobs/idp` và `GET /jobs/{job_id}` tại `ai-service/app/api/main.py:1224-1289`; không có HTTP/SSE production route nối các P5/P6 primitives, nên docs giữ nguyên production-route limitation.

## Verification và giới hạn

- Đã đọc `CLAUDE.md`, quy tắc `documentation-management.md`, `output-rendering.md`, hai tài liệu hiện có, source P5/P6/P9, test tương ứng, R4 review report và P5 contract artifact.
- Đã resolve output register bằng `ai-service\.venv\Scripts\python.exe harness/scripts/output_config.py --resolved`: `language` là `vi`, `audience` là `null`, `code_style` là `3`.
- Hai tài liệu cập nhật vẫn dưới ngưỡng 800 dòng. Nội dung mới chỉ mô tả code/library boundary và evidence hiện có; không nâng readiness `PASS`, approval prototype, SSE primitive hoặc artifact thành production capability.
- UTF-8 được kiểm tra cho hai tài liệu cập nhật và report; không chạy lại test vì đây là docs-only follow-up và không thay đổi code/test.
