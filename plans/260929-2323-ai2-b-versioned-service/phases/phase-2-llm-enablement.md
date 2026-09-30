---
phase: 2
title: "Llm Enablement"
status: pending
plan: 260929-2323-ai2-b-versioned-service
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 2 — Llm Enablement

## Overview
Nối LLM vào `/query` có kiểm soát theo hai lớp: Backend quyết định egress từ cấu hình máy chủ; AI2 áp kill switch, tenant allowlist, deadline tường-clock, circuit breaker, số lời gọi tối đa và giới hạn in-flight. Mọi lỗi provider chuyển về câu trả lời tất định, fail-closed. Phụ thuộc P1 vì dùng builder `ai2.query.v1` và trường LLM đã định nghĩa ở đó; hoàn tất trước P3/P4.

## Requirements
- Sửa bypass `body.policy_flags` của Backend trước khi nối LLM; client không thể bật egress. Quét đủ sáu site Backend nêu trong PB-B5, kiểm thử site nào thuộc lane query và giữ Kafka/processing không bật LLM ngoài chính sách đã chốt.
- Thêm `AI2_QUERY_EGRESS_ALLOWED=false` cùng `AI2_QUERY_USE_LLM=false` và server-owned helper tạo query flags. Phía AI2, `AI2_LLM_ENABLED=false`, `AI2_LLM_EGRESS_TENANTS` mặc định rỗng; từ chối thiếu cấu hình, tenant ngoài danh sách và workspace/demo theo VD-B5.
- `LlmCallGuard`: deadline monotonic tổng 12 giây mặc định, tối đa 2 logical calls, breaker có half-open hữu hạn, semaphore in-flight 4. SDK retries bằng 0; retry/fallback `response_format` chỉ theo lỗi tương thích đã phân loại, không gọi lại cho auth/timeout. Permit gắn với future/provider call và chỉ nhả khi future thực sự hoàn tất, không nhả khi caller timeout; executor có tối đa 4 worker và không nhận backlog ngoài semaphore. Nếu provider call treo vĩnh viễn, guard giữ slot, trả `SATURATED` cho call mới và runbook yêu cầu recycle AI2 worker/process để giải phóng; tuyệt đối không giả định thread bị huỷ bởi timeout. Khi hết budget/breaker/mất provider, trả mã lỗi đã chốt và state review/evidence tất định.
- Nối `/query` qua `resolve_llm` và `QueryRouter`; không đưa vector/embedding vào budget LLM. Phân biệt `llm_called` với `llm_answer_used`; không trả câu trả lời chưa được grounding.
- P2 có 4 commit logic: (2a) Backend policy; (2b) guard/client/config; (2c) L2/stack/query/API; (2d) benchmark tay, VD-B3 và mặc định cuối.

## Related Code Files
**Create**
- `ai-service/app/llm/guard.py`, `ai-service/app/llm/settings.py`, `ai-service/tests/test_llm_guard.py`, `ai-service/tests/test_llm_query_integration.py`
- `backend/src/contract_intelligence/shared/ai/egress_policy.py`, `backend/tests/unit/test_ai2_query_egress_policy.py`

**Modify**
- `backend/src/contract_intelligence/api/v1/dossiers.py`, `backend/src/contract_intelligence/config/settings.py`, `backend/src/contract_intelligence/schemas/queries.py`, `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py`, `backend/src/contract_intelligence/shared/ai/canonical_processing.py`, `backend/src/contract_intelligence/infrastructure/ai_adapters.py`, `backend/src/contract_intelligence/api/v1/webhooks.py`
- `backend/tests/unit/test_query_state_passthrough.py`, `backend/tests/unit/test_contract_router.py`, `backend/tests/unit/test_ai_adapters.py`, `backend/tests/unit/test_dossiers_query.py`
- `ai-service/app/api/main.py`, `ai-service/app/llm/client.py`, `ai-service/app/pipeline/runtime.py`, `ai-service/app/reasoning/l2_plan.py`, `ai-service/app/reasoning/stack.py`, `ai-service/app/reasoning/query.py`, `ai-service/app/reasoning/orchestrator.py`, `ai-service/.env.example`, `docker-compose.yml`
- `ai-service/tests/test_query_fallback_state.py`, `ai-service/tests/test_llm.py`, `ai-service/tests/test_llm_guardrails.py`, `ai-service/tests/test_processing_runtime.py`
- `evals/tests/test_live_benchmark.py` (chỉ nếu cần additive instrumentation cho phép đo; giữ nguyên hành vi baseline A)

