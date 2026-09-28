# Developer security R2 fix

## Kết quả

Đã xử lý sáu finding bắt buộc trong phạm vi AI2. Không commit/push.

## File đã đổi

- `ai-service/app/security/policy.py`
  - Scope của `SecurityPolicy` được giữ private/read-only; mọi override tenant/dossier khác scope constructor bị deny.
  - `AuthzRequest` bắt buộc có `Principal` binding; actor, tenant và role phải khớp principal. Thiếu binding hoặc read-only tự xưng admin đều fail closed.
  - Thêm `ApprovalGrant` bind `approval_id`, tenant, dossier, actor, tool và command digest. `approved=True` và `approved_tools` không còn cấp quyền side effect; read-only tools vẫn hoạt động.
- `ai-service/app/transport/events.py`
  - `validate_scope()` kiểm tra đầy đủ canonical envelope: event ID/type, schema, tenant/run, sequence, state version/hash, correlation, payload và replayable.
  - `map_to_agui()` bắt buộc expected tenant/run và reject event ngoài scope; hỗ trợ kiểm tra resource ID khi có.
  - `SseSession` yêu cầu trusted principal, run và resource scope khớp; thiếu/sai scope bị deny.
- `ai-service/app/ops/readiness.py`
  - Khai báo sáu required operational cases và fail readiness khi empty, missing, sai category, failed hoặc thiếu denominator.
- `ai-service/tests/test_p5_api_security.py`
- `ai-service/tests/test_p6_event_ui_convergence.py`
- `ai-service/tests/test_p9_production_readiness.py`
  - Thêm/cập nhật regression tests cho các bypass và contract fail-closed.

## TDD / verification

- RED: test mới fail ở collection với `ImportError: cannot import name 'ApprovalGrant'` trước khi production fix được áp dụng.
- Focused P5/P6/P9: `33 passed, 1 warning`.
- Targeted P0-P9: `87 passed, 1 warning`.
- Full `ai-service` với `TEMP/TMP` workspace-local: `312 passed, 6 deselected, 2 warnings`.
- Compile: `.venv\Scripts\python.exe -m compileall -q app` → `exit_code=0`.

Warning còn lại là `PytestCacheWarning` do `.pytest_cache` bị Windows ACL hạn chế và `DeprecationWarning` từ Starlette; không có test failure.

## Limitation còn lại

`ApprovalGrant` là capability/record contract được primitive kiểm tra; việc phát hành và lưu durable record vẫn thuộc trusted approval store/caller, chưa phải durable approval ledger trong module này. AI2 cũng chưa có HTTP/SSE production route; các primitive đã fail closed tại boundary.
