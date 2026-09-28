# Code review final R6 — AI2 long-running architecture

## Verdict

**BLOCKED**. Current source vẫn còn một Critical và ba Important có code evidence, đã được tái hiện bằng runtime probe trước khi kết thúc review. Vì vậy chưa đủ điều kiện `PASS` hoặc `PASS_WITH_RISK`.

Review chỉ đọc; không sửa code/docs, không commit/push.

## Phạm vi và bằng chứng verification

Đã đối chiếu source hiện tại, test/call sites trong `ai-service/app`, `ai-service/scripts`, `ai-service/src`, các caller liên quan trong tree production, P0–P9 artifacts, `docs/code-standards.md`, `docs/system-architecture.md` và các report R2–R5. Architecture review đã được thực hiện.

Các kiểm tra đã chạy trước yêu cầu kết thúc:

- Focused riêng: P5 `26 passed`, P6 `12 passed`, P9 `40 passed`.
- Focused gộp P5/P6/P9: `78 passed`.
- Targeted P0–P9: `132 passed`.
- Evals tests: `47 passed`.
- Production eval CLI: cả `ai2_contract_package` và `ai2_grounded_query` đều `100.0%`, `P0 GATE: PASS`, `OVERALL: PASS`.
- Full AI service: `357 passed, 6 deselected, 1 warning`.
- Compile: `compileall -q ai-service/app ai-service/src`, `COMPILE_EXIT=0`.
- Approval concurrency probe: `1 EXPLICIT_APPROVAL`, `31 APPROVAL_REPLAY`.
- `git diff --check`: exit `0`.

Warning duy nhất của full suite là `DeprecationWarning` từ Starlette TestClient. `hs-run review next` không khởi chạy được vì wrapper Windows hiện lỗi parse command (`'un' is not recognized...`); các verification trên được chạy trực tiếp bằng project-local Python và workspace-local `TEMP`/`TMP`.

## Findings còn mở

### Critical R6-001 — Redaction có thể bị bypass bằng custom `str` key và làm lộ secret

Evidence:

```text
ai-service/app/security/policy.py:73-91
ai-service/app/transport/events.py:51-53
ai-service/app/transport/events.py:177-183
```

`_is_sensitive_key()` gọi `str(key)` trước khi nhận diện `prompt`, `secret`, `token`, `raw_contract` hoặc `hidden_reasoning`. Một `str` subclass override `__str__()` trả giá trị an toàn nhưng vẫn giữ nội dung key nhạy cảm; probe:

```text
redact({SneakyKey("prompt"): "SECRET"}) -> {'prompt': 'SECRET'}
map_to_agui(... payload={SneakyKey("prompt"): "SECRET"}) -> payload {'prompt': 'SECRET'}
```

Như vậy audit redaction và AG-UI sanitizer có thể đưa prompt/secret ra ngoài boundary. Fix cần reject non-plain mapping keys hoặc canonicalize key bằng built-in exact-string semantics trước khi phân loại và serialize; regression phải bao phủ nested mapping/list/tuple và cả hai utility.

### Important R6-002 — AG-UI exact top-level key allowlist bị bypass bằng custom key equality/hash

Evidence:

```text
ai-service/app/transport/events.py:121-123
ai-service/app/transport/events.py:191-195
ai-service/app/transport/events.py:227-244
```

`validate_scope()` và `_event_mapping()` kiểm tra `set(event)` nhưng không yêu cầu key là plain `str`. Probe thay key `event_id` bằng `EvilKey("evil-key", "event_id")` cho `validate_scope=True`; `map_to_agui()` trả output có top-level key `"evil-key"`, dù contract yêu cầu exact canonical AG-UI keys. Fix cần kiểm tra `type(key) is str` và exact key set trước mọi lookup/equality, đồng thời tạo output chỉ với canonical plain keys.

### Important R6-003 — Readiness malformed category/config fields ném exception thay vì fail-closed

Evidence:

```text
ai-service/app/ops/readiness.py:29-30
ai-service/app/ops/readiness.py:212-213
ai-service/app/ops/readiness.py:291-298
ai-service/app/ops/readiness.py:313-323
ai-service/app/ops/readiness.py:345-355
```

Probe trực tiếp cho kết quả exception thay vì `ReadinessResult(status="FAIL")`:

