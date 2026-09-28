# Developer security R4 fix

## Kết quả

Đã hoàn tất bản sửa TDD R4 trong phạm vi AI2 source/tests/report. Không commit và không push.

## Nguyên nhân và thay đổi

- `ai-service/app/security/policy.py:275` dùng `math.isfinite` sau khi kiểm tra kiểu để từ chối TTL không phải số, âm, `NaN` và `+Inf/-Inf`. Việc phát hành grant lỗi trước khi có grant hợp lệ; authorization side effect không được cấp.
- `ai-service/app/ops/readiness.py:45` thêm kiểm tra actual bool (`type(value) is bool`). `OperationalCase.passed`, `OperationalCase.required` và ba cờ rollback chỉ được coi là đạt khi đúng kiểu bool; string, `0` và `1` đều fail closed.
- `ai-service/app/transport/events.py:76` chuẩn hóa `principal_id`/`resource_id` bằng built-in `str` operation trước mọi so sánh. Hai giá trị phải cùng vắng mặt hoặc cùng là chuỗi không rỗng; str subclass có `__eq__` độc hại không thể forge scope.
- `ai-service/tests/test_p5_api_security.py:412`, `ai-service/tests/test_p6_event_ui_convergence.py:240`, và `ai-service/tests/test_p9_production_readiness.py:287`/`310` thêm regression coverage.
- `plans/260923-1023-ai2-long-running-architecture/artifacts/p5-api-security-contract.json:12` cập nhật đúng tuple idempotency thành `(tenant_id, dossier_id, actor_id, idempotency_key)`; không đổi contract không liên quan.

## TDD và verification

- RED trước implementation: `17 failed, 44 passed, 2 warnings` trên các test P5/P6/P9 mới và hiện hữu. Các failure đúng vào ba lỗi cần sửa.
- GREEN focused sau implementation: `61 passed, 1 warning`.
- Focused riêng: P5 `23 passed`, P6 `10 passed`, P9 `28 passed`.
- P0–P9: `115 passed, 1 warning`.
- Evals toàn bộ test harness và contract tests: `47 passed` (trong đó contract tests là `36 passed`).
- Production eval `ai2_contract_package`: maturity `100.0%`, `P0 GATE: PASS`, `OVERALL: PASS`.
- Production eval `ai2_grounded_query`: maturity `100.0%`, `P0 GATE: PASS`, `OVERALL: PASS`.
- Full `ai-service`: `340 passed, 6 deselected, 2 warnings`.
- Compile: `.venv\Scripts\python.exe -m compileall -q app src` trả `exit_code=0`.
- Artifact JSON đã được cập nhật riêng theo yêu cầu; không có gate decision nào bị thay đổi.

Các warning không phải failure: pytest không ghi được `.pytest_cache` do ACL Windows; full suite còn có `DeprecationWarning` từ `starlette.testclient`.

## Giới hạn còn lại

- `ApprovalGrant` và `Principal` vẫn là primitive prototype in-process; proof/nonce/consumption cache không durable và không đồng bộ giữa worker/process.
- `issue_trusted_principal()` và `issue_approval_grant()` vẫn là trusted integration seams, không phải HTTP authentication hoặc approval route hoàn chỉnh.
- `SseSession` và readiness evaluator không chứng minh HTTP/SSE production route, deployment, HA, live traffic safety hoặc recovery thực tế.
- Readiness `PASS` chỉ phản ánh bounded evidence/configuration được cung cấp; compileall chỉ xác nhận khả năng biên dịch, không thay thế test runtime.
