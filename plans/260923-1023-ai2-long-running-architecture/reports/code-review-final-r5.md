# Code review final R5 — AI2 long-running architecture

## Verdict

**BLOCKED**. Vẫn còn Critical/Important có code evidence và runtime reproduction; vì vậy chưa đủ điều kiện `PASS` hoặc `PASS_WITH_RISK`. Review chỉ đọc; không sửa source/docs, không commit/push.

## Phạm vi và verification

Đã đối chiếu source hiện tại, tests, call sites trong `ai-service/app`, `ai-service/scripts`, `ai-service/src`, P0–P9 artifacts, plan contract và `docs/system-architecture.md`/`docs/code-standards.md`. Không tìm thấy production caller nào ngoài re-export đối với `SecurityPolicy`, `ToolPolicy`, `SseSession`, `map_to_agui()` hoặc `evaluate_readiness()`; limitation về HTTP auth/HTTP-SSE/durable multi-worker vẫn được giữ là prototype limitation, không dùng làm finding external route.

Verification độc lập đã có trong workspace-local temp:

- Focused P5/P6/P9: `61 passed`.
- Targeted P0–P9: `115 passed, 1 warning`.
- Evals: `47 passed`.
- Full AI service: `340 passed, 6 deselected, 1 warning`.
- Compile: `python -m compileall -q app src`, `COMPILE_EXIT=0`.
- Fresh focused counts: P5 `23 passed`, P6 `10 passed`, P9 `28 passed`.
- Warning không làm fail gate: `DeprecationWarning` từ `starlette.testclient`; các lần chạy có cache warning cũ không làm test fail.

## Findings còn mở

### Critical R5-001 — SecurityPolicy vẫn có thể bị bypass cross-tenant bằng `str` subclass

Evidence:

```text
ai-service/app/security/policy.py:57-59
def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
```

```text
ai-service/app/security/policy.py:541-556
if request.tenant_id != request.principal.tenant_id:
    return self._decision(request, False, "CROSS_TENANT", "principal and request tenants differ")
...
if expected_tenant is not None and request.tenant_id != expected_tenant:
    return self._decision(request, False, "CROSS_TENANT", "request is outside the tenant scope")
```

Runtime probe với `AlwaysEqualString("tenant-b")` làm `request.tenant_id` trả `allowed=True` trong policy bind `tenant-a/dossier-a`: `SECURITY_CROSS_TENANT_SUBCLASS True`. Type check hiện chấp nhận subclass và equality nằm trên object do caller cung cấp; đây là bypass scope authorization, không phải limitation durable store.

Fix cần canonicalize/reject subclass thành plain `str` cho toàn bộ identity/scope input trước mọi equality và cache-key operation; áp dụng cùng invariant cho request/principal/policy scope và thêm regression test cross-tenant subclass.

### Critical R5-002 — Event scope validation và AG-UI mapper vẫn fail-open với `str` subclass

Evidence:

```text
ai-service/app/transport/events.py:72-74
def _valid_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
```

```text
ai-service/app/transport/events.py:107-130
and _value(event, "tenant_id") == tenant_id
and _value(event, "run_id") == run_id
...
or (
    _valid_nonempty_string(resource_id)
    and _value(event, "resource_id") == resource_id
)
```

Runtime probe với raw event mang `tenant_id=AlwaysEqualString("tenant-b")` và `run_id=AlwaysEqualString("run-other")` trả `validate_scope=True` và `map_to_agui(... expected tenant-a/run-1) is not None`: `EVENT_CROSS_SCOPE_SUBCLASS True True`. Mapper vì vậy có thể đưa event ngoài scope vào AG-UI boundary. Đây là cross-scope data exposure ở transport primitive.

Fix phải chuẩn hóa/reject plain-string scope values trước comparison và trước output; regression cần phủ tenant, run và resource subclass.

### Important R5-003 — R4 finite TTL vẫn bypass được bằng `float` subclass

Evidence:

```text
ai-service/app/security/policy.py:272-279
if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)):
    raise AuthorizationError("INVALID_APPROVAL", "approval TTL must be a non-negative number")
...
if not ttl_is_finite or ttl_seconds < 0:
    raise AuthorizationError("INVALID_APPROVAL", "approval TTL must be a non-negative number")
```

```text
ai-service/app/security/policy.py:293
"expires_at": now + float(ttl_seconds),
```

Runtime probe dùng `EvilFloat(1.0)` với `__float__()` trả `inf`: `math.isfinite(ttl_seconds)` là `True`, nhưng grant có `expires_at=inf` và `ToolPolicy.authorize(...)` trả `EXPLICIT_APPROVAL`. Như vậy fix R4 mới chỉ kiểm tra giá trị underlying ở `math.isfinite`, nhưng lại gọi conversion có thể bị override; approval side effect có thể không hết hạn.

