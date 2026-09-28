# Báo cáo docs manager final R6

Ngày kiểm tra: `2026-09-24`

## Phạm vi

Audit current-state sau R6/R7 cho:

- `docs/code-standards.md`
- `docs/system-architecture.md`
- report này

Không sửa source, tests, plan hoặc artifacts; không commit/push.

## Nội dung đã đối chiếu

- Redaction chỉ giữ mapping key có `type(key) is str`; non-plain key bị bỏ. Sensitive plain key được nhận diện theo các nhóm `raw_contract`, `hidden_reasoning`, `prompt`, `secret`, `token` và nhận `"[REDACTED]`; quy tắc áp dụng đệ quy qua mapping/list/tuple tại `ai-service/app/security/policy.py:73-107` và `ai-service/app/transport/events.py:184-199`.
- AG-UI dùng exact canonical envelope allowlist gồm `event_id`, `run_id`, `tenant_id`, `sequence`, `state_version`, `state_hash`, `event_type`, `schema_version`, `correlation_id`, `payload`, `replayable`; expected resource thì thêm đúng `resource_id`. Key thiếu, thừa hoặc không phải plain `str` bị reject tại `ai-service/app/transport/events.py:43-48`, `ai-service/app/transport/events.py:210-228`.
- `map_to_agui()` chỉ map event sau scope/allowlist validation, sanitize payload và thêm `type` tại `ai-service/app/transport/events.py:231-276`.
- Readiness validate strict config/evidence shape; malformed config, findings hoặc cases trả deterministic `status="FAIL"`, `passed=False`, check `malformed_input` tại `ai-service/app/ops/readiness.py:64-140` và `ai-service/app/ops/readiness.py:274-292`. Numeric readiness phải finite; boolean phải là `bool` thật; case/category/denominator phải hợp lệ tại `ai-service/app/ops/readiness.py:35-57`, `ai-service/app/ops/readiness.py:409-529`.
- `AuthzRequest.payload` chỉ nhận `Mapping | None`; payload sai kiểu làm request invalid và `SecurityPolicy.authorize()` trả `INVALID_CONTEXT` trước policy/idempotency tại `ai-service/app/security/policy.py:566-588` và `ai-service/app/security/policy.py:620-638`.
- Command idempotency gắn actor trong tuple `(tenant_id, dossier_id, actor_id, idempotency_key)` và reject digest conflict tại `ai-service/app/security/policy.py:665-688`.
- `Principal` và `ApprovalGrant` là opaque immutable prototype contracts; direct construction bị chặn. `Principal` dùng prototype issuer seam; approval consumption là process-local/non-durable, còn external verified identity issuer và durable approval ledger chưa có tại `ai-service/app/security/policy.py:126-179`, `ai-service/app/security/policy.py:201-217`, `ai-service/app/security/policy.py:284-332`, `ai-service/app/security/policy.py:355-362`.
- `SseSession` là read-only frozen prototype state, yêu cầu trusted principal và tenant/run/resource binding; command bị từ chối và phải đi qua HTTP tại `ai-service/app/transport/events.py:279-379`. Source route inventory trong `ai-service/app/api/main.py` không có HTTP/SSE route nối các P5/P6 primitives; các route hiện hữu kết thúc ở workspace/job HTTP boundary.

## Checks

- Đã đọc `CLAUDE.md`, `harness/rules/documentation-management.md`, hai docs mục tiêu và source P5/P6/P9 liên quan.
- Đã kiểm tra claims theo source hiện tại; không dùng theory claim hoặc phase artifact làm bằng chứng wiring.
- Docs/report dùng UTF-8; các evidence token (`file:line`, identifier, status và key names) được giữ nguyên.
- Đây là docs-only audit; không chạy lại test suite.
