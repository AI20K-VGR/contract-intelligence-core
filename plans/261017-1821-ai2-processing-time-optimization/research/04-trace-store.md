# R4 — Lưu trace: có cần migration không, đặt queue_wait/load/persist ở đâu, ảnh hưởng tới FE/BE

## 1. Schema trace hiện tại

- Bảng `ai2.ai2_processing_trace_events` có các cột cố định: `stage_id, status, created_ms, started_ms, duration_ms, item_count, reason_code` (`ai-service/app/db/tables.py:98-105`, `app/db/migrations/versions/0008_ai2_processing_trace.py:15-41`).
  - Không có cột JSON/extra.
  - `stage_id` là `Text` tự do, không có CHECK (`0008:22`).
  - `status` có CHECK gồm 5 giá trị (`0008:31-34`).
- Validate ở store: `reason_code` khớp `^[A-Z][A-Z0-9_]{0,63}$` (`processing_trace_store.py:16`, `:57-58`). `duration_ms`/`item_count` là int ≥ 0 (`:59-62`).
- Cổng fence khi append: job phải đang `RUNNING`, `worker_token` và `current_execution_id` phải khớp (`processing_trace_store.py:93-98` cho SQLite, `:141-148` cho Postgres).

## 2. `llm_calls` / `llm_ms_total`: có cần migration không?

| Phương án | Migration | Thay đổi xuyên service | Đánh giá |
|---|---|---|---|
| **A. Ghi vào `result_json` coverage**. `coverage.contract_graph.pairs` thêm `llm_ms_total`, `llm_ms_max`, `batch_latency_ms[]`, `cached_tokens`. Coverage cấp job thêm `llm_timing` gồm calls/ms theo operation. | **Không** | **Không**. Coverage là object mở rộng được (`ai-service/app/contracts/wire.py:252`), backend nhận `coverage: dict[str, Any]` (`backend/.../persistence.py:113`) | **Khuyến nghị** |
| B. Nhét vào cột có sẵn (`item_count` = số lời gọi, `reason_code` = `LLM_MS_12345`) | Không | Không | Lạm dụng ngữ nghĩa. FE sẽ hiển thị "`N mục`" (`ProcessingTimeline.tsx:76-78`), gây hiểu sai. **Loại** |
| C. Migration 0009 thêm `llm_calls INT NULL, llm_ms_total BIGINT NULL` | Có | **Có**. Backend kiểm tra `set(stage) != stage_keys` và raise (`backend/.../ai_adapters.py:617-620`), nên thêm key vào projection sẽ làm hỏng việc đọc trace cho tới khi backend được cập nhật | Chỉ đáng làm nếu cần hiển thị trên UI |

Chi tiết cần lưu ý cho A:
- Key thống kê của pairs chỉ được persist nếu có trong `_COUNTS` (`pair_projection.py:40-55`, dùng ở `:163`). Key mới phải được thêm vào đó, hoặc vào một khối riêng.
- Golden: `coverage.contract_graph.pairs` bị **bỏ** khỏi golden graph-on (`scripts/capture_idp_golden.py:128-130`). Nhưng `coverage.runtime = runtime.snapshot()` (`idp.py:568`) **có** trong hash golden flag-off. Nếu thêm key vào `snapshot()` (`runtime.py:453-469`) thì `test_flag_off_capture_reproduces_committed_file` (`tests/test_contract_graph_pairs_flag_regression.py:32`) đỏ. Cần chọn một trong hai:
  - (i) chỉ thêm `coverage["llm_timing"]` khi job có ít nhất 1 lời gọi LLM. Golden chạy `llm=None` nên không đổi.
  - (ii) chụp lại golden và ghi rõ diff chỉ gồm key mới.
  - Khuyến nghị (i).
- Nguồn số liệu: `trace["latency_ms"]` có trên mọi nhánh, kể cả khi lỗi (`client.py:217`, `:237`, `:242`). Gom trong `ProcessingRuntime.complete_json` sau mỗi lần `_invoke`, có lock (R1), từ trace của bản sao client theo batch. Đồng thời đọc thêm `usage.prompt_tokens_details.cached_tokens`, vì hiện client chỉ đọc `prompt/completion/total/reasoning` (`client.py:247-256`). Tên field của Chat Completions là [PRIOR], cần probe.

## 3. Điểm đặt queue_wait / snapshot-load / persist

Dòng đời job trong worker (`ai-service/app/api/main.py`):

