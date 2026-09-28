---
id: 260923-1023-ai2-long-running-architecture
title: "AI2 long-running reasoning và live review"
status: completed
mode: hard
tdd: true
branch: TBD
created: 2026-09-23
author: user:dungskbg2004@gmail.com
decisions: []
phases:
  - phases/phase-0-contract-baseline.md
  - phases/phase-1-canonical-model.md
  - phases/phase-2-hitl-state.md
  - phases/phase-3-persistence-events.md
  - phases/phase-4-execution-adapters.md
  - phases/phase-5-api-security.md
  - phases/phase-6-agui-sse.md
  - phases/phase-7-evaluation.md
  - phases/phase-8-migration.md
  - phases/phase-9-hardening.md
harness_version: 6.3.0
harness_schema_version: 1.0
---

# Implementation plan — AI2 long-running reasoning và live review

Ngày: 2026-09-23  
Chế độ: `hs:plan --hard --deep --tdd`  
Trạng thái: **Completed — implementation, verification và review gates đã hoàn tất**  
Phạm vi: AI2; không sửa AI1 OCR trong plan này.

## 0. Evidence và guardrails

Plan dựa trên:

- [current-state-ai2-audit.md](../reports/ai2-architecture-research-20260923/current-state-ai2-audit.md);
- Track A–D research, glossary/source matrix, critique, scenario và evaluation strategy trong `plans/reports/ai2-architecture-research-20260923-v2/`;
- codebase hiện tại: `ai-service/app/api/main.py`, `ai-service/app/pipeline/idp.py`, `ai-service/app/pipeline/ai1_snapshot_adapter.py`, `ai-service/app/tools/jobs.py`, `ai-service/app/tools/persist.py`, `ai-service/app/pipeline/units.py`, `ai-service/app/pipeline/runtime.py`, `packages/typescript/frontend-sdk/src/index.ts`, `frontend/src/app/App.tsx`.

Không coi AG-UI/A2UI/ADK/A2A/SSE/WebSocket là durable state. Không viết production code trước khi plan được duyệt. Mọi phase đều TDD: test contract/state trước implementation, test failure trước happy path, verification artifact sau mỗi phase.

## 1. Dependency graph

```text
P0 decisions/contracts
  -> P1 canonical model + segmentation
  -> P2 state machine + HITL commands
  -> P3 durable persistence/event/replay
  -> P4 execution adapters (current pipeline, ADK optional, A2A deferred)
  -> P5 API/security/observability
  -> P6 AG-UI + fixed FE + hybrid HTTP/SSE
  -> P7 evaluation/regression/recovery/load
  -> P8 migration/canary/cutover
  -> P9 hardening/rollback/operational acceptance
```

P6 không được bắt đầu trước khi P3 có snapshot/replay và P5 có authorization. P4 không được làm A2A production trước human decision. P8 không được chạy nếu P7 không đạt gates.

## 2. Phase plan

### P0 — Freeze decisions, compatibility và contract test baseline

**Mục tiêu**

- Chốt domain ownership, phase-1 reviewer policy, TTL, auth/tenant, event retention, SSE provisional decision và A2A/A2UI feature policy.
- Bảo vệ contract AI1→AI2 hiện tại (`ai1.snapshot.v1`, `ocr.json` adapter) bằng golden/contract baseline.

**File/module dự kiến thay đổi**

- Tạo contract artifacts dưới `plans/.../artifacts/` và sau approval mới cập nhật schema/constants tương ứng.
- Test locations hiện có dưới `ai-service/tests/`, `evals/`.
- Không đổi AI1 producer.

**Contract**

- Input envelope giữ document/evidence refs hiện tại; thêm versioned wrapper không làm mất field cũ.
- Compatibility mode phải parse current `ocr.json` và historical compatibility nếu code đang hỗ trợ.
- Unknown fields: policy rõ (preserve/ignore/reject) trước implementation.

**Acceptance criteria**

