# ADR — AI2 long-running reasoning, HITL và live review

Ngày: 2026-09-23  
Trạng thái: **Proposed — cần human approval trước implementation**  
Scope: AI2 hiện tại, input là AI1 `ocr.json`/snapshot; không thay AI1 OCR contract trong ADR này.

## 1. Decision summary

| Area | Option được đề xuất | Mức chắc chắn |
|---|---|---|
| HITL state | BE/domain-owned reducer + durable state store | Recommendation, cần xác nhận DB/queue |
| Runtime | Giữ pipeline hiện tại; adapter ADK sau; chưa dùng A2A giữa AI1–AI2 | Recommendation |
| Event | Canonical versioned envelope + domain events + outbox | Recommendation |
| Persistence/replay | State snapshot + append-only event/audit + replay/snapshot fallback | Recommendation |
| UI protocol | AG-UI adapter; fixed allowlisted FE components trước | Recommendation |
| Dynamic UI | A2UI optional, disabled-by-default | Recommendation |
| Transport | Hybrid HTTP command + SSE | Provisional recommendation |
| WebSocket | Không chọn phase đầu; chỉ mở khi workload chứng minh cần duplex liên tục | Conditional fallback |

## 2. HITL state machine

### Option A — BE/domain-owned durable reducer (**đề xuất**)

- **Mô hình:** command được authenticate/authorize; reducer kiểm tra current state/version; commit snapshot + event/audit; worker tiếp tục từ checkpoint.
- **Ưu:** framework-independent; audit/CAS/tenant policy rõ; migration từ runtime hiện tại kiểm soát được; test deterministic.
- **Nhược:** phải tự xây persistence, lease, scheduler, replay và race handling.
- **Failure:** DB/outbox/worker crash; cần atomic commit, outbox, recovery lease.
- **Security:** policy enforce tại command/snapshot/stream; dễ audit.
- **Complexity:** cao ở BE, nhưng complexity nằm đúng owner.
- **Migration:** thêm orchestration quanh `run_id`/job hiện tại; giữ pipeline extraction.
- **Testability/observability:** reducer/state/event có thể unit/integration test và trace bằng correlation/causation.
- **Lý do:** phù hợp invariant user đã chốt: UI không phải truth, resume sau restart.

### Option B — Framework-owned interrupt/session (ADK/LangGraph)

- **Mô hình:** framework giữ pause/resume/session; BE bọc endpoint.
- **Ưu:** triển khai checkpoint nhanh; có pattern HITL sẵn.
- **Nhược:** framework state/version/upgrade có thể thành public dependency; audit/tenant/CAS/legal evidence phải bổ sung.
- **Failure:** rerun side effect, session loss, version drift, framework persistence mismatch.
- **Security:** dễ nhầm session/thread ID với authorization.
- **Complexity:** thấp ban đầu, cao khi migration/forensics.
- **Migration:** có thể phải rewrite pipeline quanh framework.
- **Testability/observability:** phụ thuộc framework internals.
- **Lý do loại làm canonical:** dùng được như adapter/runtime candidate, không làm source of truth.

## 3. ADK/A2A integration

### Option A — Internal ADK adapter, no A2A now (**đề xuất**)

ADK chỉ nhận canonical run/checkpoint snapshot và trả bounded tool/agent result. BE vẫn sở hữu task state, evidence, audit và authorization. AI1→AI2 giữ HTTP/JSON snapshot contract.

- Failure: ADK timeout/version drift; adapter map error và retry idempotent.
- Security: external tool scope bằng allowlist/tenant context; không truyền raw data ngoài policy.
- Migration/test/observability: thêm sau canonical model, contract tests và trace propagation.

### Option B — A2A giữa AI1 và AI2 ngay

AI1 là agent server, AI2 là agent client; dùng A2A Task/Context/Artifact.

- Ưu: chuẩn hóa agent handoff/discovery/task lifecycle.
- Nhược: thêm AgentCard, auth, task/error mapping, artifact semantics và conformance surface trong khi AI1 hiện chỉ là evidence JSON producer.
- Failure: duplicate push, task callback mất, artifact context mismatch.
- Security: A2A auth không thay domain authorization/tenant checks.
- Migration/complexity: lớn, không giải quyết segmentation/citation/legal semantics.
- **Loại phase đầu:** chưa có nhu cầu opaque independent-agent boundary.

