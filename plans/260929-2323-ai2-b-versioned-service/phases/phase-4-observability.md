---
phase: 4
title: "Observability"
status: pending
plan: 260929-2323-ai2-b-versioned-service
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 4 — Observability

## Overview
Thêm quan sát vận hành AI2 mà không ghi nội dung hợp đồng: JSON logs theo allow-list, Prometheus `/metrics` với nhãn hữu hạn, OTel spans tùy chọn, chi phí theo lượt từ pricing A. Xử lý log Kafka thô, thêm runbook và phát rc.2. Phụ thuộc P2 guard/call outcomes và P3 image/release workflow.

## Requirements
- Logs JSON (hoặc text theo cấu hình) chỉ có request id, route template, status/outcome, latency, counts/token/cost khi có; bỏ `exc_info`/exception message ở output công khai. Không log prompt, completion, snapshot, raw Kafka message, tenant/user IDs, keys hay provider response.
- `/metrics` có khoảng 10 metric tên cố định, nhãn chỉ route template, outcome enum, model allow-list; không có id/hash/query/tenant. Metrics bật/tắt qua env; không thêm Prometheus server/collector vào compose (VD-B8).
- OTel no-op khi endpoint không cấu hình; spans `ai2.request`, L0-L3, `ai2.llm.call` với duration/status/token/cost và `gen_ai.*` semantic attrs đã allow-list; không export input/output. Không sửa Backend trace propagation.
- Giá dùng `evals/live/pricing.json` của A; lookup model/snapshot đã pin, unknown price → `null` và metric counter; không gọi giá từ mạng.
- Sửa Kafka log nguyên message; có canary test xuyên stdout/stderr/caplog và `/metrics`. Bật tracing/logging không thay đổi response/reasoning.
- Phát rc.2 chỉ sau live HC-B1c, evidence, workflow và attestation; cuối phase tạo `review-decision.json` cho stage policy.

## Related Code Files
**Create**
- `ai-service/app/observability/logging.py`, `ai-service/app/observability/metrics.py`, `ai-service/app/observability/tracing.py`
- `ai-service/tests/test_observability_logging.py`, `ai-service/tests/test_observability_metrics.py`, `ai-service/tests/test_observability_tracing.py`
- `docs/ai2/AI2-18-observability.vi.md`

**Modify**
- `ai-service/app/api/main.py`, `ai-service/app/transport/kafka_idp_worker.py`, `ai-service/app/llm/client.py`, `ai-service/app/llm/guard.py`, `ai-service/pyproject.toml`, `ai-service/uv.lock`, `docker-compose.yml`, `ai-service/.env.example`, `ai-service/README.md`, `docs/ai2/AI2-17-release-runbook.vi.md`

**Delete:** không có.

## Implementation Steps
1. Preflight P1–P3 and A pricing; inspect locked package API/versions, all log statements that can carry provider or Kafka content, existing middleware order and app lifespan. Record anchors and dependency versions in `verification-P4.json`.
2. RED canary tests for both contract text `CANARY-HD-7f3a` and secret marker `sk-test-CANARY`, through normal request failure and Kafka logging; assert absent from captured logs, stderr and `/metrics`.
3. Implement allow-list JSON formatter and request context correlation; replace raw Kafka `%r` with bounded metadata (message type/size/outcome) and sanitized exception codes. Verify exceptions remain available only in local debugging where policy allows.
4. Define the bounded metric catalog (about 10 families); route labels use route templates, outcomes are fixed enums, model values allow-listed. Add `/metrics` gated endpoint with no user-controlled labels.
5. Add OTel SDK/provider/instrumentation dependencies pinned to supported range; no endpoint means no-op/no exporter. Add spans at request, L0-L3 and guard/provider calls; record `gen_ai.*` counts/status/cost only, redact content and identifiers.
6. Read pricing data offline from A and compute per-call cost; unknown model/price remains `null` with bounded outcome. Tests prove accounting does not alter call budget or trigger network access.
7. Update docs and env/compose defaults; run full offline suites and A regression gate. HC-B1c live benchmark requires explicit human confirmation and `--max-usd 5`; update P3 evidence/runbook and publish rc.2 only after gate/review.
8. Create `review-decision.json` with review scope/findings/disposition for the phase; update release evidence and `verification-P4.json`. Never produce GA; C owns GA after threshold PASS.

