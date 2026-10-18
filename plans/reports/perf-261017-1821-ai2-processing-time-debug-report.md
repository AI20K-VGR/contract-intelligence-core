# AI2: đo thời gian xử lý (debug --perf)

Nguồn: `ai2.jobs` và `ai2.ai2_processing_trace_events` trong container `ai2-graph-full-backend-db` (local), gồm 28 job và 116 trace event. Đo ngày 2026-10-17.

## 1. Tổng quan

| status | n | wall TB | wall max |
|---|---|---|---|
| SUCCEEDED | 24 | 96.5s | 311s |
| FAILED | 4 | 275s | 745s |

Thời gian theo stage (chỉ tính event COMPLETED):

| stage | n | p50 | p90 | max |
|---|---|---|---|---|
| extraction | 3 | 7.9s | 8.1s | 8.2s |
| contract_graph_operation | 26 | 39ms | 126ms | 3.0s |
| **contract_graph_pairs** | 24 | 4.2s | **95.4s** | **100.7s** |
| semantic | 3 | 45ms | 49ms | 50ms |

## 2. Bottleneck #1 (CONFIRMED): `contract_graph_pairs` gọi LLM tuần tự

Bảng dưới đối chiếu số batch đã gửi (`batches_completed`, lấy từ result_json) với thời gian của stage:

| candidates | batches | pairs_sent | thời gian pairs |
|---|---|---|---|
| 468 | 5 | 40 | 91.8–100.7s |
| 762 | 5 | 40 | 41.1–79.0s |
| 7 | 1 | 7 | 4.0–4.4s |
| bất kỳ, LLM_FALLBACK / NO_CONSENT | 0 | — | <2s |

Chuỗi bằng chứng:
- `pair_classifier.py:389`: vòng `for offset in range(0, len(pairs), PAIRS_PER_CALL)` gọi `runtime.complete_json` **tuần tự**, mỗi lần 8 cặp (`PAIRS_PER_CALL=8`). Số lời gọi bị chặn ở `PAIRS_MAX_CALLS=5`.
- Suy ra mỗi lời gọi mất khoảng **8–20s**. Với job lớn, pairs chiếm **85–90% wall time** (ví dụ job_8044: pairs 98.7s / wall 115.5s).
- Bao phủ thấp: chỉ 40 trong 468–762 candidate được phân loại (5–8%). Số còn lại bị cắt bởi MAX_CALLS mà không ghi `stopped_reason` (cột này là `null`).

## 3. Bottleneck #2 (ASSUMED, chưa xác minh): khoảng thời gian ~300s không có trace

Có 4 job SUCCEEDED (job_028a…, job_7e24…, job_43a2…, job_26b4…) với wall khoảng **310.9s** nhưng tổng trace chỉ khoảng **30ms**. Stage pairs của các job này dừng với lý do `NO_CONSENT`/`DEADLINE`.
- 310s ≈ `max_processing_seconds=300` (`runtime.py:206`) cộng khoảng 10s. Như vậy deadline đã cạn **trước** stage graph.
- Các job này **không có trace `extraction`**, vì instrumentation cho stage đó chỉ có ở 3 job mới nhất. Vì vậy chưa biết 300s đã đi đâu: có thể là OCR/AI1 snapshot, chờ trong hàng đợi (`created_ms` được ghi lúc enqueue), hoặc LLM ở bước extraction.
- Các job lớn khác cũng có khoảng hở 10–25s (wall − traced) chưa được giải thích.
- Bên cạnh đó có 2 job FAILED dài **342s và 745s**, với request_json lần lượt 444KB và 5.6MB.

## 4. Thiếu quan sát

- `latency_ms` của từng lời gọi LLM được tính ở `llm/client.py:217`, nhưng **không được lưu** vào result_json/trace (đếm được 0 lần xuất hiện).
- Không có trace riêng cho thời gian chờ queue/claim (từ created_ms đến lúc claim) và cho thời gian persist.

## 5. Mức độ chắc chắn

- Bottleneck #1: CONFIRMED (có số đo DB và đối chiếu với code).
- Bottleneck #2: chỉ có triệu chứng. Nguyên nhân là ASSUMED cho đến khi chạy lại một job lớn có đủ trace.
- Đây là vấn đề hiệu năng, không phải bug về tính đúng đắn, nên không viết failing test. Ở bước P1 sẽ thay bằng một test benchmark (red→green) đo wall time của `classify_pairs` với client giả lập độ trễ.