### Option C — Custom internal RPC/work queue

BE queue job tới AI2 worker, callback/status nội bộ.

- Ưu: đơn giản, fit codebase hiện tại.
- Nhược: không interoperability/discovery; tự định nghĩa lifecycle.
- **Vai trò:** implementation substrate có thể cùng tồn tại với Option A; không phải public agent protocol.

## 4. Event envelope

### Option A — Canonical envelope + domain event + adapter (**đề xuất**)

Tối thiểu cần:

```text
event_id, event_type, schema_version, run_id, tenant_id,
sequence, state_version, generation_id, created_at,
actor_id?, correlation_id, causation_id?, payload,
evidence_refs?, digest
```

- **Ưu:** replay/dedup/order/audit độc lập transport; AG-UI mapping không khóa domain.
- **Nhược:** versioning và storage overhead.
- **Failure:** sequence allocator/outbox bug; kiểm tra digest và reconciliation.
- **Security:** filter payload theo actor scope; không đưa raw contract/CoT.
- **Testability:** schema, monotonic sequence, duplicate/gap/replay dễ kiểm tra.

### Option B — Chỉ dùng AG-UI event payload

- **Ưu:** ít model.
- **Nhược:** domain semantics bị protocol coupling; AG-UI event không tự chứa AI2 citation/generation/authorization.
- **Failure:** protocol version đổi làm mất audit/replay; UI event bị coi là truth.
- **Loại làm canonical;** chỉ dùng adapter mapping.

## 5. Persistence/replay

### Option A — Snapshot + append-only event/audit + outbox (**đề xuất**)

- Snapshot là recovery point; event là lịch sử/state transition; outbox đảm bảo commit và publish không tách rời.
- Replay từ sequence; nếu retention gap thì snapshot mới; event digest mismatch fail closed.
- **Ưu:** recovery, audit, UI resync và worker restart cùng một source.
- **Nhược:** schema migration, retention và storage cost.

### Option B — Chỉ lưu latest state/result

- **Ưu:** đơn giản/rẻ.
- **Nhược:** không replay, không forensic, không chứng minh approval/causation, khó debug race.
- **Loại:** không đáp ứng long-running/HITL requirements.

### Option C — Event sourcing toàn phần không snapshot

- **Ưu:** lịch sử đầy đủ.
- **Nhược:** replay dài cho hồ sơ lớn, schema evolution và PII retention khó.
- **Không chọn phase đầu:** dùng hybrid snapshot + event phù hợp hơn.

## 6. A2UI/AG-UI boundary

### Option A — Canonical AI2 events → AG-UI adapter → fixed FE components (**đề xuất**)

- **Ưu:** protocol đổi không làm đổi domain; FE controlled; security dễ.
- **Nhược:** phải viết mapper và fixed UI coverage.
- **Failure:** mapping thiếu event; contract tests và snapshot fallback.
- **Migration:** FE hiện REST-only, thêm stream/reducer/command từng bước.

### Option B — A2UI dynamic surfaces ngay

- **Ưu:** forms/cards linh hoạt; agent có thể mô tả UI.
- **Nhược:** catalog/version evolving; action injection; renderer mismatch; khó test và audit.
- **Security:** allowlist bắt buộc, server không tin action từ client.
- **Loại phase đầu:** bật sau khi event/command canonical ổn định.

### Option C — FE custom REST polling

- **Ưu:** ít hạ tầng stream.
- **Nhược:** không live review mượt, polling load, latency và khó biểu diễn interrupt.
- **Fallback:** dùng cho snapshot/recovery, không là live channel chính.

## 7. Transport decision

### Option A — Hybrid HTTP command + SSE (**đề xuất phase đầu**)

- `POST /runs`/existing submit: tạo run.
- `GET /runs/{id}`: canonical snapshot.
- `GET /runs/{id}/events?after=sequence`: SSE/replay.
- `POST /runs/{id}/commands`: context, approve, reject, edit, confirm-impact, resume, cancel.
- **Ưu:** interaction hiện checkpoint-based; command auth/idempotency rõ; browser/proxy đơn giản hơn; test tách mutation và notification.
- **Nhược:** hai kênh; SSE vẫn cần heartbeat/buffering/idle-timeout tuning.
- **Failure:** disconnect/gap; xử lý bằng replay/snapshot.
- **Security:** auth POST và stream độc lập, stream không được tự cấp command quyền.
- **Complexity:** vừa; domain persistence là phần chính.
- **Migration:** bổ sung vào REST hiện tại, không phá JSON AI1.
- **Observability:** correlation nối POST→event→worker→audit.

