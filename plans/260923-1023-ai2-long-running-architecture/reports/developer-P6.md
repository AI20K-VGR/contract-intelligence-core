# Báo cáo developer P6 — AG-UI, SSE và A2UI boundary

## Kết quả

P6 đã hoàn tất ở mức `PASS_WITH_LIMITATIONS`. Boundary mới không coi kết nối SSE là nguồn sự thật của reasoning state. Event có scope tenant/run, sequence, state hash và correlation ID; client có thể reconnect bằng cursor và state hash.

## File thay đổi

- `ai-service/app/transport/events.py`
- `ai-service/app/transport/__init__.py`
- `ai-service/tests/test_p6_event_ui_convergence.py`
- `plans/260923-1023-ai2-long-running-architecture/artifacts/p6-event-ui-convergence.json`

## Hành vi đã kiểm chứng

- scope tenant/run bị kiểm tra fail-closed;
- duplicate, out-of-order và gap được phân loại;
- event được map qua allowlist AG-UI và loại bỏ `raw_contract`/`hidden_reasoning`;
- SSE chỉ đọc, có heartbeat, cursor reconnect và state hash;
- command gửi qua SSE bị từ chối;
- A2UI disabled mặc định và chỉ chấp nhận component trong allowlist khi bật;
- không thêm WebSocket.

## Kiểm thử

Focused P6: `3 passed, 1 warning`.

Regression P0-P6: `55 passed, 1 warning`.

`compileall`: PASS. Warning duy nhất là pytest không ghi được `.pytest_cache` do quyền thư mục Windows.

## Giới hạn

Đây là domain/transport adapter dependency-free, chưa phải HTTP/SSE server production. Replay thực tế vẫn do durable store P3 cung cấp; P6 chỉ đảm bảo cursor, ordering và scope convergence.
