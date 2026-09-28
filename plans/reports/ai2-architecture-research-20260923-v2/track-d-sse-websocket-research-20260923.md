# Track D — SSE và WebSocket

Ngày truy cập nguồn: 2026-09-23  
Câu hỏi: Với AI2 chủ yếu tương tác ở checkpoint, nên chọn SSE, WebSocket hay hybrid HTTP command + SSE?

## Kết luận ngắn

SSE phù hợp cho server→FE progress/event stream; HTTP POST/PUT là command channel cho review/approve/edit/cancel/resume. WebSocket chỉ đáng chọn nếu yêu cầu hai chiều liên tục, tần suất command cao hoặc interactive low-latency vượt quá checkpoint model. Với AI2 hiện tại, recommendation là hybrid HTTP command + SSE, nhưng phải xây event log/replay/state snapshot trước; SSE không tự cung cấp durable recovery.

## Fact từ official source

1. WHATWG định nghĩa Server-Sent Events qua `EventSource`, MIME `text/event-stream`, named events, `id`, `retry` và `Last-Event-ID` khi reconnect. Nguồn: [WHATWG HTML Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html) (truy cập 2026-09-23).
2. MDN ghi SSE là một chiều server→client; client command không đi qua EventSource và phải dùng cơ chế khác. Event stream hỗ trợ `id`, `retry` và browser reconnect. Nguồn: [MDN Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) (truy cập 2026-09-23).
3. WebSocket cung cấp session giao tiếp hai chiều giữa browser và server qua `WebSocket` API; RFC 6455 mô tả opening handshake/framing qua TCP. Nguồn: [MDN WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API) và [RFC 6455](https://datatracker.ietf.org/doc/rfc6455/) (truy cập 2026-09-23).
4. Browser WebSocket API không có backpressure tự động; nếu message đến nhanh hơn khả năng xử lý, buffer/memory/CPU có thể tăng. Nguồn: [MDN WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API) (truy cập 2026-09-23).
5. Cả SSE `Last-Event-ID` và WebSocket reconnect không thay thế application-level authorization, replay retention, dedup hoặc state reconciliation. Đây là inference từ phạm vi protocol/API: transport chỉ giúp kết nối/stream, không sở hữu AI2 task truth.

## So sánh

| Tiêu chí | SSE | WebSocket | Hybrid HTTP command + SSE |
|---|---|---|---|
| Hướng chính | Server→client | Hai chiều | Event server→client, command HTTP |
| Checkpoint review | Đủ nếu command ít | Đủ nhưng thừa | Phù hợp nhất |
| Reconnect | Có semantics `retry`/Last-Event-ID | App tự thiết kế | SSE reconnect + HTTP fetch/replay |
| Ordering | Server stream order, app sequence vẫn cần | App message sequence vẫn cần | Domain event sequence chung |
| Idempotency | Command ngoài stream, dễ tách | Command và event cùng socket, vẫn phải idempotent | Rõ boundary, dễ test |
| Backpressure | Cần batching/throttle/server policy | Browser API không có backpressure | Cần throttle event, không stream token vô hạn |
| Proxy/LB | HTTP semantics thường đơn giản hơn nhưng phải tune buffering/idle timeout | Upgrade/sticky/idle timeout phức tạp hơn | Chỉ SSE path cần tuning |
| Auth | HTTP auth/cookie/header; EventSource header hạn chế tùy client | Handshake auth + message auth | POST auth và stream auth độc lập |
| Mobile/network | Reconnect-friendly theo browser API | App reconnect policy phức tạp hơn | Chấp nhận được cho checkpoint |
| Operational cost | Một stream + REST | Connection/session broker/state | Hai endpoint, nhưng tách trách nhiệm |
| Fit AI2 hiện tại | Tốt cho events | Chưa cần | Recommendation |

## Khi nào chọn từng phương án

### SSE

Chọn khi output chủ yếu server→client: progress, status, warnings, facts-ready, comparison-ready, approval request và terminal result. Không dùng SSE làm kênh ghi approval; command phải là authenticated HTTP mutation.

### WebSocket

Chọn khi có giao tiếp hai chiều liên tục/interactive low-latency, nhiều client command nhỏ trong một session, hoặc cần duplex protocol không tiện biểu diễn qua HTTP. Trước khi chọn phải chứng minh bằng workload/test rằng SSE + HTTP không đủ; nếu không, WebSocket thêm heartbeat, backpressure, reconnect, auth và proxy complexity.

### Hybrid HTTP command + SSE

AI2 dùng `POST /runs` hoặc existing job submit; `GET /runs/{id}/events` stream event; `POST /runs/{id}/commands` nhận `approve/reject/request-context/edit/confirm-impact/resume/cancel`; `GET /runs/{id}` trả canonical snapshot; `GET /runs/{id}/events?after=sequence` replay. Đây là inference/recommendation cho AI2, không phải một protocol standard duy nhất.

## Transport invariants

- Event IDs và sequence phải do server cấp từ durable event log.
- Reconnect dùng last acknowledged sequence; server replay hoặc snapshot nếu retention gap.
- Heartbeat chỉ giữ connection sống; không được coi heartbeat là task progress.
- Event payload không chứa chain-of-thought hoặc raw sensitive data ngoài actor scope.
- Command và event authorization tách riêng; client không được chọn tenant/run tùy ý.
- Duplicate command trả idempotent result; duplicate event FE reducer bỏ qua.
- Proxy/LB timeout, buffering, max connection và mobile sleep phải là acceptance test, không assumption.

## Recommendation cho AI2 hiện tại

Chọn hybrid HTTP command + SSE cho phase live review đầu tiên. Chưa chọn WebSocket vì codebase hiện không có duplex requirement; interaction đã chốt là checkpoint-based. Quyết định này cần được đảo lại nếu discovery hạ tầng hoặc benchmark chứng minh FE cần continuous bidirectional low-latency interaction.

## Open questions

- Browser auth dùng cookie, bearer proxy hay signed short-lived stream token?
- BE/LB idle timeout, buffering và maximum concurrent streams là bao nhiêu?
- Có cần mobile background resume không?
- Event retention/replay window và snapshot fallback được lưu ở đâu?