- Có decision record được duyệt cho 8 architectural areas.
- Existing AI1 contract tests pass unchanged.
- Mapping known/unknown/missing fields và no-evidence behavior được viết thành executable contract cases.

**TDD/test cases**

- current `ocr.json` parse;
- missing citation/document ref;
- multiple logical documents in one JSON;
- unsupported schema version;
- duplicate input submission/idempotent run creation.

**Verification artifact**

- `artifacts/p0-contract-baseline.json` và approved decision record.

**Risk / rollback**

- Risk: contract giả định sai vì sample ít. Rollback: không thay schema, giữ adapter cũ và đánh dấu field provisional.

**Dependency**

- None; là gate bắt buộc cho P1–P9.

---

### P1 — Canonical AI2 domain model, segmentation và evidence graph

**Mục tiêu**

- Model hóa `AI2Run`, input snapshot, logical document, boundary, document role, party, clause, fact, relation, citation, generation, dependency và quality flag.
- Xử lý một JSON chứa hợp đồng/phụ lục chưa được AI1 tách: proposal + ambiguity + reviewer gate.

**File/module dự kiến thay đổi**

- `ai-service/app/pipeline/ai1_snapshot_adapter.py` (canonical input mapping).
- `ai-service/app/pipeline/contract_context.py`, `ai-service/app/reasoning/relations.py`, `ai-service/app/pipeline/idp.py`.
- Tạo domain/schema modules và test fixtures; chưa thay public output nếu chưa có compatibility mapper.

**Contract**

- Mọi fact/relation có `evidence_refs`; thiếu evidence phải là `UNVERIFIABLE`/`INSUFFICIENT_EVIDENCE`.
- Boundary có version, confidence, status (`PROPOSED`, `CONFIRMED`, `AMBIGUOUS`, `REJECTED`).
- Generation gắn với input snapshot + segmentation version + state version.
- User context không được serialize thành evidence.

**Acceptance criteria**

- One JSON/many logical documents được biểu diễn không làm mất raw source.
- Body/annex relation chỉ được confirmed khi evidence hoặc reviewer decision đủ.
- Dependency graph xác định stale artifacts sau boundary/fact/relation edit.

**TDD/test cases**

- segmentation proposal với page/block/table refs;
- low confidence/missing refs;
- body-annex explicit/ambiguous/missing;
- bilingual/gov-language;
- table continuation/truncated clause;
- fact/relation citation mismatch;
- edit annotation không ảnh hưởng evidence vs edit boundary làm stale.

**Verification artifact**

- `artifacts/p1-domain-schema.json`, schema conformance report, stale dependency fixture report.

**Risk / rollback**

- Risk: canonical model quá rộng/đụng output hiện tại. Rollback: mapper read-only + compatibility projection; không đổi legacy output.

**Dependency**

- P0.

---

### P2 — Durable reasoning state machine và HITL command model

**Mục tiêu**

- Implement sau approval state reducer: `CREATED → RUNNING → WAITING_FOR_HUMAN → RESUMING/RECOMPUTING → COMPLETED/FAILED/CANCELLED/EXPIRED`.
- Phân biệt review, approval, intervention; hỗ trợ context request, approve/reject/edit/confirm-impact/resume/cancel.

**File/module dự kiến thay đổi**

- Tạo domain state/reducer/command modules.
- Bọc orchestration trong `ai-service/app/api/main.py`, `ai-service/app/pipeline/idp.py`.
- Dùng `ai-service/app/pipeline/units.py`, `runtime.py` làm checkpoint groundwork nhưng không coi demo checkpoint là durable.

**Contract**

Mỗi command:

```text
command_id, command_type, run_id, checkpoint_id?, generation_id,
actor_id, actor_role, correlation_id, idempotency_key,
expected_state_version, submitted_at, reason?, payload
```

Server kiểm tra tenant/role, state transition, version, expiry và schema. User context/request không tự nâng quyền evidence.

**Acceptance criteria**

