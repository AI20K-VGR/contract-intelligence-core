# Code review R4 — AI2 long-running architecture

## Verdict

**BLOCKED**. Còn Important findings có code evidence và runtime reproduction. Vì vậy chưa đủ điều kiện `PASS` hoặc `PASS_WITH_RISK` theo gate yêu cầu không còn Critical/Important.

Review chỉ đọc; không sửa code/test, không commit/push.

## Phạm vi và bằng chứng verification

Đã đọc trực tiếp source, tests và call sites của:

- `ai-service/app/security/policy.py`
- `ai-service/app/transport/events.py`
- `ai-service/app/ops/readiness.py`
- `ai-service/tests/test_p5_api_security.py`
- `ai-service/tests/test_p6_event_ui_convergence.py`
- `ai-service/tests/test_p9_production_readiness.py`
- production callers/imports trong `ai-service/app`, `ai-service/scripts`, `ai-service/src`

Verification mới chạy với `TEMP`/`TMP` workspace-local:

- Focused P5/P6/P9: `40 passed, 1 warning`.
- Targeted P0–P9: `115 passed, 2 warnings`.
- Evals: `47 passed`.
- Full AI service: `319 passed, 6 deselected, 2 warnings`.
- Compile: `.venv\Scripts\python.exe -m compileall -q app`, exit code `0`.
- Concurrent grant probe: `1` lần `EXPLICIT_APPROVAL`, `15` lần `APPROVAL_REPLAY`; atomic one-time consumption hiện hoạt động trong process.

Các warning chỉ là `PytestCacheWarning`/`DeprecationWarning`; không có test failure.

## Findings

### Important R4-001 — Approval TTL không reject `NaN`/`+Inf`, tạo grant không hết hạn

Evidence:

```text
ai-service/app/security/policy.py:269-272
if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) or ttl_seconds < 0:
    raise AuthorizationError("INVALID_APPROVAL", "approval TTL must be a non-negative number")
```

```text
ai-service/app/security/policy.py:286
"expires_at": now + float(ttl_seconds),
```

```text
ai-service/app/security/policy.py:316-317
if time.time() >= grant.expires_at:
    return "APPROVAL_EXPIRED"
```

Runtime probe: `ttl_seconds=math.nan` và `ttl_seconds=math.inf` đều được issuer chấp nhận; `ToolPolicy.authorize(...)` trả `EXPLICIT_APPROVAL`. Với `NaN`, phép so sánh `time.time() >= expires_at` luôn false; grant được mô tả là expiring nhưng không bao giờ expire. Đây là đường cấp quyền side-effect sai, không phải chỉ là limitation durable store.

Fix cần reject mọi TTL không finite (và policy rõ ràng cho vô hạn), trước khi tính `expires_at`; giữ expiry check và consumption trong atomic boundary.

### Important R4-002 — Readiness có thể PASS với evidence boolean/string giả

Evidence:

```text
ai-service/app/ops/readiness.py:348-352
if not case.passed:
    missing_required.append(f"{case_id} (failed)")
if not _positive(case.denominator):
    missing_required.append(f"{case_id} (positive denominator required)")
```

```text
ai-service/app/ops/readiness.py:287-293
rollback_ok = all(
    (
        rollback.legacy_path_available,
        rollback.canary_feature_flag,
        rollback.rollback_drill_passed,
        bool(rollback.owner.strip()),
    )
)
```

Runtime probe: thay `OperationalCase.passed` của required case bằng chuỗi `"false"` vẫn cho readiness `passed=True`; thay ba cờ rollback bằng chuỗi `"false"` cũng cho `passed=True`. Các fix duplicate ID, unknown category và boolean denominator đều hoạt động, nhưng type validation chưa bao phủ các boolean evidence khác. Đây là readiness fail-open: evidence không phải boolean thật có thể được tính là PASS.

Fix cần validate runtime `case.passed`, `case.required`, và các rollback flags là `bool` thật; giá trị sai type phải làm readiness FAIL.

### Important R4-003 — SseSession không validate kiểu binding trước equality; object equality tùy biến có thể forge authorization

Evidence:

```text
ai-service/app/transport/events.py:224-226
authorized: bool = False,
principal_id: str | None = None,
resource_id: str | None = None,
```

