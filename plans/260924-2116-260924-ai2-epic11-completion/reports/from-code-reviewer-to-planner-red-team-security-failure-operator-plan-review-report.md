# Red-team report — EPIC-11 AI2 completion plan

Ngày: 2026-09-24
Personas: Security Adversary, Failure Mode Analyst, Maintainer 6-months-later, Bad-day Operator
Verdict: CONDITIONAL PASS — plan có hướng đúng nhưng phải giữ các mitigation dưới đây trong phase acceptance trước khi approve.

## Findings

| ID | Sev | Failure scenario | Evidence | Suggested fix |
|---|---|---|---|---|
| RT-01 | C | Backend tiếp tục gọi `/process` hoặc `/query` metadata-only nên integration “xanh” nhưng không có evidence để grounding. | `backend/src/contract_intelligence/infrastructure/ai_adapters.py:262,294`; `ai-service/app/api/main.py:622,669` | Phase 5 thêm route-selection test assert canonical `/jobs/idp` và query context; legacy lane phải fail-closed và có deprecation marker. |
| RT-02 | C | Snapshot digest đúng nhưng evidence projection thuộc tenant/dossier khác, dẫn đến cross-tenant retrieval hoặc citation leak. | `ai-service/app/reasoning/vector_recall.py:169`; plan phase 4 yêu cầu projection theo digest nhưng chưa bắt buộc composite scope key trong acceptance. | Bắt buộc key `(tenant_id, dossier_id, snapshot_digest)` và negative test cross-tenant/cross-dossier trước retrieval, không chỉ sau grounding. |
| RT-03 | H | Projection stale sau reprocess; query trả `ANSWERED` trên snapshot cũ. | `backend/src/contract_intelligence/shared/ai/persistence.py:659`; phase 4 risk đã nêu stale nhưng cần test transition. | Thêm test process v1 → process v2 → query v1 phải `INSUFFICIENT_EVIDENCE`; lưu snapshot digest trong QueryTrace/result. |
| RT-04 | H | `IndexContribution` được persist nhưng một code path vẫn đổi active pointer hoặc reviewer gate bị bypass bởi retry. | `ai-service/app/pipeline/index.py:6`; plan acceptance chỉ nói active pointer không đổi. | Thêm invariant test sau mọi retry/duplicate result: active pointer giữ nguyên và contribution state chỉ `propose`; Backend publish là command riêng có authorization. |
| RT-05 | H | Fixture source thiếu khiến targeted tests pass bằng subset nhưng full suite bị bỏ qua, tạo false confidence. | Probe pytest: imports `fixtures.catalog`/`fixtures.eval_suite` fail; `ai-service/fixtures` không có các source module tương ứng. | Phase 1 phải có artifact fixture inventory + owner/action; phase 5 cấm PASS nếu full suite chưa chạy hoặc blocker chưa được mentor chấp nhận. |
| RT-06 | M | `ai1.snapshot.v1` và legacy `ai1.snapshot.v3` tiếp tục được gọi “canonical” ở tài liệu khác nhau, gây contract drift sau khi ship. | `docs/DOC-04-architecture.md:96`; `docs/DOC-05c-backend-ai-service-contract.md:351`; `ai-service/app/contracts/wire.py:53` | Phase 1 cập nhật compatibility table và contract test; plan human gate bắt buộc mentor xác nhận version trước cook. |

## Disposition

- RT-01: Accept — đã đưa vào phase 5 requirements/steps và acceptance.
- RT-02: Accept — bổ sung composite scope key và negative test vào phase 4.
- RT-03: Accept — bổ sung stale transition test vào phase 4/5 gate.
- RT-04: Accept — bổ sung retry invariant vào phase 3 và phase 5 integration test.
- RT-05: Accept — phase 1 blocker là hard prerequisite; phase 5 không claim full PASS nếu chưa giải quyết.
- RT-06: Accept — đã ghi canonical decision/migration gate trong plan và phase 1.

## Rejected findings

Không có.
