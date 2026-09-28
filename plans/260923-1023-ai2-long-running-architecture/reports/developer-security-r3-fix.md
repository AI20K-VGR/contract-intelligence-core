# Developer security R3 fix

## Kết quả

Đã sửa sáu finding R3 trong phạm vi AI2 source/tests. Không commit và không push.

## Thay đổi

- `ai-service/app/security/policy.py`
  - `Principal` không còn dựng trực tiếp được; `issue_trusted_principal()` kiểm tra identity/role, phát hành object bất biến có proof HMAC. Principal giả hoặc role không phải string fail closed.
  - `ApprovalGrant` không còn dựng trực tiếp được; `issue_approval_grant()` bind issuer, expiry, nonce, proof và digest được tính từ `tool_name` cùng `command` thật.
  - Side-effect chỉ được phép khi command hiện tại khớp grant; `approved=True`, `approved_tools` và caller-only `command_digest` không cấp quyền.
  - Consumption grant là atomic trong process qua lock và registry one-time; replay/expiry bị từ chối.
  - Idempotency identity bao gồm `actor_id`, nên decision/audit không bị tái sử dụng giữa actor.
- `ai-service/app/transport/events.py`
  - Raw canonical mapping phải có exact top-level keys; extra leak và resource ngoài scope bị reject.
  - Resource được yêu cầu đầy đủ khi `expected_resource_id` có mặt; raw event có `resource_id` nhưng không có expected resource cũng bị reject.
  - `SseSession` không nhận `authorized=True`, giữ binding tenant/run/resource/principal bất biến và kiểm proof Principal khi authorize.
- `ai-service/app/ops/readiness.py`
  - Duplicate case ID, case ID/category không hợp lệ và category mâu thuẫn đều fail closed.
  - Denominator phải là số dương hợp lệ cho case required; boolean denominator luôn bị loại.
- Regression tests được cập nhật/thêm tại `ai-service/tests/test_p5_api_security.py`, `ai-service/tests/test_p6_event_ui_convergence.py`, `ai-service/tests/test_p9_production_readiness.py`.

## TDD và verification

- RED: `pytest` focused trước implementation dừng ở collection với `2 errors`, do thiếu `issue_approval_grant` và `issue_trusted_principal`; không có test nào được coi là xanh trước fix.
- Focused P5/P6/P9: `40 passed, 1 warning`.
- Targeted P0–P9: `115 passed, 2 warnings`.
- P7 evaluation gate: `5 passed`.
- Full AI service với `TEMP/TMP` workspace-local: `319 passed, 6 deselected, 2 warnings`.
- Compile: `.venv\Scripts\python.exe -m compileall -q app` — `exit_code=0`.

Các warning chỉ là `PytestCacheWarning` do ACL của `.pytest_cache` và `DeprecationWarning` từ Starlette; không có test failure.

## Giới hạn còn lại

- Proof/secret và one-time registry của `ApprovalGrant`/`Principal` hiện chỉ tồn tại trong process prototype. Registry không durable và không đồng bộ giữa worker/process; production cần authenticated issuer và durable atomic approval-consumption store.
- `issue_trusted_principal()` và `issue_approval_grant()` là trusted integration seams cho prototype, không phải HTTP authentication hoặc approval route.
- Các primitive transport vẫn không chứng minh có HTTP/SSE production route, live event server, deployment, HA hoặc recovery thực tế. Readiness `PASS` chỉ phản ánh supplied bounded evidence/configuration.