```text
ai-service/app/transport/events.py:267-271
and principal.tenant_id == self.tenant_id
and principal.actor_id == self.principal_id
and run_id == self.run_id
and resource_id == self.resource_id
and "stream.read" in ROLE_ACTIONS.get(principal.role.strip().lower(), frozenset())
```

Constructor chỉ validate `tenant_id`, `run_id`, `last_sequence`; `principal_id` và `resource_id` nhận object tùy ý. Runtime probe dùng một `str` subclass override `__eq__` và session vẫn `authorize(...) == True` dù giá trị không đúng, sau đó heartbeat trả metadata. Với input primitive malformed như `int`, đường hiện tại deny; nhưng public constructor không được phép dựa vào equality do caller kiểm soát.

Fix cần bắt buộc `principal_id`/`resource_id` là `str` non-empty (hoặc `None` theo policy) trước khi lưu, chuẩn hóa thành plain `str`, và so sánh binding bằng giá trị đã validate.

## Các đường đã kiểm tra và không tạo finding

- Direct `Principal(...)` và `ApprovalGrant(...)` đều raise `AuthorizationError`.
- HMAC/proof mutation bằng `object.__setattr__` làm principal/grant không còn trusted; grant sửa digest trả `APPROVAL_INVALID`.
- Approval scope, exact command digest, expiry `ttl_seconds=0`, replay và concurrent one-time consumption đều deny/atomic đúng trong process.
- `SseSession(..., authorized=True)` bị reject; normal `setattr` sau authorize bị `FrozenInstanceError`; retarget bằng normal attribute mutation không thành công.
- `map_to_agui()` reject top-level extra keys, reject resource khi expected resource absent, reject missing resource khi expected resource present; nested redaction cho mapping/list/tuple và sensitive top-level raw key hoạt động. Typed `EventEnvelope` bị reject nếu caller yêu cầu resource mà envelope không mang resource field, phù hợp contract hiện tại.
- Readiness duplicate IDs, unknown category, category mismatch và boolean denominator đều fail closed trong test/probe hiện tại.
- Actor-bound idempotency: key trong `SecurityPolicy` gồm `tenant_id`, `dossier_id`, `actor_id`, `idempotency_key`; retry actor khác không nhận cached decision/audit của actor trước.
- Không tìm thấy production caller nào của `SecurityPolicy`, `ToolPolicy`, `SseSession`, `map_to_agui()` hoặc `evaluate_readiness()` trong `ai-service/app`, `ai-service/scripts`, `ai-service/src`; `app/transport/__init__.py` chỉ re-export API. Vì vậy hiện chưa có production route vô tình bypass các primitive này.

## Prototype limitations, không đánh đồng với finding mới

- `issue_trusted_principal()` và `issue_approval_grant()` là public prototype issuer seams; chưa có HTTP authentication hoặc approval issuer thật. Việc ai được phép gọi seam là trách nhiệm integration boundary chưa tồn tại, không được dùng như bằng chứng production auth đã hoàn chỉnh.
- HMAC secret và consumed registry của approval là process-local; chưa có durable/shared atomic store hoặc multi-worker replay protection. Đây là limitation đã ghi rõ trong `docs/system-architecture.md` và R3 fix report, không phải bằng chứng hiện có production caller bypass.
- Chưa có HTTP/SSE production route, live event server, HA hay recovery proof; `SseSession`/AG-UI chỉ là library primitives.
- `object.__setattr__` có thể ép `_authorized=True` hoặc retarget frozen object trong cùng Python process. Đây là same-process tamper/unsafe-code limitation; normal constructor/setattr và proof checks đã được kiểm tra. Không có HTTP route hiện tại để biến đường này thành external caller bypass.

## Non-blocking drift

`plans/260923-1023-ai2-long-running-architecture/artifacts/p5-api-security-contract.json` vẫn mô tả idempotency tuple là `(tenant_id, dossier_id, idempotency_key)`, trong khi source và test R3 đã actor-bind key. Đây là evidence/documentation drift cần cập nhật ở vòng thay đổi docs riêng; không làm mất code fix actor-bound hiện tại.

## Final decision

`BLOCKED` vì R4-001, R4-002 và R4-003 là Important findings còn reproducible. Cần sửa và chạy lại review; chưa thể PASS chỉ dựa trên `319 passed`.
