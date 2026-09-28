# System Architecture

> Bản đồ current-state đối chiếu với repository ngày 2026-09-25. Protocol HITL/live và tên framework trong plan chỉ được xem là implemented khi có code wiring và test tương ứng.

## Overview và ownership

VSF là monorepo contract intelligence. AI1/OCR tạo JSON evidence; AI2 nhận snapshot hoặc Backend processing request, giữ raw source, dựng projection canonical, extract fact/event/context, so sánh candidate và trả kết quả có citation. Backend là owner của public API, shared ACL, durable read model/lifecycle và authoritative publish boundary. AI2 vẫn có FastAPI demo, SQLite job/session persistence, in-memory workspace store và BackgroundTasks cho job execution; đây không phải bằng chứng của external queue hoặc HA production.

- `ai-service/app/contracts/`: Pydantic domain/wire models, service envelope và schema/semantic validation.
- `ai-service/app/pipeline/`: AI1 adapter/handoff, canonical projection, extraction, comparison, context, citation grounding, IDP orchestration và execution adapter.
- `ai-service/app/reasoning/`: query stack, HITL state reducer và command validation; reducer P2 chưa nối với route.
- `ai-service/app/tools/`: in-memory store, SQLite job/session persistence và P3 `DurableRunStore` cho local snapshot/checkpoint/event/outbox/audit/lease primitives.
- `ai-service/app/security/`, `transport/`, `migration/`, `ops/`: lần lượt là P5 decision utility, P6 transport utility, P8 migration utility và P9 evidence checker; không module nào tự biến thành production orchestrator.
- `ai-service/app/ai2/v1/`: package `ai2.package.v1`, input profile `ai1.snapshot.v1/ocr-lab`; package v1 chỉ bật `relation_policy=INDEPENDENT`.
- `ai-service/src/contract_ocr/`: AI1/OCR-lab và serializer `ai1.snapshot.v1`, không phải AI2 reasoning ownership.
- `evals/`: deterministic contract/workflow scorers và test gates, không tự tạo approved business ground truth.
- `frontend/` và `packages/typescript/`: HTTP REST client và các màn hình dossier/query/review/citation/finding; chưa có live event/HITL client.
- `backend/src/contract_intelligence/`: public backend route layer, shared ACL, AI2 result projection và worker recovery seam; chưa là external-queue/HA production orchestrator.

## Implementation sync — 2026-09-25

Các thay đổi đã được kiểm chứng trong cook plan `260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238`:

- Route review/approval canonical dùng trusted principal, RBAC và cùng dossier ACL với query/search/read; simulated mutation route không còn được đăng ký trong production path.
- Backend lưu AI2 result projection đầy đủ: facts/findings/context findings, events/chunks/citations, evidence issues, annex links, coverage, digest/idempotency, `review_state`, reason code và `evidence_ready`. `SUCCEEDED` của job không tự đồng nghĩa evidence-ready.
- Query có dossier-scoped lexical fallback trước vector/LLM theo policy; response giữ `review_state`, `retrieval_layer`, `reasoning_trace`, evidence issues và `used_llm`. Frontend giữ nguyên trạng thái server và fail closed khi thiếu state.
- Citation/finding UI đọc dữ liệu động, giữ body/annex scope, provenance, unresolved gap, severity, hai phía evidence, `base_version`, conflict `409` và audit revision.
- Worker hydrate snapshot từ `pipeline_run.config_snapshot` durable projection trước cache; digest/idempotency tránh submit AI2 lặp sau restart. `AI_SERVICE_MODE=http` là mặc định canonical; stub/OCR legacy chỉ là compatibility lane explicit và không được masquerade thành AI2 result.

Phạm vi trên vẫn là offline/targeted implementation evidence. Authenticated E2E với Keycloak chưa chạy; chưa claim Kafka/external queue, HA, live SSE hoặc production deployment recovery.

## Current flow

### Backend job lane

Backend request → verify signed service envelope/ACL → validate snapshots/identities/members/relation map → adapt immutable input → `BackgroundTasks` nhận job → worker claim local job lease → chạy `run_idp` với policy/budget → serialize `ai2.be.processing.result.v1` → AI2 job store trả wire result → Backend persist durable AI2 read model, evidence/review projection và poll `/jobs/{job_id}` với signed envelope.

