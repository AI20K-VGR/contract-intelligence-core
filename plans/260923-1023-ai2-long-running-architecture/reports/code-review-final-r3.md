# Code review final R3 — AI2 long-running architecture

## Phạm vi và phương pháp

Review chỉ đọc, không sửa code, không commit/push. Đã kiểm tra source hiện tại, test trực tiếp và call site của:

- `ai-service/app/security/policy.py`
- `ai-service/app/transport/events.py`
- `ai-service/app/ops/readiness.py`
- `ai-service/tests/test_p5_api_security.py`
- `ai-service/tests/test_p6_event_ui_convergence.py`
- `ai-service/tests/test_p9_production_readiness.py`
- các boundary/test P0–P9 liên quan đến scope, replay, persistence và idempotency.

Không có production call site nào hiện dùng `SecurityPolicy`, `ToolPolicy`, `SseSession`, `map_to_agui()` hoặc `evaluate_readiness()`; các module này hiện là public library primitives, phù hợp limitation trong `docs/system-architecture.md`, nhưng bypass trực tiếp trong primitive vẫn không đạt contract fail-closed.

Independent evidence đã có:

- Focused P5/P6/P9: `33 passed`.
- Targeted P0–P9: `87 passed`.
- P7 evaluation gate: `5 passed`.
- `compileall -q app`: `EXIT=0`.

Các lỗi cleanup pytest Windows khi dùng cùng basetemp đã được tách khỏi test execution; lần chạy tuần tự với TEMP/TMP và basetemp workspace-local riêng đạt `87 passed`.

## Findings

### Critical R3-001 — ApprovalGrant tự dựng được coi là approval hợp lệ và replay vô hạn

Evidence:

```text
ai-service/app/security/policy.py:98-107
@dataclass(frozen=True)
class ApprovalGrant:
    """Validated approval capability bound to one actor, resource and command."""
    approval_id: str
    tenant_id: str
    dossier_id: str
    actor_id: str
    tool_name: str
    command_digest: str
```

```text
ai-service/app/security/policy.py:439-461
if not isinstance(approval, ApprovalGrant):
    return ToolDecision(False, "SIDE_EFFECT_APPROVAL_REQUIRED", tool_name)
...
if approval.command_digest != command_digest:
    return ToolDecision(False, "APPROVAL_COMMAND_MISMATCH", tool_name)
return ToolDecision(True, "EXPLICIT_APPROVAL", tool_name)
```

Probe runtime cho kết quả `free_grant_allowed= True` và lần gọi lại cùng object cho `same_grant_replay= True`. Bất kỳ caller nào có thể import constructor đều tự tạo record có field khớp; không có issuer, expiry, nonce/consumed state hoặc replay check. `command_digest` chỉ được so sánh với digest do caller truyền vào, không được verifier tin cậy tính và gắn với command.

Đây là side-effect authorization bypass, không chỉ là limitation durable ledger. Cần capability opaque hoặc verifier/factory đáng tin cậy, bind issuer, expiry, one-time/replay state và digest của command thực tế.

### Critical R3-002 — SseSession có thể bị forge hoặc retarget sau authorize

Evidence:

```text
ai-service/app/transport/events.py:189-199
@dataclass
class SseSession:
    tenant_id: str
    run_id: str
    last_sequence: int = 0
    state_hash: str = ""
    authorized: bool = False
    principal_id: str | None = None
    resource_id: str | None = None
```

```text
ai-service/app/transport/events.py:232-242
def heartbeat(self) -> dict[str, Any]:
    if not self.authorized:
        return {"code": "SSE_AUTHORIZATION_REQUIRED"}
    return {
        "event_type": "HEARTBEAT",
        "run_id": self.run_id,
        "tenant_id": self.tenant_id,
        "sequence": self.last_sequence,
        "state_hash": self.state_hash,
        "replayable": False,
    }
```

Probe `SseSession(..., authorized=True)` trả metadata heartbeat dù chưa gọi `authorize()`. Sau khi authorize đúng, việc mutate `tenant_id`, `run_id`, `resource_id` trên object làm heartbeat trả `tenant-b`/`run-b`; không có revalidation hoặc immutable binding. Actor/resource equality trong `authorize()` vì vậy không bảo vệ được session state sau đó.

Đây là bypass metadata cross-tenant/cross-run ở transport primitive. Cần immutable authenticated state hoặc mọi output phải revalidate binding từ một context không thể mutate; không nhận `authorized` như public constructor input.

### Critical R3-003 — Raw mapping có extra top-level field và làm rò rỉ dữ liệu qua AG-UI

Evidence:

```text
ai-service/app/transport/events.py:148-153
def _event_mapping(event: EventEnvelope | Mapping[str, Any]) -> dict[str, Any] | None:
    if isinstance(event, EventEnvelope):
        return asdict(event)
    if isinstance(event, Mapping):
        return dict(event)
    return None
```

```text
ai-service/app/transport/events.py:181-186
mapped = _event_mapping(event)
if mapped is None or not isinstance(mapped.get("payload"), Mapping):
    return None
mapped["type"] = event_type
mapped["payload"] = _sanitize(mapped["payload"])
return mapped
```

`validate_scope()` chỉ bắt buộc các canonical keys; khi `resource_id=None`, raw dict có extra `resource_id` vẫn pass (`raw_extra_scope_none= True`). Probe mapper trả nguyên top-level `resource_id: 'd-other'` và `hidden_reasoning: 'LEAK'`; chỉ `payload` được sanitize. Một raw mapping malformed/extra field vì vậy có thể đưa sensitive top-level data ra AG-UI.

