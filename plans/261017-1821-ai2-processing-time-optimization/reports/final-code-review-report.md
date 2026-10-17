# Final code review — 261017-1821-ai2-processing-time-optimization

Verdict: **PASS_WITH_RISK** (không có lỗi chặn)

## Phạm vi
- Diff chưa commit: `ai-service/app/pipeline/runtime.py`, `pair_classifier.py`, `pair_builder.py`, `idp.py`, `api/main.py`, `llm/client.py`, `.env.example`, deploy/compose. Loại trừ `ProcessingTimeline.tsx`.
- Mức low: một lượt đọc diff, bỏ qua hunk test/fixtures, KHÔNG chạy test, KHÔNG xác minh chéo compose passthrough và tính tautology của test (các gap được yêu cầu nhưng chưa được kiểm chứng ở mức này).

## Kiểm tra trọng tâm
- F2 (`runtime.py`, nhánh `if self.provider_exhausted:`): khi có `issue_sink`, gọi `fall_back("LLM_QUOTA_EXHAUSTED")` -> batch đi sau vẫn mang issue nếu batch đặt cờ bị bỏ. Không có sink thì runtime đã giữ issue. Đúng; `commit_issues` tăng `fallback_count` dưới `_state_lock`, `_add_issue_locked` khử trùng lặp.
- P3 `pairs_reasoning_effort()`: env rỗng / `provider_default` -> None; giá trị lạ -> None + warn một lần (lock). Default C0 giữ nguyên theo quyết định user.
- `effective_prompt_version()` giữ bare `pairs-v13` khi effort None và `PAIRS_PER_CALL == 8` -> golden/row cũ không đổi. `pair_builder.py` dùng `stats.get("prompt_version") or PROMPT_VERSION` cho cả relation lẫn result.
- Golden-hash: `idp.py` chỉ thêm `llm_timing` khi `runtime.llm_timing()` truthy; `_llm_timing` nằm ngoài `snapshot()`. `job_timing` gắn ở `api/main.py::_attach_job_timing` — chỉ trên đường wire job, không qua `run_idp` của golden.
- `pairs_bakeoff.py` gọi `check_router()` -> `assert_router` trên `ROUTER_ENVS` trước khi chạy.

## Findings
1. Low — `pair_classifier.py` `classify_pairs` (dòng `stats["prompt_version"] = effective_prompt_version(prompt_version)`) và `runtime.py::_reasoning_effort`: effort được đọc env hai lần độc lập (stamp lúc bắt đầu, gửi lúc mỗi call). Env đổi giữa job (hiếm, chỉ trong test/monkeypatch) -> provenance lệch effort thực gửi. Đề xuất: resolve một lần, truyền xuống.
2. Low — `api/main.py::_attach_job_timing`: `job_timing` ghi vào `coverage` mọi wire job kể cả không gọi LLM, khác chính sách "chỉ khi LLM called" của `llm_timing`. Không ảnh hưởng golden `run_idp`, nhưng nếu có golden ở tầng wire/persisted coverage thì sẽ trôi theo thời gian chạy. Cần xác nhận không có golden nào hash coverage ở tầng API.
3. Low — `api/main.py` `_ensure_timing_handler` + `propagate` vẫn bật: nếu sau này app cấu hình root handler, dòng `ai2.job_timing` sẽ in hai lần. Không lỗi hiện tại.

## Chưa xác minh (mức low)
- Passthrough `AI2_PAIRS_CONCURRENCY` / `AI2_PAIRS_REASONING_EFFORT` trong `docker-compose.yml` và `deploy/compose.prod.yml` (dựa vào `deploy/tests/test_ai2_pairs_env_passthrough.py`, chưa chạy).
- Tautology của test mới — không review hunk test ở mức này.

## Plan follow-up
- P3 + F2 có vẻ hoàn tất về code. Khuyến nghị chạy suite mục tiêu trước ship.
