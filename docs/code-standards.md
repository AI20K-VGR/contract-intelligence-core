# Code Standards

> Trạng thái hiện tại được đối chiếu với codebase ngày 2026-09-24. Tài liệu này mô tả quy ước và boundary đã có trong mã nguồn; plan/research không được coi là implementation.

## Ngôn ngữ và layout

- `ai-service` và `backend` dùng Python `>=3.12`, FastAPI, Pydantic và pytest. Module Python dùng type hints và `from __future__ import annotations` khi phù hợp.
- `frontend` và consumer SDK dùng TypeScript/React. Wire shape dùng JSON Schema dưới `docs/contracts/`; `packages/contracts/src/index.ts` là consumer type, không thay thế runtime schema.
- AI2 runtime nằm ở `ai-service/app/`; test AI2 ở `ai-service/tests/`; deterministic/evaluation gates ở `evals/`.
- `ai-service/app/contracts/` giữ model/wire validation; `app/pipeline/` điều phối ingest, extraction, grounding và comparison; `app/reasoning/` xử lý query/state/HITL primitives; `app/tools/` giữ store/job persistence; `app/api/` là FastAPI boundary.
- `ai-service/src/contract_ocr/` là AI1/OCR-lab và serializer handoff. AI2 nhận JSON snapshot, không OCR hoặc sửa raw OCR trong reasoning.
- Backend hiện có health route và workspace placeholder trong `backend/src/contract_intelligence/`; không mô tả skeleton này là persistence/orchestrator production.

## Contract và dữ liệu

- Canonical AI1 input là `ai1.snapshot.v1`; `ai1.result.v0.1` và legacy `ocr.json` là compatibility lanes riêng. Adapter phải giữ raw source immutable và đặt output dẫn xuất ngoài raw snapshot.
- Package API hiện tại là `ai2.package.v1` với input profile `ai1.snapshot.v1/ocr-lab`. `process_payloads()` chỉ cho `relation_policy=INDEPENDENT`; `process_files()` và `process_payloads_full()` là full batch paths.
- Fact, relation, boundary và citation phải giữ provenance/evidence reference. Citation chỉ hợp lệ khi kiểm tra trong snapshot/page/table scope; thiếu hoặc mơ hồ chuyển thành review/insufficient/blocked, không thành fact chắc chắn.
- Không đưa `user_context` vào object mang evidence. Chỉnh annotation không làm stale evidence; chỉnh boundary/fact/relation làm stale generation và downstream artifact.
- Adapter chỉ chuyển đổi contract. Không tự suy luận body/annex hoặc legal winner khi không có evidence hay reviewer decision.

## Boundary P0–P9 hiện có

| Phase | Boundary đã có trong code | Trạng thái và giới hạn |
|---|---|---|
| P0 | Contract/idempotency baseline tests trong `ai-service/tests/test_p0_contract_baseline.py` | Test contract, không phải production TTL/retention policy. |
| P1 | `app/contracts/canonical.py`, `app/pipeline/canonical.py` | Projection deterministic/read-only, chưa là durable run store. |
| P2 | `app/reasoning/state_machine.py`, `hitl.py` | In-process/storage-agnostic reducer; chưa tự gắn persistence/route. |
| P3 | `app/tools/durable.py` | SQLite snapshot/checkpoint/event/outbox/audit/lease primitives; chưa chứng minh HA, queue, external exactly-once, scheduler, retention hoặc RTO/RPO. |
| P4 | `app/pipeline/execution.py`, `adk_adapter.py` | Current pipeline adapter; ADK chỉ là optional protocol không import `google.adk`; A2A/provider thật chưa có. |
| P5 | `app/security/policy.py`, `service_envelope.py` | Deny-by-default decision với trusted `Principal` binding, constructor-bound scope/role/action, redaction, actor-bound command idempotency, finite approval TTL và one-time consumed registry trong process, `ApprovalGrant` cho tool side effect và prompt-injection label; chưa tự enforce HTTP route. |
| P6 | `app/transport/events.py` | Canonical event/ordering, AG-UI mapping theo expected scope, read-only `SseSession` bind principal/run/resource với binding được normalize và immutable, heartbeat/cursor/state hash, A2UI allowlist; HTTP/SSE production route vẫn absent. |
| P7 | `evals/workflow_gate.py` | Deterministic scorer cho approved ground truth và workflow invariants; chưa phải load/soak runner. |
| P8 | `app/migration/canary.py`, `boundary.py` | Legacy/canary/canonical, parity, idempotency, publish guard, rollback primitives; chưa wire route/traffic/persistence migration. |
| P9 | `app/ops/readiness.py` | Fail-closed checker cho supplied findings/config/evidence; `passed`/`required` của operational case và các rollback flags phải là boolean thật; `PASS` không chứng minh deployment, HA, live traffic hoặc recovery thật. |

## Testing

