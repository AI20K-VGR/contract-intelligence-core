# Tóm tắt research — Tối ưu thời gian xử lý AI2 (P0/P1/P2)

Ngày 2026-10-17. Nghiên cứu chỉ đọc code, không sửa code và không chạy LLM. Có 6 file chi tiết:

| # | File | Câu hỏi |
|---|---|---|
| 1 | `01-thread-safety.md` | Lock nào cần thêm, mẫu concurrency có sẵn |
| 2 | `02-determinism-and-failure.md` | Giữ output giống hệt bản tuần tự, xử lý batch lỗi giữa chừng, số wave |
| 3 | `03-llm-budget.md` | Budget 20 lời gọi, 429/quota khi song song, MAX_CALLS |
| 4 | `04-trace-store.md` | Migration, vị trí queue/load/persist, whitelist stage ở backend |
| 5 | `05-quality-guards.md` | Lệnh guard chính xác |
| 6 | `06-external-guidance.md` | OpenAI: rate limit, caching, reasoning effort |

## Phát hiện làm thay đổi plan

1. **Whitelist `stage_id` ở backend chặn stage mới.** Nếu ai-service phát stage `queue_wait`/`snapshot_load` mà backend chưa cập nhật, thì `AiAdapterError` làm hỏng **toàn bộ** trace của job (`backend/src/contract_intelligence/infrastructure/ai_adapters.py:467-469`, `:621-625`). FE thì không sao, có fallback label (`ProcessingTimeline.tsx:69`).
2. **`stopped_reason MAX_CALLS` không phải lỗi thiếu ghi.** Ứng viên bị cắt ở `PAIRS_TOP_K=40 = 8×5` trước classifier (`pair_candidates.py:28`), số bị cắt đã có trong `candidates_capped` (`pair_candidates.py:583`). Hai hệ quả:
   - Bỏ mục này khỏi P0.
   - Tăng batch trong P2 không tăng độ phủ.
3. **Default `AI2_PAIRS_CONCURRENCY=4` sẽ chạy 2 wave** với 5 batch, khoảng 30–40s, nên dễ trượt mục tiêu <40s. Nên dùng 5, hoặc batch 10 [ASSUMED dải latency 8–20s].
4. **Gán trace theo chỉ số bị sai khi chạy song song** (`pair_classifier.py:408`, `:427`). Mà cổng an toàn K-a dựa vào trace này. Sửa bằng cách dùng **bản sao client cho mỗi batch** (`copy.copy` với `traces` riêng).
5. **Persist không ghi được thành trace sau commit** vì bị fence (`processing_trace_store.py:145-148`). Nếu ghi `STARTED` thì cả trace thành `INCOMPLETE_UNKNOWN` (`:354-359`).
6. **Đòn bẩy P2 bị bỏ sót**: pairs không dùng `reasoning_effort` thấp (`runtime.py:147`), đang chạy ở mặc định medium của gpt-5.5.

## Khuyến nghị xếp hạng (toàn plan)

1. **P0, không migration**:
   - `latency_ms`/`cached_tokens` của từng lời gọi được gom (có lock) vào `result_json` coverage. Chỉ phát `llm_timing` khi có lời gọi, để golden flag-off giữ nguyên.
   - queue_wait/snapshot_load ghi vào coverage. Nếu cần hiện trên UI thì đổi sang stage trace, kèm sửa whitelist backend (deploy backend trước).
   - persist chỉ ghi log có cấu trúc.
2. **P1**:
   - `ThreadPoolExecutor(max_workers=5)`, mỗi batch một bản sao client.
   - Thu kết quả theo chỉ số batch và chạy lại **nguyên văn** phần hậu xử lý cũ.
   - Khi lỗi: prefix semantics, cộng cờ abort và `cancel_futures`.
   - Lock cho `issues`/`fallback_count`. Cho reserve kiểm tra `provider_exhausted`/abort. Backoff có jitter.
   - Test RED: output bằng nhau giữa concurrency 1 và 5.
3. **P2**: bake-off với thứ tự C1 (`reasoning_effort=low`) → C2 (batch 10) → C3 (model nhỏ cùng họ). Cổng chất lượng là `run_live --repeats 3` trên router.

## Rủi ro chấp nhận khi áp dụng

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Lỗi provider đốt tới 15/20 lời gọi, semantic bị đói | Cao | Cờ abort dùng chung, trần riêng cho pairs (cần user chốt) |
| Router đổi provider khi bị throttle, cổng K-a chặn | Trung bình | Theo dõi `served_model` từng batch (P0) |
| Sai khác `BUDGET_EXHAUSTED` → `LLM_FALLBACK` khi retry làm cạn budget | Thấp | Ghi trong plan như hành vi đã biết |
| Golden flag-off đỏ | Thấp | Phát key có điều kiện |

## Giới hạn của research

- Chưa chạy probe tải hay bake-off. Mọi con số về latency/wave là [ASSUMED], dựa trên dải 8–20s của debug report.
- Chưa đo số token của `SYSTEM_PROMPT` (venv không có tiktoken).
- Không có tài liệu chính thức về concurrency của 9router.
- Chưa xác minh tên field `prompt_tokens_details.cached_tokens` trong Chat Completions ([PRIOR]).
- Chưa điều tra Bottleneck #2 (khoảng ~300s không có trace). P0 chỉ đặt mốc đo cho nó.

## Câu hỏi mở (cần user)

1. Trần budget riêng cho pairs, ví dụ `max_calls + 2`, để giữ phần cho semantic? Câu này nối với quyết định budget còn treo ở plan 261016 (`plan.md:81`).
2. queue_wait/snapshot_load chỉ cần cho phân tích (coverage), hay phải hiện trên UI (cần sửa backend + FE và deploy backend trước)?
3. Chốt default concurrency = 5 thay cho 4?
4. Chạy bake-off P2 / `run_live` với router local (`cx/gpt-5.6-luna`) hay với OpenAI (cần cho phép)?
5. Khi batch lỗi: chấp nhận bỏ các batch sau dù đã trả phí (prefix semantics), hay muốn giữ lại (đổi ngữ nghĩa `PARTIAL_*`)?