Fix dùng exact built-in numeric normalization/reject subclasses trước finite check, sau đó chỉ dùng giá trị đã canonicalize để tính expiry; thêm regression cho numeric subclasses.

### Important R5-004 — SseSession chỉ normalize optional bindings; `tenant_id`/`run_id` vẫn forge được

Evidence:

```text
ai-service/app/transport/events.py:241-255
if not isinstance(tenant_id, str) or not tenant_id.strip() or not isinstance(run_id, str) or not run_id.strip():
    raise ValueError("tenant_id and run_id are required")
...
object.__setattr__(self, "tenant_id", tenant_id)
object.__setattr__(self, "run_id", run_id)
...
object.__setattr__(self, "principal_id", normalised_principal_id)
object.__setattr__(self, "resource_id", normalised_resource_id)
```

Runtime probe với `tenant_id`/`run_id` là `AlwaysEqualString` trả `authorize=True` cho trusted principal của `tenant-a/run-1`, sau đó `heartbeat()` trả `tenant-b/run-other`. R4 đã chuẩn hóa `principal_id`/`resource_id`, nhưng binding tenant/run còn cùng lỗi equality tùy biến; điều này mâu thuẫn với contract “binding normalized immutable”. Chưa có production SSE route nên mức này là Important ở library boundary, không phải bằng chứng đã có external HTTP bypass.

Fix canonicalize/reject mọi session scope binding, tối thiểu tenant/run cùng principal/resource, trước khi lưu frozen state.

### Important R5-005 — Malformed command request gây exception thay vì deny

Evidence:

```text
ai-service/app/security/policy.py:563-565
if action == "hitl.command":
    if not request.idempotency_key.strip():
        return self._decision(request, False, "IDEMPOTENCY_KEY_REQUIRED", "command key is required")
```

`AuthzRequest` là public dataclass không validate runtime. Probe `idempotency_key=None` trên request có principal hợp lệ ném `AttributeError: 'NoneType' object has no attribute 'strip'`, thay vì trả decision deny ổn định. Đây vi phạm fail-closed malformed boundary và có thể biến input sai schema thành 500/DoS ở caller.

Fix kiểm tra non-empty string trước `.strip()` và trả error code deny; rà soát tương tự cho các field boundary có thao tác string trực tiếp.

## Non-blocking observations

- `evaluate_readiness()` trả PASS với `rto_target_seconds=float("inf")` và `retention_days=float("inf")`; `_positive()` tại `ai-service/app/ops/readiness.py:32-38` chỉ kiểm tra `> 0`. Contract hiện ghi “positive”, chưa ghi “finite”, nên ghi nhận đây là boundary hardening gap, không dùng để nâng severity nếu policy chấp nhận vô hạn.
- Verification counts trong phase artifacts đã stale so với source hiện tại: P5 artifact ghi `11 passed` tại `p5-api-security-contract.json:18-20` trong khi fresh P5 là `23 passed`; P6 ghi `3 passed`/`55 passed` tại `p6-event-ui-convergence.json:20-23` trong khi fresh P6 là `10 passed`; P9 ghi `7 passed`/`68 passed` tại `p9-production-readiness.json:20-23` trong khi fresh P9 là `28 passed`. Đây là evidence/contract-artifact drift, không phải source defect mới. Actor-bound idempotency tuple trong P5 artifact đã aligned.
- Compatibility scan không thấy in-repo production caller bị vỡ. Tuy nhiên public helper contract đã harden: `map_to_agui()` bắt buộc `expected_tenant_id`/`expected_run_id`, còn `SseSession.authorize()` cần trusted principal cùng `run_id`/`resource_id`; external callers của prototype cũ cần migration. Đây là deliberate security contract delta, chưa có caller trong repo để biến thành finding active.

## Prior findings / prototype limitations

- R4 finite TTL, strict readiness booleans và normalized optional SseSession bindings đã có regression tests, nhưng R5-003 và R5-004 chứng minh coverage chưa bao phủ numeric/string subclasses.
- Approval issuer, trusted principal issuer, consumed registry và idempotency cache vẫn process-local; docs đã ghi rõ cần durable/shared boundary cho production. Không coi đây là finding mới vì không có production caller bypass trong scope hiện tại.
- Không có HTTP/SSE production route, HA, durable approval ledger hoặc live recovery proof; đây là limitation đã được plan/docs ghi nhận.

## Final decision

`BLOCKED` vì R5-001/R5-002 là Critical và R5-003/R5-004/R5-005 là Important, đều có code evidence và runtime reproduction. Test/eval xanh không phủ các malformed/trust-boundary inputs này. Cần sửa và re-review; `PASS_WITH_RISK` cũng không phù hợp vì còn Critical/Important chưa được giải quyết.
