# Kế hoạch Backend: chuyển Backend ↔ AI2 sang Kafka

| Trường | Nội dung |
|---|---|
| Ngày | 30/09/2026 |
| Người viết | Chương (Backend) |
| Contract | [DOC-05e v2](../../docs/DOC-05e-kafka-ai2-idp-contract.md), [BE-AI2-PROCESSING-CONTRACT](../../docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md) |
| Nhánh | `feature/sprint3-backend` |
| Thời gian | Sprint 3 (05/10 – 18/10). Không đụng tới bản demo Sprint 2 (đóng băng 02/10) |

## 1. Hiện trạng (code)

- `worker.py` `_run_ai2_if_ready` build request → `submit_ai2_processing` (HTTP, ký HMAC) → `poll_ai2_processing` tới hết deadline, trong một background task (`_schedule_ai2`, `_ai2_tasks`, `_ai2_semaphore`).
- Timeout nằm trong vòng poll; restart worker thì `_resume_pending_ai2` submit lại mọi run `EXTRACTED`.
- Đã có sẵn và dùng lại được: vòng consume có retry + DLQ + `processed_event` (`_process_record`), watchdog AI1 (`run_ai1_watchdog`), đọc kết quả qua MinIO có kiểm tra `uri`/size/sha256 (`_load_ai1_result_ref`), `_finalize_ai2_success`, `_fail_ai2_run`, `_reopen_for_ai2_retry`.
- Phía AI2 đã có `app/transport/kafka_idp_worker.py` nhưng: chỉ nhận body-only, dùng lại `event_id` của command cho result, dedupe in-memory, lỗi tạm thì bỏ qua offset (mất command), không có `max_poll_interval_ms`. Các điểm này nằm trong checklist DOC-05e §13 cho AI2.

## 2. Nguyên tắc

- Không đổi hai schema payload. Mọi thứ riêng của Kafka nằm ở envelope.
- Giữ HTTP làm fallback qua cờ `AI2_TRANSPORT` (`http` | `kafka`) cho tới khi E2E xanh.
- Dispatch là việc ngắn (build + ký + upload + publish), chạy ngay trong handler; bỏ background task và semaphore khi chạy Kafka.
- Mọi handler idempotent theo DB; Kafka chỉ đảm bảo at-least-once.

## 3. Các bước

### B1. Cấu hình, topic, compose — 0,5 ngày

- `config/settings.py`: thêm `ai2_transport`, `kafka_ai2_idp_commands_topic`, `kafka_ai2_idp_results_topic`, `kafka_backend_ai2_results_group_id`, `kafka_ai2_inline_max_bytes`, `kafka_ai2_queue_timeout_seconds`, `ai2_result_max_bytes`; đổi `ai2_poll_grace_seconds` → `ai2_result_grace_seconds` (giữ alias env cũ một sprint).
- `docker-compose.yml`: service init tạo 4 topic (DOC-05e §2) với số partition cố định; env mới cho `backend-worker`; service `ai2-worker` (AI2 làm, Backend review).
- `.env.example` và `deploy/`: thêm biến, `AI2_TRANSPORT=http` mặc định.

### B2. Storage cho AI2 — 0,5 ngày

- `infrastructure/storage.py`: `ai2_object_key(dossier_id, run_id, attempt, name)` và `ai2_object_uri(...)` theo đường `ci-render/{dossier}/ai2/{run}/attempt-{n}/{request|result}.json`.
- Tổng quát hoá `_load_ai1_result_ref` thành `_load_result_ref(ref, expected_uri, max_bytes, code)` dùng chung cho AI1 và AI2.
- Purge hồ sơ (`dossier_deletion_service.py`) xoá prefix `{dossier_id}/ai2/`.

### B3. Dispatch command — 1,5 ngày

Hàm mới `_dispatch_ai2_command(session, dossier_id, tenant_id, run_id)` thay phần submit/poll trong `_run_ai2_if_ready` khi `AI2_TRANSPORT=kafka`:

