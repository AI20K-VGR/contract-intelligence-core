# Critique toàn bộ research report AI2

Ngày: 2026-09-23  
Phương pháp: adversarial review theo các lens correctness, protocol, durability, security, UX/state synchronization và operability.  
Phạm vi reviewed: `current-state-ai2-audit.md`, Track A–D, glossary/source matrix và các quyết định đã chốt trong Outcome Contract.

## 1. Verdict

**Verdict: CONDITIONAL PASS — đủ làm đầu vào cho architecture plan, chưa đủ làm production contract.**

Các report đã phân biệt khá rõ fact/spec, implementation detail và inference. Tuy nhiên research chưa thể chứng minh behavior của hạ tầng cụ thể của repository vì worker/queue/auth/LB/FE runtime chưa có implementation tương ứng. Vì vậy các recommendation chỉ được đưa vào plan dưới dạng ADR cần xác nhận, không được coi là sự thật hiện hành.

## 2. Findings theo mức độ

### C1 — Critical: canonical truth và event truth chưa được materialize trong code

- Evidence: audit ghi nhận `InMemorySnapshotStore`, job SQLite và không có durable event/replay runtime.
- Risk: report nói “resume/replay” nhưng hiện chưa có store, sequence allocator, outbox hay recovery worker để enforce.
- Required correction: plan phải tạo domain state/event contract trước adapter AG-UI/SSE/ADK/A2A; acceptance test phải giết/restart process và kiểm tra state/effect.
- Gate: không được quảng bá long-running resume trước khi recovery test pass.

### C1 — Critical: “waiting_for_human” chưa được định nghĩa thành transition có authorization

- Risk: UI có thể hiển thị form nhưng server vẫn nhận command ngoài checkpoint hoặc nhận approval cho generation stale.
- Required correction: mỗi command cần `run_id`, `checkpoint_id`, `expected_state_version`, actor/role, correlation ID, idempotency key; reducer server phải kiểm tra transition và tenant scope.
- Gate: FE state không được quyết định quyền resume.

### C1 — Critical: event protocol bị trộn với domain event

- `RunStarted`, `RunFinished`, state delta là AG-UI vocabulary; `SEGMENTATION_PROPOSED`, `IMPACT_PREVIEW_READY`, `FACTS_READY` là AI2 domain event.
- Risk: đổi AG-UI làm vỡ domain contract hoặc ngược lại; consumer không biết event nào durable.
- Required correction: canonical envelope/domain event độc lập; adapter map sang AG-UI; mọi event transport đều có sequence/state version.

### C1 — Critical: authorization của A2A/AG-UI/SSE chưa được enforce bởi protocol

- Protocol có authentication/transport primitives nhưng không tự cấp quyền đọc contract, submit approval hay đọc tenant khác.
- Required correction: authorization tại command, snapshot, replay, stream subscription và tool call; deny-by-default; audit denied attempt.

### H1 — High: reconnect có thể mất context hoặc áp dụng sai thứ tự

- `Last-Event-ID`/WebSocket reconnect chỉ là transport hint.
- Risk: FE tiếp tục từ delta thiếu, duplicate hoặc stale approval.
- Required correction: `last_sequence`, bounded replay, snapshot fallback, gap detection, state_version check và server `GET snapshot` là recovery path.

### H1 — High: duplicate/out-of-order event chưa có normative rule đầy đủ

- Reports đã đề cập dedup nhưng chưa quy định consumer behavior cho gap, duplicate khác payload, sequence reuse.
- Required correction:
  - `event_id` immutable và unique trong run;
  - sequence monotonic trong stream;
  - cùng sequence khác digest là integrity error;
  - duplicate cùng digest được bỏ qua;
  - gap quá retention yêu cầu snapshot;
  - không tự reorder vô hạn.

### H1 — High: approval race và stale decision chưa có state transition matrix

- Optimistic concurrency đã được đề xuất nhưng chưa liệt kê HTTP/error contract.
- Required correction: một decision thắng bằng CAS; decision thua trả `409 CHECKPOINT_VERSION_CONFLICT`; audit cả decision thắng/thua; không retry mù command reject.

### H1 — High: retry sau side effect vẫn là rủi ro framework-independent