- Invalid transition/role/stale/expired command bị từ chối deterministic.
- Retry cùng idempotency key trả cùng outcome.
- Concurrent approval chỉ một command thắng CAS.
- Reject/edit/cancel/timeout/expiration có audit-ready result.

**TDD/test cases**

- full transition matrix;
- incomplete context;
- approval/rejection/edit;
- stale generation;
- duplicate retry;
- two actor race;
- timeout/expiration/cancel race;
- unauthorized tenant/role;
- no auto-approve.

**Verification artifact**

- `artifacts/p2-state-transition-matrix.json`, reducer test report và command error catalog.

**Risk / rollback**

- Risk: state machine chặn flow legacy. Rollback: feature flag facade, route legacy synchronous job vào compatibility adapter; không bypass security trong new path.

**Dependency**

- P1.

---

### P3 — Long-running persistence, event envelope, outbox và replay

**Mục tiêu**

- Durable run/checkpoint/snapshot/event/audit store; survive reconnect/restart/crash.
- Event order, duplicate, gap, digest, replay và snapshot fallback.

**File/module dự kiến thay đổi**

- Mở rộng `ai-service/app/tools/jobs.py` hoặc tạo store riêng, không phá idempotency/lease hiện có.
- `ai-service/app/tools/persist.py` chỉ là baseline session persistence; thêm canonical store migration plan.
- Tạo event/outbox/replay modules; worker recovery/scheduler module.

**Contract**

Envelope:

```text
event_id, event_type, schema_version, run_id, tenant_id,
sequence, state_version, generation_id, created_at,
actor_id?, correlation_id, causation_id?, payload,
evidence_refs?, digest
```

Events baseline: `RUN_STARTED`, `SEGMENTATION_PROPOSED`, `HITL_REQUESTED`, `IMPACT_PREVIEW_READY`, `REVIEW_APPLIED`, `RECOMPUTE_STARTED`, `FACTS_READY`, `COMPARISON_READY`, `WARNING_RAISED`, `RUN_COMPLETED`, `RUN_FAILED`, `RUN_CANCELLED`.

**Acceptance criteria**

- Domain commit và outbox không mất event.
- Replay từ sequence hội tụ canonical state.
- Gap/retention thiếu dùng snapshot fallback; duplicate cùng digest không apply lần hai; cùng sequence khác digest fail closed.
- Process restart/worker lease reclaim resume được mà không duplicate side effect.

**TDD/test cases**

- sequence monotonic;
- duplicate/out-of-order/gap;
- DB commit + publish fail;
- HTTP timeout + command retry;
- event digest mismatch;
- snapshot corruption;
- worker crash/lease fencing;
- restart at every checkpoint;
- audit append-only.

**Verification artifact**

- `artifacts/p3-replay-convergence.json`, recovery trace, outbox reconciliation report.

**Risk / rollback**

- Risk: storage migration/PII retention. Rollback: read-only new log, disable replay consumer, continue legacy job path; không xóa audit/snapshot.

**Dependency**

- P2; cần DB/queue decision từ P0.

---

### P4 — Execution boundary và ADK/A2A adapters

**Mục tiêu**

- Cho pipeline hiện tại chạy dưới canonical run/worker boundary.
- Tạo interface để ADK optional; giữ A2A deferred cho independent-agent boundary.

**File/module dự kiến thay đổi**

- `ai-service/app/pipeline/idp.py`, `ai-service/app/pipeline/ai2_batch.py`, `ai-service/app/tools/jobs.py`.
- Tạo `adk_adapter` interface sau khi pin dependency/version.
- Chưa tạo A2A production endpoint; chỉ tạo ADR/contract stub khi có approval.

**Contract**

- Adapter nhận run snapshot + correlation/tenant scope; trả typed result/artifact/error.
- Adapter không sở hữu canonical state/audit.
- Retry phải nhận operation/idempotency context; callback/notification là advisory.

**Acceptance criteria**

- Current pipeline output giữ parity với baseline.
- ADK adapter, nếu bật, có version pin và mapping test; failure không mất canonical run.
- A2A không xuất hiện trên AI1→AI2 path nếu chưa có decision/need.

