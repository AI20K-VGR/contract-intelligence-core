# R1 — Thread-safety của ProcessingRuntime / NineRouterClient khi chạy song song

Phạm vi: các trạng thái dùng chung khi `classify_pairs` gọi `runtime.complete_json` từ nhiều thread cùng lúc. Chỉ đọc code, chưa chạy probe tải.

## 1. Bảng trạng thái chia sẻ

| Thành phần | Vị trí | Hiện trạng khi nhiều thread | Có cần lock? |
|---|---|---|---|
| `llm_calls_used` (bước tăng) | `ai-service/app/pipeline/runtime.py:411-421` | Tăng **bên trong** `_request_lock` (`runtime.py:412`, `:420`). Đây là cổng cứng duy nhất. | Đã có lock, giữ nguyên |
| `llm_calls_used` (bước kiểm tra trước) | `runtime.py:343`, `runtime.py:386`, `pair_classifier.py:377`, `pair_builder.py:68` | Đọc int không có lock. Chỉ là kiểm tra trước, có thể cũ, nhưng không gây vượt budget vì `_reserve_http_request` kiểm tra lại dưới lock. | Không |
| `max_llm_calls` | `runtime.py:207` | Chỉ đọc | Không |
| `remaining()` / `deadline` | `runtime.py:232-237` | Hàm thuần: `started_at` cố định cộng `clock()` | Không |
| `issues` + `add_issue` | `runtime.py:258-260` | Kiểm tra rồi mới append, không lock. Hai thread fallback cùng mã có thể tạo **bản ghi trùng** trong `issues`, rồi đi vào `_runtime_issues` (`idp.py:766-775`). | **Có** |
| `fallback_count += 1` | `runtime.py:264` | Read-modify-write không atomic, có thể mất cập nhật. Giá trị này đi vào `snapshot()` (`runtime.py:468`). | **Có** |
| `provider_exhausted` | set ở `runtime.py:371`, chỉ check ở `runtime.py:332` | Ghi bool thì an toàn. Tuy nhiên một thread đang ngủ backoff (`runtime.py:396`) sẽ vẫn gửi request tiếp, vì `_reserve_http_request` không kiểm tra cờ này. | Nên check cờ trong `_reserve_http_request` |
| `report_progress` → `on_progress` | `runtime.py:239-252`, closure `main.py:391-411` | Closure dùng dict `last` không có lock và ghi DB (`JOB_STORE.set_wire`). Nếu gọi từ nhiều thread, `done` có thể lùi và có thể có hai lần ghi DB cùng lúc. | Gọi **chỉ từ thread điều phối** |
| `_log_call` | `runtime.py:156-172` | Đọc `client.traces[-1]` (`runtime.py:158-159`), mà phần tử cuối có thể thuộc thread khác, nên log sai latency/model. | Nên dùng trace riêng cho mỗi lời gọi |
| `NineRouterClient.last_http_calls` | `client.py:182`, `:202`, `:226`, `:243` | Thuộc tính instance bị reset về 0 ở đầu mỗi lời gọi. Thread B reset giữa chừng làm `trace["http_calls"]` của thread A sai. | Nên đổi thành biến local |
| `NineRouterClient.traces` (list) | `client.py:150`, append ở `:218/:238/:262/:269/:273` | Trên CPython 3.12 (có GIL; venv là `3.12.13`) `list.append` là atomic. Nhưng **thứ tự xen kẽ** làm sai phép cắt theo chỉ số ở `pair_classifier.py:408` và `:427` (xem R2). | Append không cần lock; cách đọc theo chỉ số thì phải sửa |
| `NineRouterClient.all_traces` (deque, thuộc class) | `client.py:125` | `deque.append` thread-safe [PRIOR, theo tài liệu CPython]. Có giới hạn bằng `maxlen`. | Không |
| SDK `OpenAI` / httpx pool | `client.py:144-149`; SDK `openai 3.14.0`, `DEFAULT_CONNECTION_LIMITS = max_connections=1000` (đọc `openai/_constants.py` trong venv) | Không có tuyên bố chính thức của openai-python rằng client thread-safe. httpx/httpcore mô tả pool là thread-safe. Pool 1000 rộng hơn nhiều so với 4–5 lời gọi. | Không (dùng chung một instance là được) |