```text
OperationalCase(category=None) -> AttributeError: 'NoneType' object has no attribute 'strip'
RollbackReadiness(owner=None) -> AttributeError: 'NoneType' object has no attribute 'strip'
ReadinessConfig(rto_denominator=None) -> AttributeError: 'NoneType' object has no attribute 'strip'
```

Ngoài ra `_canonical()` gọi method `.strip()` do caller cung cấp, nên custom `str` subclass có thể ném exception. Đây là boundary P9 không fail-closed và có thể làm caller/gate mất kết quả readiness. Fix cần validate/canonicalize mọi string field trước khi dùng, reject malformed container/type và chuyển mọi malformed evidence/config thành check FAIL ổn định.

### Important R6-004 — `AuthzRequest` payload sai kiểu vẫn được authorize

Evidence:

```text
ai-service/app/security/policy.py:557-577
ai-service/app/security/policy.py:609-617
ai-service/app/security/policy.py:654-677
```

`_canonical_authz_request()` đặt payload không phải `Mapping` thành `None` nhưng không hạ `valid=False`. Probe với principal hợp lệ và `action="hitl.command"`:

```text
payload=3      -> allowed=True, code=AUTHORIZED, normalized payload={}
payload=object() -> allowed=True, code=AUTHORIZED, normalized payload={}
```

Direct malformed request vì vậy không fail-closed; đặc biệt authorization digest/decision có thể không còn tương ứng với payload mà caller tiếp tục thực thi. Fix cần coi payload khác `Mapping | None` là invalid và deny, hoặc trả canonical request bắt buộc để caller thực thi đúng object đã authorize.

## Các finding R5 đã đóng

- SecurityPolicy cross-tenant/dossier với `str` subclass: đã canonicalize và probe deny.
- Event `tenant_id`/`run_id`/`resource_id` và `map_to_agui()` scope: đã canonicalize và probe deny.
- `SseSession` tenant/run/principal/resource binding: đã normalize plain `str`, frozen normal mutation bị reject.
- Approval TTL `NaN`/`Inf` và numeric subclass: exact built-in numeric check + finite check, probe reject.
- `idempotency_key=None`: malformed `AuthzRequest` trả deny ổn định thay vì `.strip()` exception.
- Approval direct constructor/proof mutation, exact command digest, expiry, replay và concurrent one-time consumption: không tái hiện bypass.
- Readiness strict booleans, finite numbers, duplicate IDs, unknown/category mismatch và missing evidence: các test/probe hiện hữu đều fail-closed cho các input đó.

## Caller, artifact drift và prototype limitations

Production caller scan không tìm thấy caller thực thi `SecurityPolicy`, `ToolPolicy`, `SseSession`, `map_to_agui()` hoặc `evaluate_readiness()` ngoài re-export; không có HTTP/SSE route hiện tại để biến prototype limitation thành caller bypass.

Các limitation được document rõ và không tính là finding mới: chưa có HTTP auth/approval issuer thật, durable/shared approval ledger, multi-worker replay boundary, HTTP/SSE production route, live event server hoặc HA/recovery proof. Các giới hạn này được nêu trong `docs/system-architecture.md:43-47,53,61-64,70,75` và `docs/code-standards.md:31-35,52-55`.

Artifact drift còn tồn tại:

- `plans/260923-1023-ai2-long-running-architecture/artifacts/p5-api-security-contract.json:19` ghi `11 passed`, source hiện tại P5 là `26 passed`.
- `plans/260923-1023-ai2-long-running-architecture/artifacts/p6-event-ui-convergence.json:21-23` ghi `3 passed`/`55 passed`, source hiện tại P6 là `12 passed`.
- `plans/260923-1023-ai2-long-running-architecture/artifacts/p9-production-readiness.json:21-23` ghi `7 passed`/`68 passed`, source hiện tại P9 là `40 passed`.

Drift này không thay đổi severity các finding source ở trên, nhưng các acceptance/status `PASS` trong P6/P9 artifacts không thể được dùng làm bằng chứng đã phủ các adversarial paths R6.

## Final decision

`BLOCKED`: R6-001 là Critical; R6-002, R6-003 và R6-004 là Important, đều có code evidence và runtime reproduction. Test/eval xanh không loại bỏ được các malformed/custom-boundary paths này. Cần sửa và re-review trước khi có thể ghi `PASS`.