**TDD/test cases**

- pipeline success/failure/timeout;
- adapter version mismatch;
- callback duplicate/out-of-order;
- external tool no-citation;
- tool side effect denied/approved;
- tenant scope propagation;
- cancel/fence worker.

**Verification artifact**

- `artifacts/p4-adapter-contract.json`, parity report, dependency/license/security report.

**Risk / rollback**

- Risk: framework lock-in/version drift. Rollback: disable adapter and use current pipeline worker; canonical state remains.

**Dependency**

- P3; ADK/A2A human decision.

---

### P5 — API contract, authorization, security và observability

**Mục tiêu**

- Expose authenticated snapshot/command/replay endpoints và tenant/role enforcement.
- Correlation tracing, audit, redaction, external LLM/tool policy.

**File/module dự kiến thay đổi**

- `ai-service/app/api/main.py`.
- `packages/typescript/frontend-sdk/src/index.ts` API types/client.
- `backend/src/contract_intelligence/main.py` boundary/integration nếu BE skeleton được nối.
- Security/audit/telemetry modules và tests.

**Contract**

- `GET /runs/{run_id}` snapshot;
- `GET /runs/{run_id}/events?after=sequence` replay/stream source;
- `POST /runs/{run_id}/commands` typed HITL/cancel/resume;
- stable errors: forbidden, not-found/non-disclosure, stale, expired, conflict, invalid-context, unavailable.

**Acceptance criteria**

- Mọi read/write/replay/stream được tenant/role authorize ở server.
- Approval/rejection/edit/context/timeout/cancel audit đủ actor/time/reason/correlation/causation.
- Raw contract, secret, prompt injection và hidden reasoning không vào logs/traces.
- External calls mask/pseudonymize theo policy và fail closed khi policy thiếu.

**TDD/test cases**

- cross-tenant access;
- role matrix;
- replay scope;
- idempotent command response;
- redaction;
- prompt injection;
- tool allow/deny/approval;
- correlation propagation;
- audit tamper/read access.

**Verification artifact**

- `artifacts/p5-api-security-contract.json`, authz matrix, redaction scan, trace sample.

**Risk / rollback**

- Risk: auth provider/topology chưa biết. Rollback: không mở endpoint new path publicly; keep feature flag/internal-only.

**Dependency**

- P2/P3; production auth/tenant decisions.

---

### P6 — AG-UI boundary, fixed review UI và hybrid HTTP command + SSE

**Mục tiêu**

- Map canonical events sang AG-UI lifecycle/activity/interrupt/state events.
- FE fixed allowlisted cards/forms cho segmentation, context, approval, impact preview, facts/comparison.
- SSE là notification/replay transport; HTTP là command.

**File/module dự kiến thay đổi**

- `packages/typescript/frontend-sdk/src/index.ts` stream/command/snapshot client.
- `frontend/src/app/App.tsx` và reducer/components mới.
- `ai-service/app/api/main.py` SSE endpoint/heartbeat/auth.
- AG-UI adapter module; A2UI không bật mặc định.

**Contract**

- Event ordering bằng canonical sequence, không phụ thuộc arrival timestamp.
- FE duplicate dedup; gap yêu cầu snapshot; unsupported schema không crash.
- No chain-of-thought; only safe status/rationale/evidence/warning.
- A2UI nếu thử nghiệm: catalog allowlist, known action mapping, server authorization.

**Acceptance criteria**

- Client reconnect/resume giữ cùng state hash.
- Mất SSE không làm mất pending checkpoint/result.
- Command không đi qua EventSource; command idempotency/CAS vẫn enforce.
- Browser/proxy heartbeat/buffering/idle timeout pass target test.

**TDD/test cases**

- SSE connect/auth/heartbeat/disconnect;
- last sequence replay;
- retention gap snapshot;
- duplicate/out-of-order;
- concurrent tab stale command;
- AG-UI mapping/lifecycle;
- fixed card action allowlist;
- catalog mismatch/A2UI disabled;
- mobile/background reconnect nếu requirement được duyệt.