## TDD
### Tests-before (RED)
- `test_observability_logging.py`: JSON allow-list, secret/prompt/canary redaction; exception strings excluded; request correlation survives errors.
- `test_observability_metrics.py`: exact registered metric families, finite label sets, no user-controlled values; disabled route behavior.
- `test_observability_tracing.py`: no configured endpoint produces zero exports; in-memory exporter has required spans and zero content attributes; SDK errors fail safe.
- Extend `test_llm_query_integration.py` for token/cost/error accounting and unknown-price `null`.

### Tests-after / Gate
- Run canary across 4 paths × 2 markers; 0 leaks in captured stdout/stderr/caplog and metrics.
- `/metrics` exposes only declared family names and finite labels; OTel no endpoint exports 0 spans, in-memory exporter includes L0-L3 + `ai2.llm.call` without content attributes.
- AI2/Backend/evals offline gates, lint/type check and P3 image hygiene pass; dependency lock reproducible with frozen sync.
- HC-B1c live evidence and HC-B4 rc.2 publish/attestation checks are human-controlled and recorded; code review artifact emitted.

## File inventory

| Action | Files | Approx. size / impact |
|---|---|---|
| Create | 3 observability modules, 3 tests, operations guide | 7 files; logging/metrics/tracing contracts |
| Modify | API/Kafka/provider/guard, dependency lock, compose/env/docs | 10 files; runtime initialization and release operations |

## Test scenario matrix

| Severity | Scenario | Expected check |
|---|---|---|
| Critical | Prompt, contract, secret or provider error reaches logging/metrics | both canaries absent in all captured sinks |
| Critical | Kafka message contains customer snapshot | only bounded type/size/outcome logged |
| High | User-controlled labels cause cardinality growth | labels constrained to explicit finite sets |
| High | OTLP endpoint absent or exporter fails | no-op/fail-safe; query response unaffected |
| High | Pricing model absent/stale | cost is null; no network lookup or false cost |
| Medium | Concurrent request correlation | request-scoped ids/spans do not cross requests |

## Dependency map
- **Upstream:** P2 `LlmCallGuard`, outcomes/token usage; P3 `/version`, GHCR workflow and release runbook; A `pricing.json`.
- **Downstream:** C consumes observability signals but does not require collector infrastructure; GA evidence remains owned by C.
- **Human gates:** HC-B1c allows live benchmark; HC-B4 controls rc.2 tag/deploy.

## Success Criteria
- [ ] 0/8 canary leaks across log sinks and metrics.
- [ ] Metrics contain the declared ~10 series and finite labels only; no collector stack is added.
- [ ] OTel absent endpoint exports zero; in-memory trace includes required spans and no content attributes.
- [ ] Pricing reports per-call cost or null for all observed LLM calls without extra egress.
- [ ] Kafka raw-message logging removed; offline suites, A gate, lint/type and frozen dependency sync pass.
- [ ] `verification-P4.json` and `review-decision.json` exist; rc.2 evidence verified if publish gates were met; no GA tag.

## Risks

| Risk | Likelihood × impact | Mitigation |
|---|---|---|
| Exception/Kafka formatter leaks raw content | Medium × Critical | allow-list formatter; marker tests across sinks; never attach exception text |
| Metric labels create unbounded cardinality | Low × High | route templates and fixed enums; assert sets in tests |
| OTel SDK setup changes startup or adds egress | Medium × High | no-op absent endpoint; lazy exporter setup; no network test; feature flag |
| Dependency lock conflicts with current AI2 extras | Medium × Medium | pin compatible ranges, frozen sync and full offline regression before rc.2 |