`POST /jobs/idp` và `GET /jobs/{job_id}` là boundary thật hiện tại. POST trả `202`/`QUEUED`; local demo chạy background task trong process. Backend worker có hydrate/reconcile snapshot đã persist và bounded idempotent recovery, nhưng đây chưa phải external queue, durable scheduler, HA hoặc live authenticated deployment.

### Workspace và package lane

Workspace: session JSON → adapter → SQLite session + in-memory store → `/extract` chạy `run_idp` synchronous hoặc `/reason` implicit extraction → `/ask` qua reasoning stack → FE hiển thị answer/citations. Review overlay/publish endpoints là workspace demo, không phải multi-user authorization/HITL state machine P2 đã route hóa.

Package: `process_files()` chạy batch AI2; `process_payloads()` chỉ validate/adapt; `process_payloads_full()` chạy full batch. Relation-aware models tồn tại nội bộ nhưng package v1 chỉ cho `INDEPENDENT`, nên không claim cross-document finding mặc định.

## P0–P9 implementation boundary

| Phase | Có thật trong code | Không được suy diễn thành |
|---|---|---|
| P0 | Contract tests cho version/unknown fields/reference/multi-document/idempotency/citation. | TTL/retention production policy. |
| P1 | `AI2Run`, logical documents, boundaries, facts, relations, citations, generation, stale propagation. | Durable store hoặc legal conclusion. |
| P2 | Transition matrix, tenant/role/generation checks, CAS, idempotency receipts, timeout/expiration, audit-ready result. | Durable state machine qua restart; reducer còn in-process. |
| P3 | SQLite digest-checked snapshots/checkpoints, contiguous events, atomic outbox, append-only audit, lease fencing. | HA, queue delivery, external exactly-once, retention, RTO/RPO hoặc scheduler. |
| P4 | Typed current-pipeline adapter và optional version-pinned ADK protocol; cancellation/timeout/lease/scope/error mapping. | ADK runtime thật, A2A endpoint hoặc production tool execution. |
| P5 | Deny-by-default scope/role/action với trusted `Principal` binding, constructor-bound resource scope, actor-bound command idempotency, finite approval TTL, process-local one-time consumed registry, `ApprovalGrant`, redaction, tool policy và prompt-injection label. | Global HTTP auth middleware, approval issuer/durable ledger, shared ledger hoặc command execution. |
| P6 | Event scope/order, AG-UI allowlist có expected scope, read-only SSE session bind principal/run/resource với binding normalized immutable, heartbeat/cursor/state hash và A2UI gate. | HTTP/SSE production route, SSE/WebSocket server, live event log, replay API hoặc FE live review. |
| P7 | Approved-ground-truth validation, exact field score và workflow metrics ordering/replay/idempotency/recovery/security. | Business accuracy nếu chưa adjudicate; load/soak/chaos production. |
| P8 | Legacy/canary/canonical flags, dual-read, JSON parity paths, idempotent submit, verified-generation publish guard, rollback. | Route cutover, persisted migration, canary traffic hoặc rollback drill thật. |
| P9 | Fail-closed checks cho critical findings, RTO/RPO declarations, retention coverage, observability/artifact refs, cases, rollback evidence; operational `passed`/`required` và rollback flags phải là boolean thật. | Deployment/HA/live traffic/recovery proof; `PASS` chỉ là supplied bounded evidence/configuration. |

## Event, SSE và UI

`app/transport/events.py` là library boundary. `EventEnvelope` có tenant/run scope, sequence, state version/hash, event type/schema, correlation và replayable flag. `validate_scope()` chỉ nhận canonical envelope đầy đủ trong expected tenant/run và resource scope khi được yêu cầu. `classify_delivery()` phân loại `ACCEPTED`, `DUPLICATE`, `OUT_OF_ORDER`, `GAP`; `map_to_agui()` bắt buộc expected tenant/run/resource, allowlist và sanitize key nhạy cảm.

`SseSession` giữ cursor/state hash và chỉ authorize khi trusted `Principal` có `stream.read`, tenant, run, principal actor và resource đều khớp session. Constructor kiểm tra `principal_id`/`resource_id` là binding non-empty, normalize string subclass về plain `str`, và dùng dataclass `frozen=True, slots=True`; heartbeat/reconnect trước authorization không trả metadata. Session read-only, `reject_command()` buộc command qua HTTP. Chưa có connection manager, auth middleware, HTTP/SSE production route, SSE response stream hoặc replay route. P3 durable store có thể cung cấp replay source nhưng chưa được route hóa vào P6. A2UI mặc định disabled; không có dynamic UI execution và không thêm WebSocket. FE SDK hiện chỉ có REST `getSession`, `ask`, `verifyCitation`.

