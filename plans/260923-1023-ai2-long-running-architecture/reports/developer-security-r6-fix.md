# Báo cáo Developer — sửa bảo mật R6

## Kết luận

Đã sửa bốn finding R6 trong phạm vi AI2 source/tests/report. Không commit, không push. Các regression mới đã RED trước khi sửa và GREEN sau khi sửa. Không cập nhật phase artifacts; `verification.yaml` và các phase artifact lịch sử không bị ghi đè.

## Nguyên nhân và bản sửa

- **R6-001 — Critical, redaction key spoof:** `ai-service/app/security/policy.py:73` và `ai-service/app/transport/events.py:51` không còn gọi caller-overridden `__str__` cho mapping key. `redact()` (`ai-service/app/security/policy.py:80`) và transport `_sanitize()` (`ai-service/app/transport/events.py:184`) chỉ giữ key có `type(key) is str`; key subclass/non-string bị drop, plain sensitive key vẫn bị redact. Mapping nested trong `list`/`tuple` cũng đi qua cùng policy.
- **R6-002 — Important, AG-UI raw mapping spoof:** `validate_scope()` (`ai-service/app/transport/events.py:101`) kiểm tra toàn bộ raw key bằng `_canonical_raw_event()` (`ai-service/app/transport/events.py:210`) trước mọi set/equality/lookup. Key phải là plain `str` và thuộc allowlist canonical; output `_event_mapping()` (`ai-service/app/transport/events.py:202`) là dict mới chỉ có canonical plain keys. Các key spoof `event_id`, `tenant_id`, `payload`, `extra` đều reject.
- **R6-003 — Important, readiness malformed input:** `evaluate_readiness()` (`ai-service/app/ops/readiness.py:274`) validate config, rollback, findings và cases trước canonicalization. `category=None`, `owner=None`, config denominator `None`, custom string subclass, malformed container và malformed evidence không còn ném exception; input cấu trúc sai trả `ReadinessResult(status="FAIL")` deterministic qua `_malformed_result()` (`ai-service/app/ops/readiness.py:120`). Boolean/numeric sai kiểu hoặc non-finite vẫn giữ các check cụ thể fail-closed hiện hữu.
- **R6-004 — Important, AuthzRequest payload:** `_canonical_authz_request()` (`ai-service/app/security/policy.py:566`) đánh dấu request invalid khi `payload` khác `Mapping | None`; `SecurityPolicy.authorize()` deny với `INVALID_CONTEXT`, không còn normalize payload int/object thành `{}` rồi authorize.

## Regression tests

- `ai-service/tests/test_p5_api_security.py:153`: `SneakyKey` trong mapping nested/list/tuple và kiểm tra không gọi `__str__`.
- `ai-service/tests/test_p5_api_security.py:550`: payload `int` và `object()` phải deny.
- `ai-service/tests/test_p6_event_ui_convergence.py:150`: `EvilKey` cho `event_id`, `tenant_id`, `payload`, `extra`; validate/map đều reject trước equality/lookup.
- `ai-service/tests/test_p6_event_ui_convergence.py:190`: sanitizer nested mapping/list/tuple không làm lộ sensitive value.
- `ai-service/tests/test_p9_production_readiness.py:363`: malformed config/custom string fail closed; `:391`: malformed category/denominator/container/findings không exception.

## TDD và verification

RED trước implementation:

- P5 regression: `3 failed` — redaction gọi `SneakyKey.__str__`, payload sai kiểu vẫn authorize.
- P6 regression: `4 failed` — raw key equality/lookup có thể chạy và sanitizer gọi `__str__`.
- P9 regression: `8 failed` — malformed readiness ném `AttributeError`/`TypeError` thay vì trả FAIL.

GREEN và các gate sau implementation:

- Focused P5/P6/P9: `94 passed, 1 warning`.
- Targeted P0–P9: `373 passed, 6 deselected, 1 warning`.
- Evals: `11 passed`.
- Full `ai-service`: `373 passed, 6 deselected, 1 warning`.
- Compile: `python -m compileall -q app src`, `COMPILE_EXIT=0`.
- `git diff --check`: không có whitespace error trong diff; Git chỉ cảnh báo line-ending/ACL ignore của môi trường Windows.

Cảnh báo còn lại là `DeprecationWarning` từ `starlette.testclient`; không liên quan bản sửa. Pytest cache ACL đã được tránh bằng `-p no:cacheprovider`/workspace `basetemp` trong các gate cuối.

## Review và phạm vi

Đã rà caller/boundary trực tiếp của `redact`, `map_to_agui`, `validate_scope`, `evaluate_readiness` và `SecurityPolicy.authorize`; không đổi public signature, schema, env var hoặc execution route. Không có phase artifact nào cần cập nhật cho bản sửa này.

## Giới hạn prototype

Sau bản sửa, các giới hạn kiến trúc prototype vẫn giữ nguyên: chưa có HTTP auth middleware/approval issuer production, durable/shared approval ledger, multi-worker replay boundary, HTTP/SSE production route, live event server, HA hoặc recovery proof. `PASS` của các test/eval trên chỉ chứng minh các boundary deterministic trong code hiện tại, không chứng minh deployment production hay live recovery.