**Delete:** không có.

> Tập file là dự kiến có chủ ý theo scope-size 27 file; ở bước 0 cook phải grep lại caller/anchor và không tự mở rộng danh sách. Nếu cần file khác, cập nhật plan và graph trước khi code.

## Implementation Steps
1. Preflight A/P1 và đọc `docs/code-standards.md`, `docs/system-architecture.md`; xác minh các 6 site egress, client `BudgetedClient`/pricing A, `complete_json` call sites, tuổi thọ client/breaker. Ghi anchor thực tế vào `verification-P2.json`.
2. (2a RED) Test rằng request client `egress_allowed/use_llm=true` không đổi server policy; bao phủ route query, `/search`, canonical processing, webhook, Kafka adapter và default schema. Sửa Backend policy/settings trước khi bật AI2; xác nhận Kafka vẫn `max_llm_calls=0`.
3. (2b RED) Server giả OpenAI trên `127.0.0.1:0`: success, trickle, silent timeout, connection, 401/403/400/429/500, JSON hỏng, `response_format` không hỗ trợ, breaker open/half-open, saturation và concurrent calls. Có test block provider qua caller deadline: không vượt 4 call đang chạy, permit không được tái dùng trước khi future xong, permit trở lại sau khi server nhả; tình huống không nhả phải chứng minh fail-closed `SATURATED` và runbook recycle. Implement settings, guard, phân loại lỗi SDK thật, 0 SDK retries, ContextVar deadline reset `finally`; không ghi prompt/response.
4. (2c RED) Kiểm `resolve_llm` hai kill-switch, allowlist tenant, không khởi tạo client khi bị chặn; test L2 provider exception và fallback tất định. Nối guard qua runtime/reasoner/router `/query`; mọi nhánh đi qua builder P1 và phân biệt `llm_called`/`llm_answer_used`.
5. Chạy ma trận 10/10 ở plan.md; deadline kiểm với 2 giây trong test và response ≤ deadline + 1 giây. Kiểm đếm số request upstream, mã lỗi, state/citation, và 0 exception thoát route.
6. (2d, human gate HC-B1a) Chạy benchmark live có opt-in rõ ràng, dữ liệu giả lập, `--max-usd 5`; nếu exit không 0 hoặc tripwire mới FAIL thì dừng. Dùng n≥60/UNDERPOWERED cùng quy tắc VD-B3 để chốt deadline/calls; cập nhật `.env.example`, compose, `/version` target P3 và Validation Log. Không tự chạy benchmark live khi chưa có xác nhận HC-B1a.
7. Regression: AI2 offline, Backend unit + mypy/ruff, eval offline gate A; ghi cả kết quả và lệnh thực tế. Không sửa baseline A để làm gate xanh.

## TDD
### Tests-before (RED)
- `test_ai2_query_egress_policy.py`: client flags bị bỏ qua; cấu hình default deny; từng caller query dùng policy từ settings.
- `test_llm_guard.py`: deadline wall-clock qua trickle; max calls; semaphore; future sống qua caller timeout không nhả permit sớm; capacity hồi phục khi future kết thúc; stuck call fail-closed; breaker states; reset context; phân loại 401/429/5xx/timeout/JSON lỗi; 0 retry tự động; fallback format chỉ ở lỗi format-specific.
- `test_llm_query_integration.py`: tenant allowlist và kill switch; no-client/no-call khi bị chặn; thành công grounded; LLM fail → review tất định; `llm_called` khác `llm_answer_used`; tổng latency.
- Regression P1 `test_versioned_contracts.py` giữ nguyên schema/query contract; gate A tripwire không tăng.

