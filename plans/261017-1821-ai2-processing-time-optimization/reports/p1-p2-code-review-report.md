# Review code P1+P2 — AI2 processing-time optimization

Phạm vi: `git diff` chưa commit (pair_classifier.py, runtime.py, llm/client.py, api/main.py, compose/env). Chế độ low-effort: một lượt đọc diff, không chạy test, không đọc test/fixture. Loại trừ ProcessingTimeline.tsx.

Verdict: PASS_WITH_RISK (không có lỗi chặn merge).

## Findings (xếp theo mức độ)

1. **Medium — lệch tất định so với tuần tự khi retry ăn budget.** `ai-service/app/pipeline/contract_graph/pair_classifier.py` `_plan_batches` (giả định mỗi batch đúng 1 request) + `runtime.py` nhánh `self.llm_calls_used >= self.max_llm_calls` → `fall_back(last_code or "LLM_BUDGET_EXCEEDED")`. Kịch bản: budget còn 5, 5 batch được plan và gửi song song; batch 1 bị 429 rồi retry, ăn 1 request của budget → batch 5 gặp budget hết trong `complete_json`, trả None kèm issue `LLM_BUDGET_EXCEEDED` (fallback_count +1), consume ra `LLM_FALLBACK`. Tuần tự trong cùng kịch bản dừng ở pre-check với `BUDGET_EXHAUSTED`, không có issue. Kết quả: `stopped_reason`, issues và `fallback_count` khác nhau giữa concurrency=1 và >1. Sửa: ở `consume` song song, map None-do-budget thành `cut(offset, "BUDGET_EXHAUSTED", ...)` và bỏ sink của batch đó, hoặc ghi rõ đây là khác biệt chấp nhận được.

2. **Low — LLM_QUOTA_EXHAUSTED có thể mất ở biên.** `runtime.py:373` (`if self.provider_exhausted: return None`, không issue). Nếu batch j<k vào `complete_json` sau khi batch k đã set `provider_exhausted`, batch j trả None không issue, consume dừng ở j, cancel/bỏ sink của k → issue quota không bao giờ được commit. Vì executor lấy FIFO nên cửa sổ rất hẹp (đúng như dev ghi nhận). Sửa rẻ: khi `issue_sink` khác None và `provider_exhausted`, append `LLM_QUOTA_EXHAUSTED` vào sink (add_issue đã dedupe).

3. **Low — shutdown chờ request đang bay của batch bị bỏ.** `pair_classifier.py` `finally: executor.shutdown(wait=True, cancel_futures=True)`: gate chỉ chặn trước request/retry tiếp theo, không ngắt HTTP đang chạy, nên sau khi batch k fail, S9 vẫn chờ tới `call_timeout_seconds` cho các batch >k. Tokens/llm_calls của các batch bị bỏ vẫn được cộng vào `stats` (qua merge `client.traces`) — đúng về chi phí nhưng khác số liệu tuần tự. Chấp nhận được; nên ghi trong doc.

4. **Low — timing bỏ sót nhánh LLMRequestBudgetExceeded.** `runtime.py` `except LLMRequestBudgetExceeded:` không gọi `_time_attempt`, trong khi `LLMRequestCancelled` và `Exception` có gọi. Nếu attempt đã gửi ≥1 request trước khi bị từ chối reserve (retry định dạng JSON trong client), `coverage.llm_timing` thiếu request đó.

## Ghi chú
- Thread-safety: `_state_lock` bao `issues`/`fallback_count`/`_llm_timing`; `http_calls` chuyển thành local trong client; trace per-batch qua `copy.copy(client)` + `traces=[]` — đọc diff không thấy race.
- Không xác minh bằng test (low effort). Không có số liệu coverage/lint.

## Xử lý finding (main, 2026-10-18)

| # | Xử lý |
|---|---|
| 1 | Chấp nhận: đây là KD2 đã ghi trong `phase-2-parallel-pairs.md:146` (tranh chấp slot budget cuối khi có retry, không tất định). |
| 2 | Đã sửa: `runtime.py`, nhánh `provider_exhausted` append `LLM_QUOTA_EXHAUSTED` vào `issue_sink` khi có sink. Không có sink thì giữ hành vi cũ (không ghi issue trùng). Test `test_exhausted_provider_reports_quota_to_issue_sink` đỏ trước khi sửa, xanh sau khi sửa. |
| 3 | Chấp nhận: trùng KD4 và KD1 (`phase-2-parallel-pairs.md:145,148`). |
| 4 | Không tái hiện được: `test_budget_refused_retry_still_times_the_sent_request` xanh ngay trên code hiện tại. Giữ test này làm regression guard. |

Toàn bộ suite sau khi sửa: `2378 passed, 3 skipped`. Ruff sạch.