Cần reject unknown/top-level sensitive fields hoặc chuyển raw mapping qua schema canonical exact-key validation trước khi map; redaction phải áp dụng toàn bộ mapped envelope nếu raw mapping còn được hỗ trợ.

### Important R3-004 — Trusted Principal chỉ được kiểm tra bằng kiểu runtime; role lỗi không fail closed

Evidence:

```text
ai-service/app/security/policy.py:91-96
@dataclass(frozen=True)
class Principal:
    actor_id: str
    tenant_id: str
    role: str
```

```text
ai-service/app/security/policy.py:312-319
if not isinstance(request.principal, Principal):
    return self._decision(request, False, "UNTRUSTED_PRINCIPAL", "trusted principal binding is required")
...
if role != _normalise(request.principal.role):
    return self._decision(request, False, "ROLE_MISMATCH", "request role differs from principal role")
```

Probe `Principal('u1', 't1', 'admin')` tự dựng cùng `AuthzRequest` được authorize (`free_principal_admin= True`); không có provenance/issuer để phân biệt principal do auth boundary phát hành với object do caller tạo. Probe `role=None` gây `AttributeError` thay vì deny. `SseSession.authorize()` cũng gọi `principal.role.strip().lower()` tại `ai-service/app/transport/events.py:228` mà không kiểm tra kiểu.

Contract gọi là trusted Principal nhưng implementation mới enforce structural equality. Nếu helper được nối vào route mà route dựng Principal từ input không đáng tin, đây là privilege-escalation bypass; malformed role cũng tạo 500/DoS thay vì fail closed. Cần trusted factory/issuer hoặc authenticated context opaque, cùng normalization/type validation trước mọi method string.

### Important R3-005 — Readiness cho phép duplicate ID/category mâu thuẫn và boolean denominator

Evidence:

```text
ai-service/app/ops/readiness.py:31-36
def _positive(value: int | float | None) -> bool:
    return value is not None and value > 0
```

```text
ai-service/app/ops/readiness.py:300-314
supplied_by_id = {case.case_id.strip(): case for case in supplied_cases if case.case_id.strip()}
...
if _canonical(case.category) != expected_category:
    missing_required.append(f"{case_id} (category must be {expected_category})")
...
if not _positive(case.denominator):
    missing_required.append(f"{case_id} (positive denominator required)")
```

```text
ai-service/app/ops/readiness.py:326-342
for case in supplied_cases:
    ...
    passed = (not case.required or case.passed) and denominator_ok
    checks.append(...)
```

Probe với duplicate `chaos-restart` trong đó bản ghi đầu có category sai nhưng `passed=True, denominator=1`, bản ghi sau hợp lệ, trả `duplicate_wrong_category_pass= True`: dict comprehension bỏ qua category sai của bản ghi đầu và per-case check không kiểm tra category. Probe khác cho `denominator=True` cũng trả PASS vì `bool` là subclass của `int`.

Readiness có thể PASS với evidence mâu thuẫn hoặc denominator không phải sample count. Cần reject duplicate IDs trước map, validate category cho từng case, và chỉ chấp nhận số thực sự là `int|float` nhưng không phải `bool` (kèm policy rõ cho extra cases).

### Important R3-006 — Idempotency cache trả decision/audit của actor trước cho actor khác

Evidence:

```text
ai-service/app/security/policy.py:339-351
cache_key = (request.tenant_id, request.dossier_id, request.idempotency_key)
...
if prior is not None:
    prior_digest, prior_decision = prior
    if prior_digest != digest:
        return self._decision(request, False, "IDEMPOTENCY_CONFLICT", ...)
    return AuthorizationDecision(**{**prior_decision.__dict__, "cached": True})
```

Probe hai actor khác nhau cùng tenant/dossier/key và payload cho kết quả request thứ hai `cached=True`, nhưng `actor_id=owner-1`, `correlation_id=c1`, `audit_event.actor_id=owner-1`. Tenant/dossier isolation và digest conflict vẫn hoạt động, nhưng audit/authorization result không còn đại diện request hiện tại. Nếu quyết định được dùng trước side effect, retry khác actor đang thừa hưởng decision record của actor trước.

Cần đưa actor vào idempotency identity/digest nếu contract yêu cầu actor-bound command, hoặc dựng decision/audit mới cho caller hiện tại thay vì trả nguyên object cached. Nếu chủ ý idempotency chỉ scope tenant/dossier, vẫn phải sửa metadata attribution để không ghi audit sai actor.

## Những điểm round 2 đã xác nhận là đã sửa

- `SecurityPolicy` từ chối request/caller override ngoài constructor-bound tenant/dossier tại `ai-service/app/security/policy.py:302-329`.
- `AuthzRequest` không có Principal binding bị deny; role mismatch và read-only command đều có regression test.
- `map_to_agui()` đã yêu cầu expected tenant/run và canonical envelope cho typed event.
- `SseSession.authorize()` đã kiểm tra tenant, actor, run, resource và `stream.read` ở happy path; vấn đề R3 là state/constructor có thể forge hoặc mutate sau đó.
- Empty readiness cases hiện fail closed qua `REQUIRED_OPERATIONAL_CASES`; retention và references có test regression.
- Idempotency conflict khác digest, P3 replay/lease/sequence và cross-tenant store tests đều xanh.

## Verdict

**BLOCKED**. Còn 3 Critical và 3 Important findings có code evidence và runtime reproduction. `33 passed` focused và `87 passed` P0–P9 không loại bỏ được các input/trust-boundary paths mà test hiện tại chưa bao phủ. Không đủ điều kiện `PASS` hoặc `PASS_WITH_RISK` theo gate yêu cầu không còn Critical/Important.
