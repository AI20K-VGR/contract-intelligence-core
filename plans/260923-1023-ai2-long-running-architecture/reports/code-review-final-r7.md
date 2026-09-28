# Code review final R7 — AI2 long-running architecture

## Verdict

`PASS`. Không còn Critical/Important finding chưa giải quyết trong source hiện tại. R7 là review-only: không sửa source/docs, không commit/push.

`in-place:true` — review trực tiếp trong phiên này theo yêu cầu hoàn tất ngay; không chạy thêm test sau khi người dùng xác nhận independent suite hiện tại `373 passed`.

## Phạm vi và bằng chứng

- Đọc lại các report R1–R6, source/call sites hiện tại trong `ai-service/app`, `ai-service/tests`, `ai-service/scripts`, `ai-service/src`, P0–P9 artifacts, `docs/system-architecture.md` và `docs/code-standards.md`.
- Preflight harness đã trả về scope `large`, risk `high_risk`, architecture route và rule `STD-REVIEW-COMMON-RG1-R2`. `hs-run review next` wrapper Windows vẫn lỗi encoding/PATH; đây là tooling issue, không phải source finding.
- Người dùng xác nhận independent suite hiện tại `373 passed`; theo chỉ dẫn R7 không chạy thêm test.

## R6 findings — đã đóng

### R6-001 — Redaction custom `str`/mapping key

Đã đóng. `ai-service/app/security/policy.py:73-100` chỉ nhận `type(key) is str`; key không phải plain `str` bị bỏ khỏi output trước khi value được copy. Sensitive plain keys đi qua `_is_sensitive_key()` và nhận `"[REDACTED]"`. Nested `Mapping`, `list`, `tuple` tiếp tục đi qua cùng redaction boundary.

Evidence:

```text
ai-service/app/security/policy.py:74-76
if type(key) is not str:
    return False
```

```text
ai-service/app/security/policy.py:94-98
if type(key) is not str:
    continue
safe[key] = "[REDACTED]" if _is_sensitive_key(key) else redact(
```

AG-UI sanitizer có cùng fail-closed behavior tại `ai-service/app/transport/events.py:184-194`.

### R6-002 — AG-UI exact top-level key allowlist

Đã đóng. `ai-service/app/transport/events.py:210-228` kiểm tra `type(key) is str`, membership exact trong allowlist, và `require_exact=True` yêu cầu đủ/đúng canonical key set trước mọi scope decision. `_event_mapping()` và `map_to_agui()` chỉ copy canonical keys; extra/non-plain key bị reject.

### R6-003 — Readiness malformed config/evidence

Đã đóng. `ai-service/app/ops/readiness.py:64-117` validate exact container/model/field types; `evaluate_readiness()` tại `:287-292` chuyển config, findings hoặc cases malformed thành `_malformed_result()` có `status="FAIL"`, `passed=False` và output deterministic. Các string method caller-controlled không còn được gọi sau khi type gate đã yêu cầu plain `str`.

### R6-004 — `AuthzRequest` payload sai kiểu

Đã đóng. `ai-service/app/security/policy.py:581-588` đặt `valid=False` khi payload khác `Mapping | None`; `SecurityPolicy.authorize()` tại `:626-628` trả `INVALID_CONTEXT` trước khi policy có thể authorize hoặc ghi idempotency decision.

## Prior findings R1–R5

Không tái hiện finding mới từ các nhóm đã review trước: tenant/dossier scope và principal binding; AG-UI/event scope; SSE tenant/run/resource/principal binding và read-only command boundary; finite TTL/numeric subclass; malformed idempotency identity; actor-bound idempotency; approval grant immutability/proof, exact command digest, expiry và one-time replay; readiness strict booleans, duplicate IDs, category mismatch và missing evidence. Các prototype limitations (chưa có HTTP/SSE production route, external auth/approval issuer, shared durable approval ledger, multi-worker replay/HA proof) vẫn được tài liệu hóa và không có production caller bypass trong source scan.

## Artifact drift — non-blocking, tách khỏi source defects

- `plans/260923-1023-ai2-long-running-architecture/artifacts/p5-api-security-contract.json:19` còn ghi `11 passed`, trong khi verification hiện tại được người dùng xác nhận là `373 passed` tổng suite.
- `plans/260923-1023-ai2-long-running-architecture/artifacts/p6-event-ui-convergence.json:21-23` còn số liệu `3 passed`/`55 passed` cũ.
- `plans/260923-1023-ai2-long-running-architecture/artifacts/p9-production-readiness.json:21-23` còn số liệu `7 passed`/`68 passed` cũ.

Đây là drift của verification artifacts, không phải defect trong source và không làm thay đổi verdict R7; nên refresh artifacts ở vòng tài liệu/verification riêng.

## Final decision

`PASS` — không còn Critical/Important finding chưa giải quyết; artifact drift được ghi nhận riêng là non-blocking. Architecture review đã kiểm tra và được stamp trong canonical decision.