1. Giữ nguyên các kiểm tra hiện có: job `EXTRACTED`, manifest `confirmed`, chưa có `ai2_result_digest`, đủ snapshot.
2. Thêm kiểm tra đúng một member `body`; sai thì `FAILED` với `AI2_DOSSIER_INVALID` (không retry được).
3. Nếu run đã có `ai2_dispatch` cho attempt hiện tại thì không gửi lại (redelivery, restart).
4. Build request như cũ, ký `service_envelope` (tách hàm ký khỏi `submit_ai2_processing` để dùng chung).
5. Serialize; lớn hơn `KAFKA_AI2_INLINE_MAX_BYTES` thì upload lên MinIO và tạo `payload_ref`. Luôn tạo `result_target` (presigned PUT).
6. Ghi vào `pipeline_run.config_snapshot`: `ai2_dispatch = {attempt, event_id, dispatched_at, queue_deadline_at, request_uri?, result_uri}`; step S4 = `queued`; commit.
7. Publish `ai2.idp.command` key `dossier_id`. Publish lỗi → `FAILED` với `AI2_DISPATCH_FAILED` (thêm vào `AI2_RETRYABLE_ERRORS`).

`_schedule_ai2` rẽ nhánh theo `AI2_TRANSPORT`: `kafka` thì gọi thẳng dispatch trong session của handler; `http` giữ nguyên code cũ. `_resume_pending_ai2` khi `kafka` chỉ dispatch các run `EXTRACTED` chưa có `ai2_dispatch` cho attempt hiện tại.

`_ai2_query_snapshot_digest` vẫn giữ để tính digest cho `/query` cho tới khi AI2 trả `query_snapshot_digest` trong result (DEC D10, việc A1).

### B4. Consumer kết quả — 2 ngày

- `run_ai2_results_consumer`: giống `run_ai1_results_consumer` (manual commit, `max_partition_fetch_bytes` = `KAFKA_MAX_MESSAGE_BYTES`), DLQ `ci.ai2.idp.results.dlq`, thêm vào `asyncio.gather` trong `run_consumer` chỉ khi `AI2_TRANSPORT=kafka`.
- `handle_ai2_result(session, message)`:
  1. Dedupe `processed_event` theo `event_id` (consumer `ai2_results`).
  2. Đọc `correlation`; `run_id` phải là `current_run_id` của job và `attempt` phải bằng attempt hiện tại của run. Sai → audit `ai2.result_late`, bỏ qua.
  3. `ai2.idp.started` → S4 `running`, ghi `started_at` và `run_deadline_at = started_at + max_processing_seconds + grace` vào `ai2_dispatch`; commit.
  4. `completed` / `failed`: lấy payload inline hoặc qua `result_ref` (chỉ nhận đúng `result_uri` đã phát). Kiểm tra `idempotency_key`, `attempt`, `input_snapshots[]` khớp request → sai là `AI2_RESULT_MISMATCH`.
  5. `completed` → `_finalize_ai2_success(source="kafka")`; result có `query_snapshot_digest` thì lưu nguyên giá trị đó thay cho digest tự tính (DEC D10).
  6. `failed` → `_fail_ai2_run` với `AI2_PROCESSING_FAILED` nếu `errors[0].retryable`, ngược lại `AI2_REQUEST_REJECTED`; mã gốc của AI2 vào `audit_detail`.
- Payload không đúng shape (thiếu `correlation`, `event_type` lạ) → raise để vào DLQ, không đoán.

### B5. Watchdog AI2 — 1 ngày

- `fail_overdue_ai2_runs(session, now)`: tìm job `EXTRACTED` có `ai2_dispatch` của attempt hiện tại; quá `queue_deadline_at` khi chưa có `started_at`, hoặc quá `run_deadline_at` khi đã có → `_fail_ai2_run(code="AI2_TIMEOUT")`, audit ghi phase (`queued`/`running`) và số giây đã chờ.
- Gộp vào vòng watchdog hiện có (đổi tên `run_ai1_watchdog` → `run_watchdog`, gọi cả hai).

### B6. Retry và trạng thái — 0,5 ngày

- `AI2_RETRYABLE_ERRORS` = `AI2_PROCESSING_FAILED`, `AI2_TIMEOUT`, `AI2_DISPATCH_FAILED`, `AI2_RESULT_UNREADABLE`. `AI2_REQUEST_REJECTED`, `AI2_DOSSIER_INVALID`, `AI2_RESULT_MISMATCH` không retry.
- `_reopen_for_ai2_retry` giữ nguyên (attempt + 1); dispatch sau đó tạo command mới, URL MinIO mới.
- Giới hạn 3 attempt cho một run (theo đề xuất D7 cũ); quá thì từ chối retry kèm lý do.
- Mapping trạng thái hồ sơ giữ như hiện tại (`PENDING_REVIEW` khi thành công). Việc tách "AI2 xong" và "chờ duyệt" là quyết định của Lead, không nằm trong kế hoạch này.