- LangGraph cảnh báo node có thể chạy lại; A2A/ADK notification cũng có thể duplicate.
- Required correction: chia pre-commit/post-approval, idempotency key theo side effect, external operation token, compensation hoặc manual recovery. Không gọi external side effect trước gate nếu không cần.

### H1 — High: A2UI maturity bị suy luận quá rộng

- A2UI repository ghi v0.9.1 production và v1.0 evolving tại thời điểm nghiên cứu.
- Risk: lấy v1.0 candidate làm stable contract.
- Required correction: phase 1 không phụ thuộc A2UI; nếu thử nghiệm phải pin version/commit, catalog allowlist và test unsupported catalog.

### H1 — High: “reasoning live stream” dễ bị hiểu thành chain-of-thought

- Required correction: chỉ public safe progress/reasoning summary/decision rationale có policy; không phát token trace hoặc internal hidden reasoning. Đây là security/privacy acceptance criterion.

### M1 — Medium: ADK session và A2A task bị đặt cạnh canonical run quá gần

- ADK session/A2A task là integration representation.
- Required correction: mapping table một chiều; canonical `AI2Run` do AI2/BE sở hữu; adapter phải chịu version drift và map lỗi.

### M1 — Medium: recommendation SSE chưa có workload measurement

- Recommendation hợp lý với checkpoint interaction nhưng chưa có concurrency, idle timeout, mobile background hoặc proxy data.
- Required correction: ghi là provisional; benchmark/test với target SLO trước production. Có rollback path sang WebSocket nếu continuous duplex requirement xuất hiện.

### M1 — Medium: evaluation metric chưa có denominator/adjudication

- “citation correctness” và “completeness” có nguy cơ thành metric khẩu hiệu.
- Required correction: định nghĩa unit, denominator, abstention handling, reviewer disagreement, confidence interval và publish gate.

### M1 — Medium: expiration/cancellation semantics chưa thống nhất

- Track A có `EXPIRED`, objective có timeout/expiration/cancellation, nhưng terminal vs reopen chưa chốt.
- Required correction: human approval cho policy; không cho plan giả định TTL/reopen.

### L1 — Low: thuật ngữ “pause” gây ambiguity

- `PAUSED` có thể là operational state hoặc waiting state.
- Recommendation: public domain state là `WAITING_FOR_HUMAN`; `paused_reason` là substate/metadata.

## 3. Protocol assumption audit

| Assumption dễ sai | Trạng thái | Cách sửa |
|---|---|---|
| SSE Last-Event-ID bảo đảm replay | Sai nếu thiếu event store | dùng sequence + replay/snapshot application layer |
| WebSocket là durable session | Sai | task state nằm ở BE store |
| AG-UI interrupt là approval enforcement | Sai | server command reducer enforce |
| A2A auth-required là authorization | Sai | kiểm tra principal/scope mỗi operation |
| ADK session là audit/legal record | Chưa chứng minh | canonical audit ngoài ADK |
| A2UI component/action an toàn vì protocol | Sai | catalog/action allowlist + server validation |
| token stream là reasoning progress có thể resume | Sai | durable safe events/snapshot |
| retry sẽ không lặp side effect | Sai | idempotency/fence/compensation |

## 4. Required additions to implementation plan

1. State transition table và invariant test trước mọi transport.
2. Versioned command schema với conflict/expired/forbidden errors.
3. Durable event envelope, digest, sequence allocator, outbox và snapshot cadence.
4. Replay protocol: from sequence, snapshot fallback, retention gap và integrity error.
5. Crash/restart test có external side-effect spy.
6. Multi-user approval race test với concurrent commands.
7. Tenant/role matrix cho snapshot, event stream, command, replay và audit.
8. Explicit no-chain-of-thought/redaction tests.
9. A2UI disabled-by-default feature flag và catalog conformance test.
10. SSE operational test và documented WebSocket trigger/rollback.
11. Evaluation denominator/adjudication protocol.

## 5. Research limitations

- Chưa có production topology, BE worker, queue, database schema, auth provider hoặc FE event reducer để kiểm chứng operational claims.
- Chưa có ground truth nghiệp vụ đủ tin cậy để chấm legal correctness.
- Chưa chạy benchmark SSE/WebSocket hoặc crash/recovery integration vì yêu cầu hiện tại là không viết code.
- Vì vậy verdict chỉ cho phép tiếp tục architecture planning, chưa cho phép claim production readiness.