### Option B — WebSocket duplex

- **Ưu:** một session hai chiều, latency thấp, phù hợp continuous interaction.
- **Nhược:** browser API không có backpressure tự động; reconnect/auth/heartbeat/proxy/sticky/session broker phức tạp; command/event coupling dễ hơn.
- **Failure:** socket sống nhưng task đã đổi; cần snapshot/replay vẫn vậy.
- **Security:** handshake và từng command đều phải authorize.
- **Migration/ops:** lớn hơn SSE; cần benchmark chứng minh lợi ích.
- **Chỉ chọn khi:** nhiều command liên tục/low-latency duplex là requirement đã đo được.

### Option C — HTTP polling only

- **Ưu:** đơn giản, dễ vận hành.
- **Nhược:** không live; latency/load kém khi nhiều run; UX review yếu.
- **Vai trò:** fallback khi stream không khả dụng, không phải primary live channel.

### Decision matrix

| Tiêu chí | Hybrid HTTP+SSE | WebSocket | Polling |
|---|---:|---:|---:|
| Checkpoint fit | 5 | 3 | 2 |
| Duplex liên tục | 2 | 5 | 1 |
| Reconnect/replay dễ kiểm soát | 4 | 2 | 4 |
| Browser/proxy operations | 4 | 2 | 5 |
| Command idempotency boundary | 5 | 3 | 5 |
| Current codebase migration | 4 | 2 | 4 |
| Long-running durability (transport-only) | 1 | 1 | 1 |
| Cần domain store riêng | 5 | 5 | 5 |
| Đánh giá hiện tại | Chọn provisional | Giữ fallback | Recovery fallback |

Điểm chỉ là decision aid, không phải benchmark. SSE/WS đều không tự tạo durability.

## 8. Security/observability decisions áp dụng chung

- Authorization tại mọi read snapshot, replay, stream subscription và mutation command.
- Tenant/run IDs không phải secret; vẫn cần scope và non-disclosure policy.
- Pseudonymize/mask external LLM/tool; classify tool side effects; approval trước side effect.
- Redact raw contract, prompt, secret và hidden reasoning khỏi log/telemetry.
- Propagate `correlation_id`, `causation_id`, `run_id`, `generation_id`, `attempt`.
- Audit append-only cho approval/rejection/edit/context/timeout/cancel và denied actions.
- Alert event gap, outbox lag, lease expiry, stale publish, duplicate command và recovery failure.

## 9. Migration and rollback

### Migration

1. Giữ adapter `ai1.snapshot.v1`/compatibility hiện tại.
2. Bọc `run_id` hiện tại vào canonical AI2 run/generation.
3. Chạy synchronous pipeline dưới durable command/state facade.
4. Thêm checkpoint segmentation trước các cross-document conclusions.
5. Thêm event/outbox và snapshot API.
6. Thêm AG-UI/SSE read path; HTTP command path trước WebSocket.
7. Chỉ bật ADK/A2UI/A2A bằng feature flag sau contract tests.

### Rollback

- Tắt feature flag live/HITL adapter; giữ input/result compatibility.
- Command chưa apply bị reject an toàn; không rollback raw AI1.
- Generation mới không được publish nếu verification fail; vẫn giữ audit/snapshot cũ.
- Revert transport về snapshot/polling; task state vẫn ở canonical store.
- Framework adapter lỗi thì chạy bounded current pipeline hoặc mark failed/manual recovery, không bypass approval.

## 10. Human decisions required

1. Chấp thuận BE/domain store là owner của canonical task state.
2. Chấp thuận hybrid HTTP command + SSE là primary phase đầu, WebSocket là conditional fallback.
3. Chọn DB/queue/worker/lease/fencing cụ thể.
4. Chọn approval policy phase 1 và TTL/expiration behavior.
5. Chấp thuận AG-UI adapter + fixed components; A2UI disabled-by-default.
6. Chấp thuận A2A chưa dùng giữa AI1–AI2.
7. Chọn auth/tenant/retention policy và external tool data policy.
8. Chọn ground-truth adjudicator và publish thresholds.
