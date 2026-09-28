---
id: {{id}}
type: worker
tier: L2
status: {{status}}
owner: {{owner}}
version: {{version}}
parent: {{parent}}
---

# {{title}} — Worker bất đồng bộ

> TBD — worker này xử lý việc gì, vì sao chạy async.

## 1. Trigger / sự kiện
> TBD — nguồn kích hoạt (queue, cron, event) + payload đầu vào.

## 2. Xử lý
> TBD — các bước xử lý chính (happy path).

## 3. Idempotency
> TBD — đảm bảo xử lý lặp không gây tác dụng phụ trùng.

## 4. Retry / DLQ
> TBD — chính sách retry, backoff, dead-letter queue.

## 5. Concurrency & SLA
> TBD — mức song song, thứ tự, mục tiêu thông lượng/độ trễ.

## 6. Observability
> TBD — log/metric/trace cần có để giám sát worker.