## 2. Concurrency có sẵn trong code để làm mẫu

- `call_with_timeout` (`client.py:86-109`): mỗi lời gọi LLM **đã** chạy trên một daemon thread (`client.py:102`). Khi quá giờ thì bỏ thread đó, còn HTTP thì bị cắt bằng SDK timeout. Vì vậy song song 4 batch nghĩa là 4 thread pool cộng 4 daemon thread, chấp nhận được.
- Cổng budget dùng `threading.Lock` cộng `threading.Event` để huỷ: `runtime.py:226`, `:348`, `:411-421`. Request đến muộn sau khi lời gọi đã bị bỏ sẽ bị chặn ở `runtime.py:416`.
- `threading.BoundedSemaphore` cho các slot job ở `main.py:139-140`. `asyncio.to_thread` ở `main.py:95`, `:104` và `transport/kafka_idp_worker.py:282`.
- Code app **không** dùng `ThreadPoolExecutor`. Chỉ test dùng (`tests/test_ai2_postgres_store.py:5`, `:279`). Cách dùng `Future` cộng thread có ở `tests/test_st067_bounded_jobs.py:27-39`.
- Job chạy trong process con kiểu spawn (`main.py:321-325`, compose `AI2_JOB_ISOLATION=process`, `docker-compose.yml:615`) với `AI2_MAX_CONCURRENT_JOBS=1` (`docker-compose.yml:614`). Do đó pool thread chỉ nằm trong một job, không cạnh tranh giữa các job.

## 3. Thiết kế khuyến nghị (tối thiểu)

1. **Mỗi batch dùng một bản sao client**: `batch_client = copy.copy(client); batch_client.traces = []`.
   - Bản sao nông nên vẫn dùng chung `_client` (pool httpx), `isinstance(..., NineRouterClient)` vẫn đúng nên `_invoke` vẫn đi nhánh có timeout (`runtime.py:436`).
   - Trace và `last_http_calls` tách riêng theo batch, `_log_call` đọc đúng trace.
   - Chạy được với test double `SimpleNamespace(traces=[], served=...)` (`tests/test_contract_graph_pair_classifier.py:75`, `:434`).
   - Khi xong, `client.traces.extend(batch_client.traces)` **theo thứ tự batch**, để phần thống kê cuối (`pair_classifier.py:529-533`) giữ nguyên.
2. Thêm `_state_lock` (hoặc dùng lại `_request_lock`) bọc `add_issue`, `_fall_back` và mọi bộ đếm mới như `llm_ms_total`.
3. Chặn `provider_exhausted` và cờ `abort` của pairs ngay trong `_reserve_http_request`, để thread đang backoff không gửi thêm request.
4. Chỉ thread điều phối được gọi `report_progress`, theo thứ tự hoàn tất.
5. Đổi `last_http_calls` thành biến local, nếu muốn giữ thì gán vào `self` ở cuối. Nếu dùng bản sao client cho mỗi batch thì việc này không bắt buộc, nhưng nên làm vì semantic/extraction vẫn dùng chung client.
6. Backoff thêm jitter (`runtime.py:388-390` hiện là `0.5*2**attempt` cố định). Khi nhiều thread nhận 429 cùng lúc, chúng sẽ retry đồng loạt. Tài liệu OpenAI khuyên dùng jitter (xem R6).

## Kết luận xếp hạng

1. **Bắt buộc**: tách trace theo từng batch (bản sao client). Nếu không, model phục vụ batch bị gán sai, mà cổng an toàn K-a (`pair_classifier.py:432`) lại dựa vào giá trị này.
2. **Bắt buộc**: lock cho `issues` / `fallback_count` / bộ đếm mới.
3. **Nên làm**: check `provider_exhausted`/abort trong `_reserve_http_request`; backoff có jitter.
4. **Nên làm**: chỉ gọi `report_progress` từ thread điều phối.
5. Không cần: lock cho `remaining()`, `max_llm_calls`, `all_traces`, SDK client.
