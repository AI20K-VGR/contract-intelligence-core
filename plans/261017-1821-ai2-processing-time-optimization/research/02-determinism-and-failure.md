# R2 — Cách `classify_pairs` dùng kết quả, các điểm phải tất định, và hành vi khi một batch lỗi giữa chừng

## 1. Dòng xử lý hiện tại (tuần tự)

| Bước | Vị trí | Ghi chú tất định |
|---|---|---|
| Vòng batch `offset` bước `PAIRS_PER_CALL=8` | `pair_classifier.py:375` | |
| Kiểm tra dừng **trước** mỗi batch: `BUDGET_EXHAUSTED` → `MAX_CALLS` → `DEADLINE` | `pair_classifier.py:377-388` | Phần còn lại phát `not_sent` với `batch_id=batch-{batches+1}` |
| id cặp toàn cục `p{offset+n+1}` | `pair_classifier.py:391`, `:522-523` | Phụ thuộc offset, không phụ thuộc thứ tự hoàn tất, nên an toàn khi chạy song song |
| `stats["pairs_sent"] += len(batch)` **trước** lời gọi | `pair_classifier.py:407` | |
| `ProcessingTimeout` → `DEADLINE`. `None` → `LLM_FALLBACK`, cộng **toàn bộ phần còn lại** vào `pairs_unclassified` rồi `break` | `pair_classifier.py:416-426` | Batch lỗi phát `no_answer`, các batch sau phát `not_sent` |
| Model phục vụ lấy từ `client.traces[batch_trace_start:]` | `pair_classifier.py:408`, `:427-430` | **Sai khi chạy song song** (xem R1) |
| Cổng họ model K-a → `served_model_rejected` cộng `LLM_FALLBACK` cộng `break` | `pair_classifier.py:432-446` | Cổng an toàn |
| `batches += 1` chỉ khi batch được chấp nhận | `pair_classifier.py:447` | `batches_completed` đi vào `record.pair_relations_ran` (`idp.py:643-649`) |
| Duyệt `rows` theo thứ tự model trả về → `decisions.append`, `emit_pair`, `emit_batch` | `pair_classifier.py:448-518` | Thứ tự bên trong batch theo thứ tự hàng trong response |
| `missing` → `no_answer` | `pair_classifier.py:519-527` | |
| Thống kê cuối: `llm_calls = used - initial`, token cộng dồn từ `client.traces[initial_traces:]`, `served_model` lấy từ trace cuối | `pair_classifier.py:528-535` | |

Các consumer phía sau **phụ thuộc thứ tự**:
- `pair_builder.py:197-234`: `relation_id` trùng thì giữ quyết định **đầu tiên** (`:217-218`).
- Gán `citation_reject` cho event **đầu tiên** khớp cặp (`:208-214`, có `break`).
- Phát lại `pair_events` theo thứ tự (`:236-238`).

Vì vậy `decisions` và `pair_events` phải theo **thứ tự batch tăng dần**, và bên trong mỗi batch theo thứ tự hàng. Nếu không, output (relation nào thắng, event nào bị gán reject) sẽ khác bản tuần tự.

## 2. Thiết kế song song giữ output giống hệt (happy path)

1. **Lập kế hoạch batch trước** trên thread điều phối:
   - `n_batches = min(ceil(len/8), max_calls, max_llm_calls - llm_calls_used)`.
   - Kiểm tra `DEADLINE` một lần.
   - Phần vượt kế hoạch phát `not_sent` với reason đúng như bản tuần tự (`MAX_CALLS` / `BUDGET_EXHAUSTED`).
   - Cách này giữ được `test_batches_of_eight_and_max_five_calls` (`tests/test_contract_graph_pair_classifier.py:154-160`) và `test_budget_checked_before_each_batch` (`:393-398`).
2. Submit phần **chỉ gọi LLM** (dựng message, `complete_json` với bản sao client theo batch) vào `ThreadPoolExecutor(max_workers=AI2_PAIRS_CONCURRENCY)`.
   - Chỉ đếm `injection_signals` khi dựng message, và làm trên thread điều phối.
3. Thread điều phối **thu kết quả theo chỉ số batch** (`futures[i].result()` lần lượt i = 0..n-1, không dùng `as_completed`). Sau đó chạy **nguyên văn** phần hậu xử lý hiện có (`:418-527`) cho từng batch. Kết quả là `decisions`, events, stats, `batches` giống hệt bản tuần tự khi các batch đều thành công.
4. `report_progress` gọi trên thread điều phối khi batch i đã được xử lý.

## 3. Một batch lỗi khi các batch khác đang chạy