**Verification artifact**

- `artifacts/p6-event-ui-convergence.json`, AG-UI mapping matrix, SSE operational test report.

**Risk / rollback**

- Risk: SSE infra not support long-lived connection. Rollback to snapshot/polling; task state unaffected. WebSocket only after explicit trigger + benchmark.

**Dependency**

- P3/P5; FE review and transport decisions.

---

### P7 — Evaluation, regression, recovery và load gates

**Mục tiêu**

- Mở rộng framework `evals/` để chấm domain output và workflow/recovery.
- Tạo reviewed ground truth, golden cases, deterministic contract/replay/security/load tests.

**File/module dự kiến thay đổi**

- `evals/cards/`, `evals/corpus/`, `evals/eval_types/`, `evals/scripts/`, CI config.
- Chỉ thêm sau khi T0–T5 adjudication và no-code research approval hoàn tất.

**Contract**

- Metrics: schema, citation validity/entailment, precision/recall/completeness, boundary/relation, abstention, stale propagation, approval correctness, event ordering/replay, recovery, latency/timeout.
- Deterministic/security gates không bị thay bởi LLM judge.

**Acceptance criteria**

- Mỗi gate có denominator, expected behavior, reviewer/provenance.
- Process kill/restart, duplicate, race, replay and side-effect tests pass.
- Existing AI1/AI2 evals không regression.
- SLO/load thresholds được human approved, không tự đặt.

**TDD/test cases**

- 18 golden suites trong evaluation strategy;
- mutation missing citation/stale/event order;
- workflow crash/restart;
- concurrent approvals;
- SSE reconnect;
- tenant/redaction/prompt injection;
- long-running soak/load.

**Verification artifact**

- `artifacts/p7-evaluation-gate.json`, quality report, regression XML, load/recovery report.

**Risk / rollback**

- Risk: ground truth sai hoặc quá ít. Rollback: không bật publish gate mới; report score confidence/coverage và giữ advisory-only.

**Dependency**

- P1–P6; human adjudication.

---

### P8 — Migration, canary và cutover từ AI2 hiện tại

**Mục tiêu**

- Di chuyển từ synchronous workspace `/extract` và job `/jobs/idp` hiện tại sang canonical run facade mà không phá AI1 contract.
- Canary theo tenant/feature flag, dual-read/compare output trước cutover.

**File/module dự kiến thay đổi**

- `ai-service/app/api/main.py`, `ai-service/app/tools/jobs.py`, persistence migration.
- `packages/typescript/frontend-sdk/src/index.ts`, `frontend/src/app/App.tsx`.
- BE integration boundary nếu cần.

**Contract**

- Legacy route giữ behavior hoặc trả explicit deprecation/version; new route có run/generation/state fields.
- Raw AI1 snapshot và legacy result không bị overwrite.
- Publish chỉ nhận non-stale, verified generation.

**Acceptance criteria**

- Canary parity trong approved tolerance cho existing corpus.
- Rollback về legacy path không làm mất canonical audit/state.
- Migration restart/resume/partial deployment an toàn.

**TDD/test cases**

- old/new route parity;
- one JSON/multi-document;
- legacy session vs durable run;
- feature flag off/on;
- deploy mid-run;
- rollback mid-run;
- duplicate submit.

**Verification artifact**

- `artifacts/p8-migration-parity.json`, canary report, rollback drill record.

**Risk / rollback**

- Risk: data migration/route divergence. Rollback feature flags and traffic; preserve append-only records; no destructive migration.

**Dependency**

- P7 pass; operations/auth approval.

---

### P9 — Production hardening và release gate

**Mục tiêu**

- Verify SLO, capacity, retention, incident/recovery runbook, security and operational ownership.

**File/module dự kiến thay đổi**

- `docs/` operational additions, runbooks, dashboards/alerts/config.
- Không đưa protocol chưa được chọn vào production config.

