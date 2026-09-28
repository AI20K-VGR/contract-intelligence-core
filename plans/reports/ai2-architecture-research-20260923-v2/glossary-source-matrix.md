# AI2 architecture research — glossary, source matrix và research questions

Ngày lập: 2026-09-23  
Phạm vi: AI2 long-running reasoning, HITL, protocol boundary, event transport và evaluation.  
Trạng thái: research artifact, chưa phải production contract.

## 1. Nguyên tắc đọc tài liệu

Mỗi kết luận trong bộ nghiên cứu được gắn một loại evidence:

- **Fact/spec**: được phát biểu trực tiếp trong specification, official documentation hoặc official repository.
- **Implementation detail**: hành vi/API của một framework hoặc codebase cụ thể; không tự động trở thành contract của AI2.
- **Best practice**: hướng dẫn vận hành/thiết kế được nhiều nguồn hoặc kinh nghiệm triển khai hỗ trợ; cần kiểm chứng trong context của AI2.
- **Inference/recommendation**: suy luận áp dụng vào AI2 hiện tại; phải được ghi là đề xuất và cần human approval trước implementation.

Không dùng tên protocol để suy ra semantics nghiệp vụ. AG-UI không tự tạo citation; A2A không tự tạo authorization domain; SSE không tự tạo replay; ADK không tự tạo canonical audit.

## 2. Glossary

| Thuật ngữ | Nghĩa dùng trong AI2 | Không được nhầm với |
|---|---|---|
| AI1 snapshot | JSON đầu vào hiện tại từ AI1, chứa OCR/evidence và metadata theo contract đang có | raw PDF hoặc canonical AI2 result |
| Logical document | Một hợp đồng/phụ lục hoặc phần tài liệu được AI2 đề xuất nhận diện trong một input JSON | physical file; một page riêng |
| Segmentation | Phân chia input thành logical document, kèm boundary, confidence và evidence | OCR; extraction fact |
| Boundary | Tập page/block/table hoặc evidence span định nghĩa phạm vi một logical document | UI selection không có version |
| Evidence | Dữ liệu nguồn AI2 được phép dùng để chứng minh fact/relation | user note/context |
| Citation | Con trỏ có cấu trúc tới evidence: document/page/block/table/span và snapshot | câu giải thích không có source |
| Fact | Giá trị/claim được trích xuất từ evidence, có status và citation | inference của LLM |
| Relation | Quan hệ có hướng giữa document/party/clause/fact, có loại quan hệ, confidence và evidence | similarity không giải thích được |
| Canonical domain model | Model ổn định của AI2 cho run, document, fact, relation, checkpoint, command, event và artifact | payload riêng của ADK/AG-UI |
| Run | Một lần AI2 xử lý một bộ hồ sơ, có input snapshot và generation | HTTP connection |
| Generation | Phiên bản kết quả được tạo từ input/segmentation/review version cụ thể | retry lần gửi request |
| Checkpoint | Điểm reasoning có thể dừng, lưu durable state và chờ quyết định/context | token stream hoặc UI modal |
| Human review | Người xem/đánh giá kết quả, chưa tạo approval gate bắt buộc | human approval |
| Human approval | Quyết định cho phép vượt một gate cụ thể | người chỉ mở màn hình |
| Human intervention | Người sửa/đưa context/ra lệnh làm thay đổi execution hoặc input proposal | approval thuần túy |
| Request-context | Yêu cầu reviewer bổ sung thông tin có schema và mục đích rõ | chat tự do được coi là evidence |
| Proposal | Thay đổi do AI2 đề xuất trước khi áp dụng, có before/after và impact | mutation đã được commit |
| Impact preview | Danh sách artifact bị stale, giữ nguyên hoặc cần recompute trước khi áp dụng edit | kết quả recompute |
| Stale | Kết quả không còn chứng minh được bởi input/boundary/fact generation hiện hành | kết quả sai chắc chắn |
| State version | Version optimistic-concurrency của domain state | protocol version |
| Event sequence | Số thứ tự monotonic của event trong một stream/run | timestamp, vốn có thể trùng |
| Event envelope | Metadata chung bao quanh domain event: IDs, version, sequence, actor, causation và payload | UI event riêng |
| Correlation ID | ID nối command/request với run, event, worker và audit trail | task ID duy nhất cho mọi hệ |
| Causation ID | ID của command/event trực tiếp gây ra event hiện tại | correlation ID toàn chuỗi |
| Idempotency key | Khóa để retry cùng command không tạo side effect mới | event ID tự sinh sau mutation |
| Replay | Phát lại event hoặc snapshot để client/worker tái đồng bộ | chạy lại LLM tùy ý |
| Durable state | State tồn tại qua disconnect, process restart và crash theo policy | state trong browser |
| Outbox | Bản ghi bền vững nối domain mutation với việc phát event, tránh mất notification | SSE buffer |
| Snapshot | Ảnh chụp canonical state tại sequence/version cụ thể | screenshot UI |
| AG-UI | Protocol/event vocabulary agent→user cho lifecycle, state, interrupt và activity | canonical AI2 business model |
| A2UI | Protocol declarative để stream surface/component/data tới renderer theo catalog | HTML/JS arbitrary từ agent |
| ADK | Agent Development Kit/framework candidate cho orchestration, tool và session | AI2 persistence contract |
| A2A | Protocol giao tiếp giữa agent độc lập/opaque, có task/context/artifact và lifecycle | API nội bộ bắt buộc giữa AI1–AI2 |
| SSE | Server-Sent Events, stream một chiều server→client qua HTTP | kênh command hai chiều |
| WebSocket | Kênh session hai chiều giữa client và server | durable task state |
| Hybrid command + SSE | HTTP mutation cho command, SSE cho notification/event, GET cho snapshot/replay | một protocol chuẩn duy nhất |
| Truth source | Nguồn có quyền quyết định state hiện tại: domain store/evidence snapshot, không phải FE | UI connection |
| Ground truth | Annotation được reviewer xác nhận đủ để chấm output | output AI2 chưa kiểm chứng |