- Offline gate dùng pytest với marker `not live` theo `ai-service/pyproject.toml`. Trên Windows, đặt `--basetemp` vào thư mục writable trong workspace nếu default pytest temp root bị `PermissionError`.
- Test kiểm tra invariant cụ thể: schema/semantic validation, source scope, citation, review state, idempotency, tenant isolation, state transition, command race, event ordering/replay, recovery boundary và authorization khi liên quan.
- Selector phase gồm `test_p0_contract_baseline.py` đến `test_p6_event_ui_convergence.py`, `test_p8_*.py`, `test_p9_production_readiness.py`; P7 dùng `evals/tests/test_p7_evaluation_gate.py`. Focused/regression tests không tự chứng minh production behavior.
- Evals phải tách `denominator`, `covered`, `passed` và nguồn ground truth. Candidate corpus không tự thành ground truth; chỉ record `approved=true`, có source và labels hợp lệ mới tính business accuracy.
- LLM judge, nếu có, chỉ advisory; không thay deterministic schema, security, citation, ordering, replay, idempotency hoặc migration gates.

## Error, retry, logging và security

- Input sai schema/semantic bị reject hoặc `BLOCKED`. Retry chỉ dùng cho lỗi retryable và bounded; cancellation, timeout, lease fencing, scope mismatch và side-effect chưa approved phải có error code ổn định.
- Phân biệt `SUCCEEDED` của job với `PASS` của evidence/review. `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE` và `BLOCKED` không được hạ thành success.
- Audit/log chỉ chứa actor, tenant, dossier, correlation, action, outcome và details đã redact. Redaction trong `app/security/policy.py`/`app/transport/events.py` là utility boundary; không phải bằng chứng mọi logger/route đã được kiểm soát.
- Không log/commit secret, provider key, HMAC secret, raw contract/PDF, hidden reasoning hoặc provider response chưa sanitize.
- `tenant_id`, `dossier_id`, actor, correlation, attempt, idempotency key và signed service envelope là scope bắt buộc trên Backend↔AI2 job boundary. `/jobs/{job_id}` kiểm tra envelope với stored owner scope.
- `SecurityPolicy` hỗ trợ `snapshot.read`, `replay.read`, `stream.read`, `hitl.command`; `read_only` không được command. `AuthzRequest` phải bind tới trusted `Principal`, trong đó actor/tenant/role phải khớp principal; policy phải bind tenant/dossier từ constructor và caller không được override scope. Unknown role/action/tool, cross-scope và command thiếu idempotency bị deny. Cache quyết định command dùng đúng tuple `(tenant_id, dossier_id, actor_id, idempotency_key)` và reject digest conflict; artifact `plans/260923-1023-ai2-long-running-architecture/artifacts/p5-api-security-contract.json` phải giữ cùng tuple.
- `ToolPolicy` cho read-only tool; side effect chỉ được phép với `ApprovalGrant` bind `approval_id`, tenant, dossier, actor, tool và command digest. Approval TTL phải là số hữu hạn, không âm; consumption one-time được kiểm tra và ghi atomically trong process-local registry. `approved=True` hoặc `approved_tools` không tự cấp quyền. Primitive này không phát hành hay lưu durable approval record/ledger; issuer và trusted approval store nằm ngoài module. Prompt-injection classifier chỉ gắn nhãn untrusted, không thực thi input. Các registry/cache in-process không phải nguồn sự thật cho nhiều worker/process.
- `validate_scope()` yêu cầu canonical event envelope đầy đủ; `map_to_agui()` bắt buộc expected tenant/run và resource khi có. `SseSession` chỉ authorize trusted principal có `stream.read` khi tenant, run và resource khớp; `principal_id`/`resource_id` được kiểm tra non-empty, normalize thành plain `str`, và session `frozen`/read-only; command phải qua HTTP boundary. `app/api/main.py` hiện không có HTTP/SSE production route cho các transport primitives này.
- `evaluate_readiness()` phải có đủ `REQUIRED_OPERATIONAL_CASES`; `passed` và `required` phải là `bool` thật, ba rollback flags cũng phải là `bool` thật; thiếu, sai category, failed hoặc thiếu positive denominator đều làm readiness fail-closed. `PASS` vẫn chỉ phản ánh supplied bounded evidence/configuration, không chứng minh deployment hay live recovery.

## Compatibility, migration và review

- Public schema/API/CLI change phải ghi before/after, caller bị ảnh hưởng, migration và rollback path. Không âm thầm phá `ai1.snapshot.v1` hoặc `be.ai2.processing.request.v1`.
- P8 chỉ là deterministic boundary: retry cùng payload trả record cũ, conflict bị reject, publish stale/unverified bị chặn, parity báo JSON paths và rollback chuyển legacy. Không gọi đây là cutover đã triển khai.
- Không reset hoặc giả định working tree sạch. Mỗi phase cần targeted gate, regression gate và artifact verification; report phải nêu command, kết quả, warning môi trường và limitation.
- Release không suy ra từ self-report hoặc readiness `PASS`; cần test/eval artifact, infrastructure evidence và human approval.