| Phương án | Output so với tuần tự | Chi phí | Rủi ro |
|---|---|---|---|
| **A. Prefix semantics**: nhận batch 0..k-1, batch k lỗi thì gán `no_answer`/stop reason của k; batch > k bị **bỏ** (event `not_sent`, reason = stop), dù đã chạy xong | Giống hệt tuần tự **với cùng kết quả của từng batch** | Phí token cho các batch bị bỏ | Event `not_sent` không đúng sự thật (thực ra đã gửi). Nên thêm outcome `discarded` nếu chấp nhận đổi schema event |
| B. Giữ các batch thành công sau k | Khác tuần tự: nhiều relation hơn, `pairs_unclassified` khác | Không lãng phí | Phá ngữ nghĩa "PARTIAL_<stop>" (`idp.py:721-728`) và test hiện có. Với `served_model_rejected` thì **không an toàn**, vì router đổi model là tín hiệu toàn job |
| C. Huỷ ngay: đặt cờ abort, `executor.shutdown(cancel_futures=True)` để huỷ batch chưa chạy. Batch đang chạy thì không retry nữa (cờ abort check trong `_reserve_http_request`) | Kết hợp với A | Giảm số HTTP bị đốt | Cần sửa runtime (R1 mục 3) |

Khuyến nghị **A + C**:
- Kết quả tất định theo chỉ số batch.
- Các batch chưa chạy được huỷ (`Future.cancel` chỉ có tác dụng với future đang xếp hàng [PRIOR]).
- Batch đang bay thì không retry tiếp.
- `ProcessingTimeout` phát ra trong worker sẽ được ném lại khi gọi `future.result()`, và được xử lý như `DEADLINE` ở đúng chỉ số batch, giống `:416-417`.

Có sai khác nhỏ không tránh được so với tuần tự, xảy ra khi retry làm cạn budget giữa chừng:
- Tuần tự: batch k+1 dừng với `BUDGET_EXHAUSTED` ở bước kiểm tra đầu vòng (`:377-378`).
- Song song: batch k+1 đã được submit, `_reserve_http_request` ném `LLMRequestBudgetExceeded`, dẫn tới `None` rồi `LLM_FALLBACK` (`runtime.py:365-367`).

Cần ghi rõ điều này trong plan. Không nên cố mô phỏng.

## 4. Test hiện có sẽ đổi hành vi khi concurrency > 1

- `test_runtime_none_marks_batch_unclassified_and_stops` (`tests/...pair_classifier.py:383-390`): assert `len(runtime.calls) == 1` với 10 cặp (2 batch). Chạy song song thì có 2 lời gọi.
- `test_runtime_rejects_non_anthropic_served_model` (`:431-441`): assert `len(runtime.calls) == 1`.
- `test_missing_current_trace_cannot_reuse_prior_claude_trace` (`:444-462`): vẫn đúng nếu dùng bản sao client theo batch, nhưng phải chứng minh lại.
- Fake `Runtime` (`:38-69`) tăng `llm_calls_used` không có lock. Chỉ ảnh hưởng test.

Xử lý: tham số `concurrency` (mặc định đọc env). Test cũ ghim `concurrency=1`, test mới assert **output bằng nhau** giữa `concurrency=1` và `concurrency=4`. Riêng hai test đếm số lời gọi thì đổi assert thành "không có kết quả nào sau batch lỗi được nhận".

## 5. Số học "wave" (ảnh hưởng thẳng tới mục tiêu <40s)

`PAIRS_TOP_K = 40` (`pair_candidates.py:28`) đúng bằng `8 × 5`, nên job lớn luôn có đúng 5 batch.

| PAIRS_PER_CALL | batch | concurrency 4 | concurrency 5 |
|---|---|---|---|
| 8 | 5 | **2 wave** ≈ 2 × max(latency) ≈ 30–40s | 1 wave ≈ max(5 lời gọi) ≈ 18–20s |
| 10 | 4 | 1 wave | 1 wave |
| 14 | 3 | 1 wave | 1 wave |

Ước lượng dựa trên dải 8–20s/lời gọi trong debug report, là [ASSUMED] cho tới khi P0 đo được latency từng lời gọi. Với default `AI2_PAIRS_CONCURRENCY=4` và batch 8, stage pairs vẫn tốn 2 wave, nên có nguy cơ trượt mục tiêu. **Khuyến nghị default concurrency = `PAIRS_MAX_CALLS` (5)**, hoặc chốt batch 10 trong P2.

## Kết luận xếp hạng

1. Thu kết quả theo chỉ số batch và tái dùng nguyên phần hậu xử lý. Đây là cách duy nhất đảm bảo output giống hệt mà không cần viết lại logic.
2. Khi lỗi thì dùng prefix semantics (A) cộng huỷ/abort (C). Không dùng B vì vi phạm cổng K-a.
3. Default concurrency = 5 (bằng số batch tối đa), không phải 4.
4. Ghi trong plan sai khác `BUDGET_EXHAUSTED` → `LLM_FALLBACK` khi retry làm cạn budget, coi là thay đổi đã biết.