| Mốc | Vị trí | Ghi chú |
|---|---|---|
| Enqueue | `jobs.created_ms` (`app/tools/jobs.py:234`, `:518`) | |
| Chờ slot | `with _JOB_SLOTS:` (`main.py:285`); `AI2_MAX_CONCURRENT_JOBS=1` (`docker-compose.yml:614`) | Job xếp hàng nối tiếp nhau |
| Spawn process con | `_run_isolated_job` (`main.py:321-325`); compose `process` (`docker-compose.yml:615`) | Có chi phí import app trong process con spawn [ASSUMED, chưa đo] |
| **Load/adapt snapshot** | `verify_service_envelope` + `adapt_be_ai2_processing_request` (`main.py:418-423`) | Xảy ra **trước claim**, lúc chưa có `worker_token`, nên chưa ghi trace được |
| Claim | `JOB_STORE.claim` (`main.py:431-437`; PG `jobs.py:540-551`) | Bảng jobs không có cột `claimed_ms`. Claim chỉ trả token |
| Deadline bắt đầu | `ProcessingRuntime(...)` (`main.py:461-468`, `started_at` ở `runtime.py:228-230`) | Thời gian chờ queue không tính vào deadline |
| Có trace writer | `main.py:470-478` | |
| Pipeline | `run_idp` (`main.py:482-490`) | |
| **Persist** | `complete_with_snapshot` (`main.py:496-506`; PG `jobs.py:569-597`) | Đặt `worker_token=None` và status kết thúc (`jobs.py:594`) |

Cách đặt khuyến nghị:
- **queue_wait** và **snapshot_load**:
  - Lấy `perf_counter` / `time.time()` khi vào `_execute_wire_job` và quanh bước adapt.
  - Sau khi có `trace_writer`, ghi **một event `COMPLETED` duy nhất** cho mỗi mốc, với `started_ms` là mốc thật và `duration_ms` là khoảng đã đo. Cần thêm method `record()` vào `ProcessingTraceWriter`, vì hiện chỉ có start/finish/skip (`processing_trace_store.py:288-318`).
  - Phần projection đã xử lý được event không có `STARTED` (`processing_trace_store.py:350-353`).
  - `queue_wait = entry_ms − created_ms`. Muốn tách riêng thời gian spawn thì truyền thêm `parent_dispatch_ms` qua payload/args của process con [ASSUMED].
- **persist**: **không** ghi được bằng trace sau commit, vì append sẽ bị fence (`processing_trace_store.py:145-148`, status ≠ RUNNING và token = NULL).
  - Tuyệt đối **không** ghi `STARTED persist` rồi để finish bị fence. Projection với `terminal_job=True` sẽ chuyển stage đó thành `INCOMPLETE_UNKNOWN`, và cả trace thành `INCOMPLETE_UNKNOWN` (`processing_trace_store.py:354-359`). FE khi đó hiển thị "Luồng AI2 chưa đầy đủ" (`ProcessingTimeline.tsx:24`).
  - Phương án: (a) log `ai2.job_persisted duration_ms=` và `payload_bytes=` (đơn giản nhất). (b) đo riêng `record_to_dict` + `json.dumps` (`jobs.py:584`) rồi đưa vào coverage trước commit. (c) chèn trace row ngay trong transaction của `complete_with_snapshot`, phức tạp hơn.
  - Khuyến nghị (a), cộng (b) nếu muốn có số liệu trong DB.

## 4. FE/BE xử lý `stage_id` mới

- FE `ProcessingTimeline.tsx`:
  - Label tra từ map, không có thì fallback về `'Bước xử lý AI2'` (`:4-9`, `:69`).
  - Parser FE nhận `stage_id` là chuỗi tự do (`frontend/src/api/contractGraph.ts:316`).
  - Vậy FE **không vỡ** với stage_id mới, chỉ hiển thị nhãn chung.
- **Backend mới là chỗ vỡ**: `_TRACE_STAGE_IDS = {"extraction","contract_graph_operation","contract_graph_pairs","semantic"}` (`backend/src/contract_intelligence/infrastructure/ai_adapters.py:467-469`). Gặp stage lạ thì `raise AiAdapterError("AI2 trace stage is malformed")` (`:621-625`), nên **cả trace** của job đó không đọc được.
  - Ngoài ra có trần `len(stages) > 32` (`:615`). 6–7 stage thì vẫn ổn.
- Hệ quả khi triển khai: thêm `queue_wait`/`snapshot_load` thành stage trace thì phải sửa whitelist backend (và thêm label FE) **và deploy backend trước** ai-service. Nếu không muốn đụng backend thì đưa các số này vào `result_json` (`coverage.timings`).

## Kết luận xếp hạng

1. `llm_calls`/`llm_ms_total`/`cached_tokens` → `result_json` coverage (phương án A): không migration, không đổi backend. Chỉ phát `llm_timing` khi có lời gọi để không đụng golden flag-off.
2. `queue_wait`/`snapshot_load`: nếu chỉ cần cho phân tích thì ghi vào coverage (không đổi xuyên service). Nếu cần hiện trên UI thì làm stage trace mới, sửa whitelist `ai_adapters.py:467-469` + label FE, và deploy backend trước.
3. `persist`: log có cấu trúc, cộng thời gian serialize trong coverage. Không bao giờ ghi `STARTED` cho persist.
4. Migration 0009: **không cần** cho scope P0.