### B7. Test — 2 ngày (làm song song B3–B6)

Unit (`backend/tests/unit/`), dùng producer giả như test hiện có:

- Dispatch: inline vs `payload_ref` theo ngưỡng; không gửi lại khi đã có `ai2_dispatch`; hai body → `AI2_DOSSIER_INVALID`; publish lỗi → `AI2_DISPATCH_FAILED`.
- Consumer: `started` cập nhật deadline; `completed` inline và qua ref; ref sai `uri`, sai sha256, quá cỡ; attempt cũ và run cũ bị bỏ qua; `event_id` lặp; `failed` retryable và không retryable; `query_snapshot_digest` có và chưa có.
- Watchdog: hết hạn khi đang xếp hàng, khi đang chạy; không động vào run chưa dispatch.
- Contract test: command sinh ra hợp lệ với `be.ai2.processing.request.v1.schema.json`; fixture result hợp lệ với `ai2.be.processing.result.v1.schema.json`.

Integration (compose, Kafka thật, AI2 giả trả kết quả cố định):

- Hồ sơ 20 trang; hồ sơ body + annex; hồ sơ ~200 trang đi đường `payload_ref`.
- Kill worker AI2 giữa chừng → watchdog `AI2_TIMEOUT` → retry attempt 2 → kết quả attempt 1 đến muộn bị bỏ qua.
- Restart `backend-worker` sau khi dispatch → không gửi command thứ hai.

### B8. Tài liệu và dọn dẹp — 0,5 ngày

- DOC-09 (SAD): sửa đoạn "AI2 chỉ có một đường HTTP" và quyết định D4.
- `HUONG-DAN-TEST-E2E-UPLOAD.md`, `backend/README.md`: cách chạy với `AI2_TRANSPORT=kafka`, cách xem topic và DLQ.
- Sau khi mặc định chuyển sang `kafka` một sprint: xoá `submit_ai2_processing`/`poll_ai2_processing` khỏi worker, `_ai2_tasks`, `_ai2_semaphore`, và bộ hàm trùng `submit_idp_job`/`get_idp_job`/`poll_idp_job`/`build_idp_request` trong `ai_adapters.py`.

## 4. Lịch

| Ngày | Việc | Cổng |
|---|---|---|
| 01/10 – 03/10 | AI2 duyệt DOC-05e §13 | Contract `accepted` |
| 05/10 – 07/10 | B1, B2, B3 | Unit dispatch xanh |
| 08/10 – 10/10 | B4, B5, B6 | Unit consumer và watchdog xanh |
| 12/10 – 14/10 | B7 integration với AI2 giả, rồi với `ai2-worker` thật | 4 kịch bản E2E xanh |
| 15/10 | Đổi mặc định `AI2_TRANSPORT=kafka` trên bản online | Demo chạy qua Kafka |
| 16/10 – 18/10 | B8, đo thời gian và ghi vào DOC-06 | — |

Tổng Backend khoảng 8,5 ngày công.

## 5. Phụ thuộc phía AI2

Backend làm được tới hết B7 với AI2 giả. Để bật trên bản online cần AI2 xong DOC-05e §13: nhận full dossier, `payload_ref`/`result_target`, `started`, dedupe bền theo `(idempotency_key, attempt)`, lỗi tạm trả `failed` có `retryable`, `max_poll_interval_ms`, service `ai2-worker` trong compose.

## 6. Rủi ro

| Rủi ro | Xử lý |
|---|---|
| AI2 chưa kịp sửa worker trước 12/10 | Giữ `AI2_TRANSPORT=http` cho demo; Kafka chạy song song trên local |
| Commit DB xong nhưng publish lỗi | Run `FAILED` với `AI2_DISPATCH_FAILED`, retry được; không có run treo |
| Publish xong nhưng commit lỗi | Handler retry sẽ dispatch lại cùng attempt; AI2 dedupe theo `(idempotency_key, attempt)` |
| Nhiều hồ sơ xếp hàng, AI2 chỉ một worker | Deadline hàng đợi tách riêng; tăng số `ai2-worker` tối đa bằng số partition |
| Digest `/query` lệch nếu AI2 đổi cách hash | Dùng `query_snapshot_digest` AI2 trả trong result (DEC D10); có test so digest với AI2 thật trong E2E |