## 3. Source matrix

| ID | Nguồn chính thức | Phạm vi được dùng | Loại evidence | Ghi chú/conflict |
|---|---|---|---|---|
| S-A1 | [LangGraph HITL interrupts](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/) | pause/resume, thread/checkpoint, rerun và idempotent side effect | implementation detail + best practice | Không phải protocol AI2; API có thể thay đổi theo framework |
| S-A2 | [LangGraph review tool calls](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/review-tool-calls/) | approve, edit/modify, feedback | implementation detail | Cho thấy interaction pattern, không quyết định policy reviewer AI2 |
| S-A3 | [LangGraph persistence](https://langchain-ai.github.io/langgraphjs/how-tos/cross-thread-persistence-functional/) | persistence/snapshot theo thread | implementation detail | Cần tách framework cursor khỏi domain run ID |
| S-A4 | [Temporal documentation](https://docs.temporal.io/) | durable execution sau crash/network/infrastructure failure | official product fact | Không chứng minh AI2 phải dùng Temporal |
| S-B1 | [ADK Python tools](https://github.com/google/adk-python/blob/main/src/google/adk/tools/__init__.py) và [BaseTool](https://github.com/google/adk-python/blob/main/src/google/adk/tools/base_tool.py) | long-running function tool | implementation detail | Cần pin version và test behavior trước khi adapter |
| S-B2 | [ADK session state](https://github.com/google/adk-docs/blob/main/docs/sessions/state.md) | event/session state delta | implementation detail | Không thay thế audit/legal evidence store |
| S-B3 | [ADK HITL reference](https://github.com/google/adk-python/blob/main/.agents/skills/adk-agent-builder/references/human-in-the-loop.md) | resume input và multi-step input | implementation detail | Không phải canonical AI2 state machine |
| S-B4 | [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) | agent boundary, task/context/artifact, security | spec fact | Authorization scope vẫn do deployment định nghĩa |
| S-B5 | [A2A life of a task](https://a2aproject.github.io/A2A/latest/topics/life-of-a-task/) | task lifecycle, status, artifact, cancel/retrieve | spec fact | Notification/push không thay thế source-of-truth read |
| S-C1 | [AG-UI events](https://docs.ag-ui.com/concepts/events) | lifecycle, tool, state, activity, interrupt | protocol fact | Domain payload/citation vẫn do AI2 định nghĩa |
| S-C2 | [AG-UI event specification](https://github.com/ag-ui-protocol/ag-ui/blob/main/docs/concepts/events.mdx) | snapshot/delta, ordering, resume | protocol fact | Phải pin schema/version khi tích hợp |
| S-C3 | [A2UI protocol](https://github.com/a2ui-project/a2ui/blob/main/specification/v1_0/docs/a2ui_protocol.md) | catalog/surface/component/data/action | protocol fact | v1.0 còn release candidate theo repository |
| S-C4 | [A2UI repository](https://github.com/a2ui-project/a2ui) | version maturity | official repository fact | v0.9.1 current production, v1.0 evolving tại thời điểm truy cập |
| S-D1 | [WHATWG Server-Sent Events](https://html.spec.whatwg.org/multipage/server-sent-events.html) | EventSource, id/retry/Last-Event-ID | web standard fact | Reconnect không tạo domain replay |
| S-D2 | [MDN SSE](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) | one-way stream và browser behavior | implementation guidance | Client command phải qua kênh khác |
| S-D3 | [MDN WebSocket](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API) | duplex, no browser backpressure | platform documentation | Backpressure phải do app xử lý |
| S-D4 | [RFC 6455](https://datatracker.ietf.org/doc/rfc6455/) | handshake/framing | standard fact | Không định nghĩa AI2 authorization/replay |

Ngày truy cập toàn bộ nguồn: **2026-09-23**. Các link trên là source trực tiếp, không dùng search-result page làm evidence.

## 4. Research questions còn phải trả lời trong implementation discovery

1. BE hiện dùng database/queue/worker nào để sở hữu lease, scheduler và fencing?
2. Phase 1 approval policy là named reviewer, any-one hay all-required?
3. TTL của pending checkpoint/approval là bao lâu; hết hạn thì reopen hay tạo request mới?
4. FE cần dynamic form thật hay fixed allowlisted React components đủ cho phase đầu?
5. Có yêu cầu mobile background resume và giới hạn concurrent SSE nào không?
6. AG-UI baseline/version và event schema có được pin theo package/commit nào?
7. Có roadmap expose AI2 qua network boundary để cần A2A trong 12 tháng không?
8. Fact edit được phép đổi value hay chỉ đổi classification/boundary/relation?
9. Retention của raw contract, evidence, event và audit có cùng policy không?
10. Dataset nào sẽ được reviewer xác nhận để tạo ground truth; ai có quyền adjudicate disagreement?
11. Ngưỡng completeness/citation correctness nào đủ để cho phép publish kết quả?
12. External LLM/tool nào được phép gọi, dữ liệu nào phải mask, và tool nào bị cấm side effect?

## 5. Known / inference / missing data

### Biết chắc từ codebase và nguồn

- AI2 hiện nhận AI1 JSON qua adapter/schema và có pipeline extraction/relation/citation/query bounded.
- Runtime hiện chưa có durable HITL state machine, event replay, SSE, WebSocket, AG-UI, A2UI, A2A hoặc ADK integration.
- Các protocol được nghiên cứu đều không tự thay thế domain persistence, authorization, evidence provenance hoặc audit.

### Inference/đề xuất

- BE-owned canonical state + durable event/outbox + HTTP command + SSE là fit ban đầu cho checkpoint interaction.
- A2A nên để sau; ADK chỉ nên đi qua adapter.
- Fixed allowlisted FE components nên đi trước A2UI dynamic surfaces.

### Còn thiếu dữ liệu

- Hạ tầng production, SLO, concurrency, retention, auth model, worker/queue và mobile requirements.
- Ground truth nghiệp vụ đủ rộng cho nhiều loại hợp đồng/phụ lục.
- Quyền reviewer, policy conflict và tiêu chí publish cuối cùng.
