# Track C — A2UI và AG-UI

Ngày truy cập nguồn: 2026-09-23  
Câu hỏi: Lớp nào chịu trách nhiệm event agent→user, live review, request-context, approval card, artifact update, resume và UI state synchronization?

## Kết luận ngắn

AG-UI phù hợp làm transport/event vocabulary giữa AI2 và FE: run lifecycle, tool calls, state snapshot/delta, activity, reasoning summary, interrupt/resume và custom events. A2UI phù hợp như optional declarative surface cho form/card động, nhưng v1/preview status và catalog evolution làm nó chưa nên là contract bắt buộc của AI2 phase đầu.

Recommendation: AI2 công bố canonical event envelope/domain events trước; adapter AG-UI map event đó sang protocol. FE phase 1 dùng fixed allowlisted React components. Chỉ dùng A2UI cho `request-context`, `approval-card` hoặc `impact-preview` khi catalog, action binding, validation và security review đã được chốt; không cho agent tự phát code/UI arbitrary.

## Fact từ official source

1. AG-UI là streaming event-based architecture; event categories gồm lifecycle, text, tool call, state management, activity, subagent và custom/special events. Nguồn: [AG-UI events](https://docs.ag-ui.com/concepts/events) và [official repository](https://github.com/ag-ui-protocol/ag-ui) (truy cập 2026-09-23).
2. AG-UI lifecycle yêu cầu `RunStarted` và kết thúc bằng `RunFinished` hoặc `RunError`; `RunFinished` có thể biểu diễn success hoặc interrupt cần resume. Nguồn: [AG-UI lifecycle events](https://github.com/ag-ui-protocol/ag-ui/blob/main/docs/concepts/events.mdx) (truy cập 2026-09-23).
3. AG-UI state model dùng snapshot/delta: snapshot thay thế state hiện tại; delta là JSON Patch RFC 6902 áp dụng theo thứ tự; client có thể yêu cầu snapshot mới khi inconsistency. Nguồn: cùng tài liệu AG-UI, phần State Management Events.
4. AG-UI có tool call start/args/end/result với `toolCallId`, text message lifecycle và reasoning events; protocol event không tự chứng minh nội dung reasoning là an toàn để lộ. Nguồn: cùng tài liệu AG-UI, Tool Call và Reasoning sections.
5. AG-UI supports interrupt outcome với open interrupts; client resume bằng run input addressing interrupts. Đây là interaction contract, không phải durable task database. Nguồn: [AG-UI events](https://docs.ag-ui.com/concepts/events) (truy cập 2026-09-23).
6. A2UI là JSON-based streaming UI protocol; protocol tách structure/data khỏi catalog component. Renderer chỉ được dùng catalog mà nó hiểu; catalog có thể là custom để restrict component set. Nguồn: [A2UI v1.0 candidate protocol](https://github.com/a2ui-project/a2ui/blob/main/specification/v1_0/docs/a2ui_protocol.md) (truy cập 2026-09-23).
7. A2UI repository hiện cảnh báo v0.9.1 là current production release, v1.0 là release candidate và specification còn evolving. Nguồn: [A2UI official repository](https://github.com/a2ui-project/a2ui) (truy cập 2026-09-23).
8. A2UI catalog có thể giới hạn component/function; renderer phải validate catalog/version và action/input binding. Nguồn: [A2UI protocol](https://github.com/a2ui-project/a2ui/blob/main/specification/v1_0/docs/a2ui_protocol.md) (truy cập 2026-09-23).

## Phân biệt protocol và AI2 semantics

### Protocol fact

- AG-UI cung cấp event vocabulary và state synchronization primitives.
- A2UI cung cấp declarative component/surface/data-model messages.

### AI2 implementation detail

- `SEGMENTATION_PROPOSED`, `IMPACT_PREVIEW_READY`, `FACTS_READY`, `COMPARISON_READY` là domain events đã được Outcome Contract chọn; chúng không phải AG-UI standard event names.
- `HITL_REQUESTED` phải map thành interrupt/custom/activity event; payload canonical vẫn do AI2 định nghĩa.
- Citation/fact/relation payload phải giữ `snapshot_id`, `document_id`, `page/block/table`, citation IDs và state version; AG-UI/A2UI không tự tạo evidence semantics.

### Best practice

- Mỗi event có `event_id`, `run_id`, `sequence`, `state_version`, `event_type`, `created_at`, `causation_id`, `payload`, `evidence_refs` và `schema_version`.
- FE reducer áp dụng event theo sequence/state version, bỏ qua duplicate đã nhận và yêu cầu full snapshot nếu gap/out-of-order.
- `StateSnapshot` là recovery point; delta/token stream không được coi là durable reasoning state.
- Không stream chain-of-thought. Chỉ gửi reasoning summary, status, evidence, decision rationale có kiểm soát và warnings.
- User command đi qua HTTP command endpoint; event stream chỉ thông báo/đồng bộ trạng thái.

## Event map đề xuất

| AI2 domain event | AG-UI mapping | FE representation |
|---|---|---|
| `RUN_STARTED` | `RunStarted` | run header + state snapshot |
| `SEGMENTATION_PROPOSED` | activity/custom | boundary proposal card |
| `HITL_REQUESTED` | interrupt outcome/custom activity | context/approval form |
| `IMPACT_PREVIEW_READY` | activity/state delta | diff + stale impact card |
| `REVIEW_APPLIED` | custom/state delta | audit/review result |
| `RECOMPUTE_STARTED` | `StepStarted`/activity | recompute progress |
| `FACTS_READY` | activity/state snapshot/delta | fact table + citations |
| `COMPARISON_READY` | activity/state delta | comparison finding card |
| `WARNING_RAISED` | activity/custom | warning/review queue |
| `RUN_COMPLETED` | `RunFinished(success)` | terminal summary |
| `RUN_FAILED` | `RunError` | retry/support action |
| `RUN_CANCELLED` | custom + terminal outcome | cancelled state |

## A2UI boundary

Phase 1 không cần A2UI để render fixed review UI. Nếu bật A2UI sau này:

- FE đăng ký catalog allowlist gồm `Text`, `Card`, `Button`, `TextField`, `CheckBox`, diff/table/citation wrappers nội bộ.
- Agent chỉ gửi declarative surface/data; không gửi JSX/HTML/URL arbitrary hoặc function ngoài allowlist.
- Button action phải map tới known command type và qua authorization/idempotency server.
- `catalog_id`, `surface_id`, `component_id`, `state_version` và event sequence phải được validate.
- A2UI surface không được chứa raw contract data vượt tenant/actor scope.

## Failure analysis

- Reconnect sau state delta gap: FE không tự merge mù; gọi snapshot/replay từ `last_sequence`.
- Duplicate event: reducer dedupe bằng `event_id`/sequence.
- Event sai thứ tự: giữ pending buffer bounded; nếu gap không lấp được thì snapshot refresh.
- Resume cũ: server kiểm tra run/checkpoint/state version/idempotency, trả conflict nếu stale.
- User action trong A2UI giả mạo: server không tin component/action metadata từ client; chỉ nhận command schema đã đăng ký.
- Catalog mismatch: không render và báo unsupported, không fallback arbitrary component.

## Open questions

- AG-UI version nào là baseline và có cần pin commit/schema không?
- FE có cần dynamic forms thật ở phase 1 hay fixed React components đủ?
- Có được hiển thị “reasoning summary” đến mức nào theo privacy policy?
- Event replay retention bao lâu và snapshot size limit bao nhiêu?
