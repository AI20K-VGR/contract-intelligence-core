# Báo cáo Developer — sửa bảo mật R5

## Kết luận

Đã hoàn tất sửa R5 trong phạm vi AI2 source/tests/report. Không commit và không push. Năm finding R5 đã được harden bằng canonicalization fail-closed và regression tests; không thay đổi artifact/gate decision cũ.

## Thay đổi

- `ai-service/app/security/policy.py:62` thêm canonicalizer dùng built-in `str.strip`, trả plain `str`; áp dụng cho Principal issuer (`:154`), policy constructor scope (`:580`), toàn bộ AuthzRequest identity fields (`:557`, `:600`), request-context/ledger và tool approval scope. Equality/cache key chỉ dùng giá trị đã canonicalize. AuthzRequest malformed, gồm `idempotency_key=None`, trả deny ổn định thay vì gọi `.strip()` trực tiếp.
- `ai-service/app/security/policy.py:275` chỉ nhận đúng built-in `int`/`float`, loại `bool` và numeric subclass; kiểm tra finite trên TTL canonical và tính expiry từ giá trị đó. Approval identity fields cũng được lưu plain immutable strings.
- `ai-service/app/transport/events.py:76` canonicalize tenant/run/resource/event identity trước scope compare và AG-UI output; `validate_scope()` (`:94`) và `map_to_agui()` (`:199`) không còn phụ thuộc equality của caller subclass. `SseSession` (`:248`) normalize tenant/run trước frozen storage và canonicalize input authorize (`:297`).
- `ai-service/app/ops/readiness.py:33` yêu cầu numeric SLO/retention/recovery là exact built-in finite positive number, loại `NaN`/`Inf`/`-Inf`.
- Regression tests: `ai-service/tests/test_p5_api_security.py:457`, `:512`, `:532`; `ai-service/tests/test_p6_event_ui_convergence.py:262`, `:317`; `ai-service/tests/test_p9_production_readiness.py:337`.

## TDD và verification

RED đã chạy trước implementation trên các regression mới. Các failure tái hiện đúng: cross-tenant/cross-scope subclass được allow, output/session còn subclass, `EvilFloat` không bị reject, malformed idempotency gây exception, và readiness `Inf` vẫn PASS.

GREEN và các gate sau sửa:

- Focused P5/P6/P9: `78 passed`.
- Targeted P0–P9: `132 passed, 1 warning`.
- Evals từ repo root: `11 passed`.
- Full `ai-service`: `357 passed, 6 deselected, 2 warnings`.
- Compile: `.venv\Scripts\python.exe -m compileall -q app src`, exit `0`.

Warnings chỉ gồm pytest cache ACL trên Windows và `starlette.testclient` deprecation; không có test failure. Không có thay đổi ngoài AI2 source/tests và report này.
