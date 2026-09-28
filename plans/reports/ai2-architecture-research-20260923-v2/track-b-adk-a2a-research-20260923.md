# Track B — ADK và A2A

Ngày truy cập nguồn: 2026-09-23  
Câu hỏi: ADK và A2A nên nằm ở lớp nào của AI2, hỗ trợ long-running lifecycle ra sao, và tại sao chưa nên dùng A2A làm AI1→AI2 contract hiện tại?

## Kết luận ngắn

ADK phù hợp để thử nghiệm orchestration/tool/HITL trong một agent workflow, nhưng không nên sở hữu canonical AI2 task state nếu BE cần durability, audit, tenant authorization và migration độc lập. A2A là protocol cho giao tiếp giữa các agent độc lập/opaque, có task/context/artifact, polling, streaming và push notification. AI1→AI2 hiện là service processing boundary với schema đã biết, không phải agent-to-agent delegation; do đó A2A hiện làm tăng protocol surface mà chưa giải quyết nhu cầu chính.

Recommendation: giữ BE-owned `AI2Run`/task state và HTTP processing contract; tạo `ADKAdapter` nội bộ ở phase sau nếu ADK thực sự được chọn. Chỉ thêm `A2AAdapter` khi AI2 cần expose capability cho agent độc lập bên ngoài hoặc cần handoff nhiều agent qua boundary có discovery/authentication.

## Fact từ official source

1. ADK Python có `LongRunningFunctionTool`; source chính thức đánh dấu long-running tool có thể trả resource ID trước và hoàn tất sau. Nguồn: [ADK Python tools export](https://github.com/google/adk-python/blob/main/src/google/adk/tools/__init__.py) và [BaseTool](https://github.com/google/adk-python/blob/main/src/google/adk/tools/base_tool.py) (truy cập 2026-09-23).
2. ADK session lưu event history/state; state changes được đưa vào event state delta và SessionService persistence. Nguồn: [ADK session state](https://github.com/google/adk-docs/blob/main/docs/sessions/state.md) (truy cập 2026-09-23).
3. ADK official repository có pattern HITL với `LongRunningFunctionTool` và resume inputs cho multi-step input. Nguồn: [ADK human-in-the-loop reference](https://github.com/google/adk-python/blob/main/.agents/skills/adk-agent-builder/references/human-in-the-loop.md) (truy cập 2026-09-23).
4. A2A định nghĩa giao tiếp giữa các independent/opaque agent systems, hỗ trợ message, task, context, artifacts, streaming và asynchronous push notification cho long-running tasks. Nguồn: [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) (truy cập 2026-09-23).
5. Trong A2A, `taskId` định danh task; `contextId` nhóm các task/message liên quan. Task lifecycle có status update/artifact update; có operation cancel và task retrieval. Nguồn: [A2A life of a task](https://a2aproject.github.io/A2A/latest/topics/life-of-a-task/) và [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) (truy cập 2026-09-23).
6. A2A yêu cầu production transport mã hóa; client/server authentication và authorization dựa trên web security practices. Server phải scope mọi operation theo caller authorization boundary; tenant/role/project/custom authorization là implementation-defined. Nguồn: [A2A security and authorization](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) (truy cập 2026-09-23).
7. A2A `AUTH_REQUIRED`/authorization state không tự có nghĩa là operation cụ thể đã được cấp quyền; scope/validity/revocation phải do implementation hoặc extension định nghĩa. Nguồn: cùng specification, phần in-task authorization.

## Implementation detail vs inference

### Implementation detail

- ADK `LongRunningFunctionTool`, `SessionService`, event state delta và callback API là ADK-specific.
- A2A JSON-RPC methods, AgentCard, `Task`, `TaskStatusUpdateEvent`, `TaskArtifactUpdateEvent`, SSE/push binding là A2A-specific.
- `correlation_id` không phải tên field duy nhất được A2A bắt buộc cho mọi AI2 use case; AI2 vẫn nên có correlation ID nội bộ để nối BE request → run → event → audit.

### Best practice

- Đừng dùng ADK session history làm toàn bộ audit/legal evidence. Lưu canonical AI2 state/evidence refs bên ngoài và đưa snapshot ID/version vào ADK context.
- Đừng coi A2A `Task` là authorization. Authorization phải kiểm tra ở gateway và mỗi operation.
- Handoff retry phải có task idempotency, causation/correlation IDs, dedup và artifact digest.
- Agent boundary chỉ nên mở khi capability, ownership, security principal, data scope và failure contract đã rõ.
- Callback/push notification là notification, không phải source of truth; client vẫn cần `get task/status` hoặc resume cursor.

## Lifecycle mapping cho AI2

| AI2 concept | ADK candidate | A2A equivalent | Ownership đề xuất |
|---|---|---|---|
| `run_id` | invocation/session reference | task/context lineage | BE canonical run ID |
| checkpoint | session/event state | task status/artifact snapshot | BE/workflow store |
| waiting reviewer | long-running/HITL tool | `input-required`/auth-required extension policy | AI2 domain + BE |
| resume | resume input/tool response | send message/update task | authenticated command endpoint |
| progress | ADK events/callbacks | status/artifact events | durable event log then transport |
| cancel | runner/tool cancellation policy | cancel task operation | BE authorization + worker fence |
| retry | tool/agent retry | new or same task per policy | idempotency at domain boundary |

## Vì sao chưa dùng A2A giữa AI1 và AI2

- AI1 hiện chỉ trả evidence JSON; AI2 cần schema validation và provenance, không cần discovery giữa opaque agents.
- BE đã là caller được authenticate và có processing request/result schemas; A2A sẽ thêm AgentCard, task history, A2A error mapping và interoperability tests.
- A2A không định nghĩa semantics của contract segmentation, citation correctness, fact grounding, reviewer approval hay legal precedence; các semantics này vẫn phải do AI2 contract sở hữu.
- Nếu AI1/AI2 cùng một product boundary và BE điều phối, A2A không tự tạo durability; task store/worker/audit vẫn phải xây.

## Khi nào A2A trở nên hợp lý

- AI2 exposed như agent độc lập cho hệ thống/tenant khác.
- Nhiều agent chuyên biệt (segmentation, extraction, comparison, legal-policy) do team/vendor khác nhau sở hữu.
- Cần capability discovery và handoff task/artifact qua network boundary.
- Có team chịu trách nhiệm AgentCard, auth scopes, tenant isolation, task history, event/push compatibility và conformance tests.

## Rủi ro cần kiểm chứng

- ADK/A2A version drift và behavior ở long-running tool completion; không dựa vào issue/discussion như normative fact.
- Framework state compaction hoặc rerun có thể lặp side effect; phải kiểm tra thực nghiệm trước khi chọn runtime.
- A2A push callback có thể duplicate/out-of-order/mất mạng; cần pull/replay path.
- Multi-tenant auth không được phó mặc cho `contextId`/`taskId`; mọi task read/write phải scope theo principal.

## Open questions

- Team có cam kết dùng Google ADK hay chỉ nghiên cứu pattern?
- AI2 có cần expose ra ngoài process/organization trong roadmap 12 tháng không?
- Nếu có nhiều agent, ai sở hữu canonical evidence và final comparison state?
- BE có sẵn worker/queue và tracing propagation để làm task owner chưa?
