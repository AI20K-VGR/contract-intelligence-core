# P1 — Developer notes (Trace Instrumentation)

Trạng thái: hoàn thành, chưa commit (theo yêu cầu). Không đụng `backend/`, `frontend/`, migration, `docs/contracts/`,
`ai-service/.env`; `frontend/src/components/ai2-graph/ProcessingTimeline.tsx` là thay đổi có sẵn của user, không chạm.

## File thay đổi

| File | Diff |
|---|---|
| `ai-service/app/pipeline/runtime.py` | +87/−7 |
| `ai-service/app/llm/client.py` | +4 |
| `ai-service/app/pipeline/idp.py` | +7/−1 |
| `ai-service/app/api/main.py` | +76 |
| `ai-service/fixtures/perf/__init__.py` | mới, 1 dòng |
| `ai-service/fixtures/perf/replay_job.py` | mới, 321 dòng |
| `ai-service/tests/test_llm_timing_coverage.py` | mới, 143 dòng |
| `ai-service/tests/test_job_timing_log.py` | mới, 130 dòng |
| `ai-service/tests/test_perf_replay_job.py` | mới, 83 dòng |
| `plans/.../reports/phase-1-measurement.md` | mới (báo cáo đo) |

## Tests Before

- TB1.1–TB1.5 trước khi sửa: `76 passed in 241.69s` (golden flag-off/pairs + `test_llm_complete_json.py` +
  `test_job_process_isolation.py` + `test_st067_bounded_jobs.py`).
- Red, lần chạy đầu các test mới:
  - `test_perf_replay_job.py`: `ModuleNotFoundError: No module named 'fixtures.perf'`.
  - `test_llm_timing_coverage.py` + `test_job_timing_log.py`: `11 failed, 1 passed` (R1.1 pass như dự kiến). Lý do:
    `AttributeError: 'ProcessingRuntime' object has no attribute 'llm_timing'` ×3, `KeyError: 'llm_timing'`,
    `KeyError: 'cached_tokens'`, `KeyError: 'job_timing'`, `ValueError: not enough values to unpack (expected 1, got 0)`
    ×3 (chưa có dòng `ai2.job_timing`), `assert ([])` (chưa có handler), và R1.7
    `AssertionError: assert '98765.4' not in 'ai2.llm_cal...'` (log đọc trace cũ — đúng bug F1.4).

## Tests After / Regression Gate

- Test mới: `17 passed in 3.82s`.
- TB + test mới + `test_memory_bounds.py` sau format: `115 passed in 264.91s`.
- Full offline: `AI2_REQUIRE_DATABASE=false uv run --no-sync pytest -q -p no:cacheprovider -m "not live"` →
  `2029 passed, 3 skipped, 6 deselected, 25 warnings in 388.77s` (golden nằm trong suite; không chụp lại golden).
- `ruff check` 9 file: `All checks passed!`; `ruff format --check`: `9 files already formatted` (4 file app đã sạch
  format ở HEAD, nên `ruff format` chỉ đổi dòng mới).
- basetemp: `C:\Users\dungs\.claude\jobs\ad849255\tmp\*`, không tạo `.pytest-tmp-*` mới.

## Acceptance → evidence

- F1.1 gom timing mọi lần thử đã gửi request, dưới `_state_lock`: `runtime.py:231-232` (field `repr=False`),
  `:381` (nhánh lỗi), `:413` (nhánh thành công), `:425-455` (`_time_attempt`/`_record_llm_attempt`), `:500`
  (`reserved.append` trong `_reserve_http_request`). Budget refusal không tính (test R1.4).
- F1.2 `llm_timing()` trả `None` khi 0 lời gọi: `runtime.py:457-485`; merge vào coverage chỉ khi truthy:
  `idp.py:619-632`.
- F1.3 `cached_tokens`: `client.py:257-260`.
- F1.4 `_log_call` nhận trace của chính lần thử: `runtime.py:156-162`, gọi ở `:417`.
- F1.5 mốc worker + `job_timing` + log `scope=worker` trong `finally`: `main.py:450-458` (`_attach_job_timing`),
  `:476`, `:510`, `:548-549`, `:568`, `:604-617`.
- F1.6 `slot_wait_ms`/`run_ms` + log `scope=dispatch`: `main.py:308-334`.
- F1.7 logger `ai2.timing` + handler stderr INFO, propagate giữ True: `main.py:133-147`.
- F1.8 harness: `fixtures/perf/replay_job.py` (`nearest_rank`, `assert_router`, `assert_idle`, `rewrite_request`,
  `summarize_rows`, `render_markdown`, `run`, `summarize`).
- NF1.1 `snapshot()` không đổi key: test R1.1 + golden xanh.
- Success criteria đo lại: 5/5 SUCCEEDED, mỗi job có `llm_timing` (pairs `llm_calls=5`) và `job_timing` int ≥ 0;
  `wall − (slot_wait+run)` = −980…−738ms (≤ 2000); 10 dòng `ai2.job_timing` trong `docker logs`. Chi tiết:
  `reports/phase-1-measurement.md`.

## Đo lại (bước 1, 9, 10)

- Đã chạy, đúng giao thức: preflight RUNNING=0, URL `:20128`; backup 6 CSV trước replay; `docker restart` sau khi
  kiểm `ai2.jobs` RUNNING=0; replay N=5 label `p1-baseline`; summarize.
- Lời gọi LLM: probe 1 + replay 40 = 41 (trong ngân sách 41–101), toàn bộ qua router local, không gọi OpenAI.
- Handler có mặt trong process con spawn (thấy dòng `scope=worker`), nên KHÔNG cần fallback gắn handler trong
  `_job_process_entry`.

## Ghi chú / lệch nhỏ (không đổi hướng plan)

- `status=UNCLAIMED` trong dòng `scope=worker` khi `JOB_STORE.claim` trả `None` (plan không nêu giá trị cho nhánh này).
- R1.11 kiểm `type(h) is logging.StreamHandler` + level INFO, không so identity `sys.stderr` vì pytest thay
  `sys.stderr` theo test.
- Test R1.8 đọc wire tại `result.index_contribution.coverage` (tên field thật của wire), không phải `contribution`.
- Số tuyệt đối của `p1-baseline` (wall p90 41.6s) dùng model router `cx/gpt-5.6-luna`, không so được với baseline prod
  (156.4s); P2/P3 nên so với `p1-baseline`.
- Replay đã ghi đè snapshot/relations AI2 local của hồ sơ tham chiếu (hậu quả đã chấp nhận); backup ở
  `$HOME/.ai2-perf/backup-ref/`, chưa khôi phục (chỉ khi user yêu cầu).
