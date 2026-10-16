# AI2 critique vòng 2 — lens chi phí (261017)

Đo bằng `python -m fixtures.seeded.cost` trên 4 hồ sơ seeded, model router `cx/gpt-5.6-luna` (không gọi OpenAI).

| Hồ sơ | Trước (calls) | Sau (calls) | tokens in/out sau |
|---|---|---|---|
| HD-TEST-001 | 20 (chạm budget) | 8 | 13.6k / 3.3k |
| HD-TEST-003 | 20 (chạm budget) | 4 | 11.0k / 1.7k |
| HD-TEST-004 | 20 (chạm budget) | 5 | 13.0k / 3.0k |
| HD-TEST-002 | 20 (chạm budget) | 6 | 13.7k / 1.8k |
| **Tổng** | **80** | **23** | 51.3k / 9.8k |

Theo stage sau sửa: `pairs` 19, `fact_normalize` 4, `slot_context` 0.

## Theo tính năng
- **Slot-context (frame_context)**: trước đây tiêu hết budget mà 0 slot được chấp nhận. Nguyên nhân: extractor đánh dấu thời hạn "theo thời hạn quy định tại…" là ABSENT, và LLM bị gọi ngay cả khi không clause ngữ cảnh nào có thể ground giá trị. Sửa: `deferred_by_reference` (UNKNOWN) + cổng `_groundable` trước khi gọi LLM. Kết quả: −57 calls, không mất chất lượng (seeded dev 42/42, held-out 20/21, 1944 test pass).
- **Pairs**: giờ chiếm 83% calls; là đích tối ưu tiếp theo (top-K 40, 8 cặp/call).
- **Hết budget**: không hồ sơ seeded nào còn `LLM_BUDGET_EXCEEDED`.

## Bakeoff đã dự kiến
- Batch slot 8 vs 12: không còn ý nghĩa — slot_context hiện 0 call trên seeded.
- Pairs timeout 45 vs 75s: không ảnh hưởng số call; chỉ ảnh hưởng tỉ lệ retry, chưa thấy lỗi timeout ở lượt đo này → giữ nguyên.

## Việc tiếp theo
1. Cắt pairs: lọc cặp deterministic (DUPLICATE/không cùng family) trước khi gửi LLM; đo lại `COST_CALLS`.
2. Guard CONFLICT deterministic (trigger mismatch) cho false conflict của luna.
3. Luna chỉ là proxy chất lượng; xác nhận trên gpt-5.5 chỉ khi người dùng đồng ý chi phí.