**Contract**

- RTO/RPO, event retention, max run duration, max concurrent streams, retry budget, expiration policy, alert thresholds.

**Acceptance criteria**

- Recovery drill đạt RTO/RPO đã duyệt.
- Không có open critical auth/data-loss/duplicate-side-effect finding.
- On-call có runbook cho stuck checkpoint, outbox lag, replay gap, worker lease và external tool failure.
- Release decision ghi rõ known limitations/ground-truth coverage.

**TDD/test cases**

- chaos restart/queue duplicate/outage;
- stream saturation/proxy timeout;
- retention deletion + snapshot fallback;
- incident audit and rollback;
- security regression.

**Verification artifact**

- `artifacts/p9-production-readiness.json`, signed go/no-go record, rollback drill.

**Risk / rollback**

- Risk: production topology khác assumption. Rollback canary/feature flag; giữ legacy synchronous path cho đến khi issue đóng.

**Dependency**

- P8 và mọi human approval.

## 3. Coverage của 22 yêu cầu bắt buộc

| # | Requirement | Phase |
|---:|---|---|
| 1 | canonical domain model | P1 |
| 2 | reasoning state machine | P2 |
| 3 | HITL command model | P2 |
| 4 | context request/response | P1/P2 |
| 5 | approval/rejection | P2 |
| 6 | ADK adapter | P4 |
| 7 | A2A adapter | P4, deferred gate |
| 8 | long-running persistence | P3 |
| 9 | event envelope | P3 |
| 10 | correlation ID | P2/P3/P5 |
| 11 | replay | P3/P6 |
| 12 | retry/idempotency | P2/P3/P4 |
| 13 | cancellation | P2/P5 |
| 14 | timeout | P2/P4/P9 |
| 15 | SSE/WebSocket decision | P6 + ADR |
| 16 | A2UI/AG-UI boundary | P6 + ADR |
| 17 | API contract | P5/P6 |
| 18 | security | P5/P9 |
| 19 | observability | P3/P5/P9 |
| 20 | evaluation | P7 |
| 21 | migration | P0/P8 |
| 22 | rollback | every phase, drill P8/P9 |

## 4. Open questions blocking implementation approval

1. BE chọn PostgreSQL/SQLite production, queue và worker orchestration nào?
2. Phase 1 approval là named reviewer, any-one hay all-required?
3. TTL/expiration/reopen behavior cụ thể?
4. Auth provider, tenant identifier, role model và non-disclosure policy?
5. Event/snapshot/audit retention và raw contract privacy policy?
6. SSE idle timeout/concurrent stream/mobile requirement/SLO?
7. AG-UI version/schema pin nào; FE fixed components đã đủ chưa?
8. ADK có phải technology commitment không; A2A có roadmap thực sự không?
9. Fact edit được sửa value hay chỉ boundary/relation/classification?
10. Ai adjudicate ground truth và publish threshold?
11. Tool/external LLM allowlist và side-effect policy?
12. Có chấp thuận feature flag + legacy rollback trong suốt migration không?

## 5. Human approval checklist

- [ ] P0 decision summary.
- [ ] BE canonical state/persistence ownership.
- [ ] Hybrid HTTP command + SSE phase đầu.
- [ ] WebSocket chỉ conditional fallback.
- [ ] AG-UI adapter/fixed UI; A2UI optional disabled.
- [ ] A2A deferred giữa AI1–AI2.
- [ ] Security/privacy/external-tool policy.
- [ ] Approval/TTL/expiration/multi-user policy.
- [ ] Ground-truth adjudication và evaluation gates.
- [ ] Migration/canary/rollback policy.

## 6. Execution record

Plan đã được human approve và đã thực thi bằng:

```text
hs:cook plans/260923-1023-ai2-long-running-architecture/plan.md --tdd
```

Cook đã đóng plan với `10/10` phase PASS, code review R7 PASS, test/evaluation gates PASS; các giới hạn prototype và open questions vẫn cần xử lý trước production rollout.