### Tests-after / Gate
- Test server giả 10/10 tình huống theo acceptance plan.md; mỗi request ≤ deadline test + 1 giây và assertion số lần gọi chính xác.
- AI2 offline suite; Backend `uv run pytest tests/unit -q -p no:cacheprovider`, `ruff check src/ tests/`, mypy không thêm lỗi; eval offline; Ruff AI2/evals.
- Live HC-B1a chỉ sau xác nhận người dùng: `run_live_benchmark.py --k 3 --max-usd 5 --load-dotenv --fail-on-threshold --tripwire-only`; 0 tripwire regression; ghi n, p95/CI, deadline exceeded, USD và verdict VD-B3.

## File inventory

| Action | File groups | Approx. size / test impact |
|---|---|---|
| Create | 2 guard/policy modules, 4 focused test modules | ~700 LOC; new unit + integration tests |
| Modify | Backend policy and six caller/schema/settings modules | 7 production + 4 test files; egress invariant |
| Modify | AI2 main/client/runtime/L2/stack/query/orchestrator/config/compose | 10 files; response semantics, budget, query wiring |
| Modify | AI2 existing tests and A live benchmark test (additive only) | 5 files; prevent regression / capture `used_llm` metrics |

## Test scenario matrix

| Severity | Scenario | Expected check |
|---|---|---|
| Critical | Client forges egress flags or tenant not allowlisted | Backend policy wins; AI2 makes 0 provider calls |
| Critical | Trickle provider exceeds wall-clock budget | Route returns by deadline + 1 s; worker call count bounded |
| Critical | LLM output unsupported/unverified or provider errors | deterministic review/evidence response; no exception or fabricated answer |
| High | Repeated provider failure opens breaker | calls stop; bounded half-open probe only |
| High | Concurrent requests exhaust in-flight slots | excess requests fail closed with `SATURATED` |
| High | SDK response-format incompatibility | at most 2 logical calls; no retry for auth/timeouts |
| Medium | `llm_called` versus used answer | correct flags and query schema for every branch |
| Medium | L0/L1-only and Kafka/processing lanes | unchanged behavior and no unintended LLM egress |

## Dependency map
- **Upstream:** P1 contract builder/schema; A live benchmark + pricing; Backend settings and query adapter.
- **Downstream:** P3 exposes final LLM config in `/version`; P4 instruments guard outcome/call counts and uses bounded error codes.
- **Human gate:** HC-B1a blocks live benchmark and final numeric tuning, not offline development.

## Success Criteria
- [ ] Forged client policy cannot enable egress; all query policy defaults deny; Kafka lane remains disabled by test.
- [ ] 10/10 provider matrix passes; 0 unhandled provider exceptions; call count and response time satisfy plan acceptance.
- [ ] Kill switch and tenant allowlist each demonstrate zero provider calls when denying.
- [ ] `llm_called` and `llm_answer_used` are accurate; failed/ungrounded LLM output never becomes an answered state.
- [ ] Offline suites, A gate, Ruff and Backend type-check meet plan thresholds.
- [ ] `verification-P2.json` contains OBSERVED results; VD-B3 numeric decision is recorded only after HC-B1a, with sample count and underpowered status.

## Risks

| Risk | Likelihood × impact | Mitigation |
|---|---|---|
| Backend egress bypass remains when AI2 LLM is enabled | Medium × Critical | commit 2a before 2c; test every inventoried path; AI2 kill switch/tenant allowlist is second layer |
| SDK timeout still permits trickle to exceed caller budget | Medium × Critical | monotonic wall-clock guard + trickle test, do not trust per-phase timeout |
| Abandoned worker threads continue consuming calls | Medium × High | bounded executor/semaphore, no enqueue after deadline; document in-flight lifetime |
| Live sample too small to tune a reliable percentile | High × Medium | n<60 marked UNDERPOWERED; retain conservative default and defer GA tuning |