## Security, trust và data handling

- Signed service envelope mang tenant/dossier/actor/nonce/payload digest; `/jobs/{job_id}` kiểm tra envelope với owner scope trong job store.
- AI1 snapshot là source evidence, không phải legal conclusion. Raw text/page/table geometry/source digest giữ nguyên; AI2 không sửa OCR và không tự chọn legal winner.
- LLM/vector là candidate material không đáng tin cậy. Citation resolver/grounding/review state là AI2 checks; `PASS` không phải legal approval.
- P5 policy deny-by-default cho `snapshot.read`, `replay.read`, `stream.read`, `hitl.command`; `read_only` bị chặn command. `AuthzRequest` phải có trusted `Principal` binding; actor/tenant/role của request phải khớp principal. `SecurityPolicy` bind tenant/dossier từ constructor và deny caller override hoặc request ngoài scope. Cross-scope, unknown action/role/tool và side effect chưa có grant hợp lệ bị deny.
- `ApprovalGrant` là capability/record contract immutable được primitive kiểm tra, bind `approval_id`, tenant, dossier, actor, tool và command digest. `ttl_seconds` phải finite và không âm; grant được consume một lần trong registry có lock nhưng registry này chỉ process-local, non-durable. `approved=True` và `approved_tools` không cấp quyền side effect; việc phát hành grant và lưu durable issuer/approval ledger không nằm trong module này.
- `SecurityPolicy` cache command decision theo tuple actor-bound `(tenant_id, dossier_id, actor_id, idempotency_key)`; `plans/260923-1023-ai2-long-running-architecture/artifacts/p5-api-security-contract.json` hiện aligned với tuple này và vẫn chỉ là contract artifact, không phải shared durable ledger.
- Redaction helpers của P5/P6 xử lý `raw_contract`, `hidden_reasoning`, prompt, secret/token; đây là utility boundary, chưa là cam kết mọi logger/route production đã sanitized.
- P2 reducer, P5 cache, approval consumed registry và session/in-memory store là process boundaries. SQLite P3 local không thay Backend durable persistence, ACL, audit ownership hay publish authority.

## Migration và readiness

P8 giữ legacy path và mapping legacy session → run trong `MigrationBoundary`; canary có thể dual-read và so sánh JSON-like output theo path ổn định. Retry cùng idempotency/payload trả record cũ; conflict bị reject; stale/unverified generation không publish; rollback đặt mode về legacy. Chưa có route wiring hoặc traffic controller.

P9 `evaluate_readiness()` kiểm tra finding critical, RTO/RPO target/denominator, `retention_days >= recovery_window_days`, observability, runbook/dashboard/alert refs, rollback owner/flag/drill và `REQUIRED_OPERATIONAL_CASES` gồm `chaos-restart`, `queue-duplicate-outage`, `stream-saturation`, `retention-gap`, `incident-audit`, `security-regression`. `OperationalCase.passed`, `OperationalCase.required` và `legacy_path_available`/`canary_feature_flag`/`rollback_drill_passed` phải là boolean thật; thiếu case, sai category, failed hoặc thiếu positive denominator đều fail-closed. Nó không kiểm tra file/infrastructure reference có tồn tại, không chạy live drill và không chứng minh HA; `PASS` chỉ phản ánh supplied bounded evidence/configuration. Test retention đúng không thay thế operational exercise.

## Constraints và non-goals

- Không PDF/OCR trong AI2 reasoning; AI2 tiêu thụ JSON. Không automatic authoritative publish, ACL ownership, legal conclusion hay `LEGAL_WINNER`.
- Không claim production HITL pause/resume, multi-user approval, event replay endpoint, SSE/WebSocket streaming, AG-UI/A2UI runtime, ADK/A2A execution, migration cutover, HA hoặc RTO/RPO chỉ từ phase artifacts. Worker snapshot hydrate/reconcile sau restart đã có targeted coverage, nhưng không thay thế production HA/recovery proof.
- Phase artifact/report là evidence của test/boundary tương ứng, không thay code wiring hoặc infrastructure evidence. Khi plan khác code, current code và test là nguồn sự thật của tài liệu current-state.
