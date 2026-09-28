# Báo cáo docs manager R2 — AI2 long-running architecture

Ngày kiểm tra: `2026-09-24`

## Kết quả

Đã cập nhật đúng hai tài liệu current-state sau khi đối chiếu post-R2 source:

- `docs/code-standards.md`
- `docs/system-architecture.md`

Các cập nhật làm rõ strict trusted `Principal` binding, `SecurityPolicy` constructor-bound scope, giới hạn của `ApprovalGrant`, canonical AG-UI expected scope, `SseSession` resource binding, `REQUIRED_OPERATIONAL_CASES` readiness fail-closed và việc HTTP/SSE production route vẫn absent.

Không sửa code, test, plan, artifact hay file nào khác; không commit/push.

## Evidence từ codebase

- `ai-service/app/security/policy.py:92-108` định nghĩa `Principal` và `ApprovalGrant`; grant bind `approval_id`, tenant, dossier, actor, tool và command digest, không có issuer hoặc durable ledger field.
- `ai-service/app/security/policy.py:302-329` yêu cầu trusted principal, kiểm tra actor/tenant/role binding, bắt buộc policy scope đã bind ở constructor và deny caller scope override/cross-scope.
- `ai-service/app/security/policy.py:422-461` deny `approved=True` cho side effect, yêu cầu `ApprovalGrant` và kiểm tra đầy đủ scope/actor/tool/command digest; read-only tool vẫn được phép.
- `ai-service/app/transport/events.py:70-106` kiểm tra canonical event envelope, tenant/run và resource scope; `:156-186` buộc `map_to_agui()` nhận expected tenant/run/resource.
- `ai-service/app/transport/events.py:189-257` bind `SseSession` với trusted principal, tenant, run, resource và `stream.read`; session read-only, metadata trước authorization bị chặn, command bị từ chối.
- `ai-service/app/ops/readiness.py:17-24` khai báo sáu `REQUIRED_OPERATIONAL_CASES`; `:300-323` fail readiness khi thiếu, sai category, failed hoặc thiếu positive denominator.
- Route inventory của `ai-service/app/api/main.py:1224-1315` chỉ có `POST /jobs/idp` và `GET /jobs/{job_id}` cho lane job; không có HTTP/SSE production route, SSE response stream hoặc replay route. `ai-service/app/transport/events.py:1` và `:189-257` chỉ cung cấp library/session primitives.

## Regression evidence

- `ai-service/tests/test_p5_api_security.py:49-72` kiểm tra cross-scope/override và deny-by-default; `:154-220` kiểm tra `ApprovalGrant` và mismatch.
- `ai-service/tests/test_p6_event_ui_convergence.py:87-118` kiểm tra canonical envelope và AG-UI expected scope; `:121-180` kiểm tra principal/resource/run-bound `SseSession`.
- `ai-service/tests/test_p9_production_readiness.py:79-95` kiểm tra readiness fail-closed khi operational cases rỗng hoặc thiếu case.
- Report post-R2 ghi nhận focused P5/P6/P9 `33 passed, 1 warning` và targeted P0-P9 `87 passed, 1 warning` tại `plans/260923-1023-ai2-long-running-architecture/reports/developer-security-r2-fix.md:19-23`.

## Kiểm tra tài liệu

- Hai tài liệu vẫn ở dưới ngưỡng 800 dòng.
- Nội dung giữ current-state boundary: các primitive/security checks không được nâng thành HTTP wiring, durable issuer/ledger, production SSE, HA hoặc live recovery evidence.
