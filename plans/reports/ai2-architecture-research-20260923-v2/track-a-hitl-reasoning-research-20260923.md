# Track A — HITL reasoning và durable execution

Ngày truy cập nguồn: 2026-09-23  
Câu hỏi: Làm thế nào để AI2 dừng ở checkpoint, chờ reviewer, nhận context/approval/edit, tiếp tục sau nhiều giờ/ngày và không mất evidence, audit hoặc idempotency?

## Kết luận ngắn

AI2 cần một state machine durable do BE/workflow persistence sở hữu; UI connection chỉ là consumer. Một human checkpoint phải lưu snapshot input, state version, pending request, allowed response schema, expiry, actor policy và event/audit record. Resume phải tham chiếu đúng run/checkpoint, dùng idempotency key và thực hiện compare-and-swap trên state version. Side effect trước checkpoint phải idempotent hoặc nằm sau approval.

LangGraph là bằng chứng implementation pattern rõ về interrupt/checkpointer/thread ID/resume; Temporal là bằng chứng về durable execution sau crash/network failure. Hai nguồn này không phải protocol bắt buộc cho AI2. Đây là implementation evidence và best practice, không phải lý do tự động chọn framework.

## Phân loại evidence

### Fact từ tài liệu/specification/official docs

1. LangGraph `interrupt()` cho phép pause graph để nhận external input; state được persistence layer lưu và run tiếp tục bằng `Command(resume=...)`. Resume dùng cùng `thread_id`; payload interrupt phải JSON-serializable. Nguồn: [LangGraph HITL interrupts](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/) (truy cập 2026-09-23).
2. LangGraph node chạy lại từ đầu khi resume; side effects trước interrupt có thể chạy lại, nên tài liệu yêu cầu side effect phải idempotent hoặc đặt sau interrupt. Nguồn: cùng tài liệu, phần “Side effects called before interrupt must be idempotent”.
3. LangGraph hỗ trợ các interaction approve, modify/edit và feedback; request và resume value là application-defined. Nguồn: [Review tool calls](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/review-tool-calls/) (truy cập 2026-09-23).
4. LangGraph có state snapshot/delta và interrupt stream, nhưng việc bảo toàn/triển khai durable checkpoint phụ thuộc checkpointer/deployment, không phải chỉ do stream connection. Nguồn: [LangGraph persistence](https://langchain-ai.github.io/langgraphjs/how-tos/cross-thread-persistence-functional/) và [streaming interrupts](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/).
5. Temporal mô tả durable execution là khả năng workflow resume sau crash, network failure hoặc infrastructure outage trong thời gian dài. Nguồn: [Temporal documentation](https://docs.temporal.io/) (truy cập 2026-09-23).
6. A2A specification có trạng thái task và authorization mid-task, nhưng phần A2A chi tiết thuộc Track B; HITL domain không được suy ra chỉ từ transport.

### Implementation detail

- `interrupt()`/`Command` là API của LangGraph; `thread_id` là cursor của LangGraph, không phải tên bắt buộc trong AI2.
- Temporal workflow history/worker semantics là implementation của Temporal, không phải requirement tối thiểu của AI2.
- AI2 có thể tự xây state machine trên PostgreSQL/SQLite/queue mà không phụ thuộc hai framework trên.

### Best practice

- Persist immutable `run_input_ref` và `state_snapshot_ref`, không serialize raw LLM chain-of-thought vào client.
- Tách `human_review`, `human_approval`, `human_intervention`: review là quan sát/đánh giá; approval là quyết định gate; intervention là chỉnh state/proposal hoặc cung cấp context.
- Mỗi pending request có `request_id`, `run_id`, `checkpoint_id`, `state_version`, `expires_at`, `allowed_actions`, `required_role` và evidence refs.
- Mỗi command có `correlation_id`, `idempotency_key`, `actor_id`, `actor_role`, `submitted_at`, `reason`, `expected_state_version`; command đã apply trả cùng result khi retry.
- Approval/rejection không được chỉ lưu cờ hiện tại; phải có append-only audit record và decision snapshot.
- Khi nhiều actor thao tác cùng checkpoint, chỉ một transition thắng theo optimistic concurrency; command thua trả conflict/stale, không silently overwrite.
- Timeout/expiration phải là state transition có event/audit, không chỉ là query-time calculation.
- Recompute sau boundary/fact edit phải tạo generation mới; output generation cũ stale và không được publish.

## Mô hình HITL đề xuất cho AI2

```text
CREATED
  -> RUNNING
  -> WAITING_FOR_HUMAN {checkpoint, request-context, impact/approval}
  -> RESUMING {accepted command, new state_version}
  -> RECOMPUTING {new generation}
  -> COMPLETED | NEEDS_REVIEW | FAILED | CANCELLED | EXPIRED
```

`PAUSED` có thể là operational substate của `WAITING_FOR_HUMAN`; không nên dùng `PAUSED` để thay thế pending request vì UI cần biết đang chờ loại input nào. State machine phải validate transition ở server, không tin state do FE gửi.

### Context request

Request context không phải evidence. Reviewer text, note hoặc proposed boundary là user-provided annotation; nó phải lưu actor/time/source và chỉ được dùng để tạo proposal/candidate input. Evidence fact vẫn phải trỏ AI1 citation. Nếu user context mâu thuẫn source, output phải hiển thị conflict và yêu cầu quyết định, không nâng user text thành source truth.

### Edit proposal

Đề xuất sửa gồm before/after, target path, source basis, impact set và operation type. Không sửa raw AI1 JSON. `impact_preview` phải trả danh sách result IDs bị stale, result IDs giữ được, bước cần recompute và ước lượng resource trước khi reviewer confirm.

## Failure analysis

| Failure | Required behavior |
|---|---|
| Reviewer không phản hồi | Giữ `WAITING_FOR_HUMAN`; reminder/expiration là policy riêng; không auto-approve |
| Input thiếu context | Reject command ở validation layer hoặc tạo request bổ sung; không resume partial state |
| Reject | Ghi actor/reason/audit; chuyển branch/replan hoặc terminal `REJECTED/NEEDS_REVIEW` theo policy |
| Edit proposal | Validate schema/scope; tạo generation mới; impact preview trước recompute |
| Crash/restart | Load durable snapshot + event cursor; tiếp tục đúng checkpoint, không chạy side effect trùng |
| Duplicate resume | Idempotency key trả kết quả cũ; không tạo generation/event duplicate |
| Out-of-order command | `expected_state_version` fail; FE fetch snapshot mới |
| Timeout | Ghi timeout event; không coi là approval |
| Two users approve/reject | Atomic compare-and-swap; một decision thắng, decision kia conflict/audit |
| Cancellation | Cancellable transition kiểm tra quyền; running side effect cần compensation/abort policy |
| Expired approval | Không nhận resume cũ; yêu cầu request mới với checkpoint/generation mới |

## Recommendation cho AI2 hiện tại

Chọn domain-owned state machine + durable BE persistence trước. ADK/LangGraph/Temporal chỉ là adapter/runtime candidate sau khi canonical state/event model đã ổn định. Không để framework-specific interrupt object trở thành public AI1→AI2 contract. Tối thiểu phải có deterministic transition reducer, snapshot store, append-only command/audit log và outbox/event cursor.

## Open questions

- BE dùng PostgreSQL + queue nào và ai sở hữu scheduler/lease/fencing?
- Approval một người ở phase 1 là `any-one`, `all-required` hay `named-reviewer`?
- Expiration mặc định bao lâu; sau expiration là `EXPIRED`, reopen hay tạo request mới?
- Reviewer có được sửa fact value hay chỉ sửa classification/boundary/relation?
- Audit retention và quyền đọc raw contract/audit khác nhau thế nào?
