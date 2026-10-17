---
phase: 1
title: "Trace Instrumentation"
status: pending
plan: 261017-1821-ai2-processing-time-optimization
created: 2026-10-17
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 1 — Trace Instrumentation

## Overview

Phase này đo cho đủ mà không đổi hành vi. Sản phẩm của phase:
- timing từng lời gọi LLM, ghi vào `coverage.llm_timing` (chỉ khi job có ≥1 lời gọi);
- timing vòng đời job, ghi vào log `ai2.job_timing` và `coverage.job_timing`;
- harness đo lại hồ sơ tham chiếu;
- baseline mới cùng ngày, có phân rã wall.

Phase không có phụ thuộc. Đây là nền cho P2 (latency theo batch, baseline) và P3 (metric của bake-off).

## Requirements

**Chức năng**

- F1.1 — `ProcessingRuntime` gom timing của mọi lần thử đã gửi ít nhất một HTTP request, dù thành công hay lỗi.
  - Đơn vị `llm_calls` là HTTP request, cùng đơn vị với `llm_calls_used` (`ai-service/app/pipeline/runtime.py:197-201`).
  - Latency của một lần thử là wall đo bằng `perf_counter` quanh `call_with_timeout` (`runtime.py:351-364`).
  - Theo từng `operation`, gom `llm_calls`, `llm_ms_total`, `llm_ms_max` và `cached_tokens`.
  - Lần thử bị reserve từ chối (`LLMRequestBudgetExceeded`, `runtime.py:365-367`) không gửi gì nên **không** được tính.
  - Việc gom được bảo vệ bởi `_state_lock` mới.
- F1.2 — `coverage["llm_timing"]` có dạng sau và **chỉ xuất hiện khi `llm_calls ≥ 1`** (D2). Key được merge tại điểm
  dựng coverage cuối, sau stage semantic (`ai-service/app/pipeline/idp.py:627`).
  ```text
  {"llm_calls": int, "llm_ms_total": int, "cached_tokens": int | None,
   "by_operation": {"<op>": {"llm_calls": int, "llm_ms_total": int, "llm_ms_max": int, "cached_tokens": int | None}}}
  ```
  `cached_tokens` là `None` khi provider chưa từng báo giá trị này; không ghi số 0 giả.
- F1.3 — `NineRouterClient.complete_json` đọc `usage.prompt_tokens_details.cached_tokens` vào `trace["cached_tokens"]`
  khi có (`ai-service/app/llm/client.py:247-256`). Tên field là [PRIOR]; bước 1 sẽ probe.
- F1.4 — Hàm module `_log_call` nhận trace của **chính lần thử đó** (lấy theo phần list `traces` tăng thêm),
  không đọc `traces[-1]` (`runtime.py:156-172`, gọi ở `:403`). Định dạng dòng `ai2.llm_call` giữ nguyên.
- F1.5 — `_execute_wire_job` (`ai-service/app/api/main.py:414-506`) đo các mốc sau:

  | Mốc | Đo quanh | Vị trí |
  |---|---|---|
  | `snapshot_load_ms` | verify cộng adapt | `main.py:418-423` |
  | `claim_ms` | claim cộng `set_wire` RUNNING | `main.py:431-454` |
  | `pipeline_ms` | `run_idp` | `main.py:482-490` |
  | `persist_ms` | `complete_with_snapshot` | `main.py:496-506` |

  - Trước `job_result_to_wire` (`main.py:495`), gắn `coverage.job_timing = {snapshot_load_ms, claim_ms, pipeline_ms}` vào
    `result.contribution.coverage` (`ai-service/app/contracts/models.py:1023`, `:1043`) nếu contribution khác `None`.
    Lúc gắn thì `run_idp` đã xong, nên `pipeline_ms` đã có.
  - P3 dùng `wall_ms − pipeline_ms` (tính được từ DB) làm phần overhead của job trong điều kiện dừng p90 (F5 trong
    plan.md).
  - Ghi **một** dòng log `ai2.job_timing scope=worker` trong `finally`, gồm mọi mốc đã đo được (mốc chưa tới thì
    `None`), `status=`, `accepted=`. Nhờ vậy job FAILED (342s/745s ở debug report) cũng có số liệu.
- F1.6 — `_run_wire_job` (`main.py:276-296`) đo `slot_wait_ms` (từ lúc vào hàm tới lúc lấy được `_JOB_SLOTS`, `:285`)
  và `run_ms` (thời gian giữ slot, ở mode `process` chính là vòng đời process con). Ghi log
  `ai2.job_timing scope=dispatch isolation=<mode>`. Hai số này chỉ ghi log, không vào coverage (VL-3 của plan.md).
- F1.7 — Logger `ai2.timing` có handler `StreamHandler(sys.stderr)` ở mức INFO, chỉ gắn khi logger chưa có handler.
  `propagate` giữ `True` để `caplog` bắt được. Lý do: app không cấu hình logging, và OBSERVED có 0 dòng
  `ai2.llm_call` trong `docker logs` (ràng buộc Log trong plan.md).
- F1.8 — Harness `ai-service/fixtures/perf/replay_job.py`. Harness không dùng dependency mới; ghi DB thì đi qua
  `JOB_STORE`/POST, phần đọc dùng SQL chỉ-đọc.
  - `run --request-file <path> --runs N --label <l>`:
    - Từ chối chạy nếu base URL không chứa `:20128`, hoặc nếu có job `RUNNING`.
    - Mỗi lần chạy: đổi `request_id`/`idempotency_key` thành `perf-<label>-<i>-<uuid8>`, ký lại `service_envelope`
      bằng `build_service_envelope` (`ai-service/app/security/service_envelope.py:42`), dùng secret, issuer,
      audience và key id từ env của container.
    - POST `http://127.0.0.1:8002/jobs/idp`, rồi poll trạng thái trong `ai2.jobs` tới khi kết thúc. Chạy tuần tự.
  - `summarize --label <l>`:
    - Đọc `ai2.jobs` (wall = `updated_ms − created_ms`, cùng định nghĩa với debug report), trace events và coverage.
    - In bảng markdown: p50/p90 nearest-rank của wall và pairs, phần ngoài pairs (`wall − pairs` và
      `wall_ms − pipeline_ms`), `job_timing`, `llm_timing.by_operation.pairs`, `batches_completed`, `stopped_reason`.
  - Mỗi lệnh in `calls=<tổng llm_timing.llm_calls>` để cook cộng dồn ngân sách lời gọi (F9 trong plan.md).

**Phi chức năng**

- NF1.1 — Không thêm key vào `ProcessingRuntime.snapshot()` (`runtime.py:453-469`), vì golden flag-off hash cả khối
  này (`ai-service/tests/test_contract_graph_pairs_flag_regression.py:32`).
- NF1.2 — Không có `stage_id` mới, không migration, không đổi backend/FE.
  - `backend/src/contract_intelligence/infrastructure/ai_adapters.py:467-469`, `:621-625`.
  - `docs/contracts/ai2.processing-trace.v1.schema.json:25`.
- NF1.3 — Log và coverage chỉ chứa số, id job, operation và model. Không chứa prompt, answer, request hay text hợp đồng.
- NF1.4 — Bỏ mục "stopped_reason MAX_CALLS" (D2). Số ứng viên bị cắt đã có trong `candidates_capped`
  (`ai-service/app/pipeline/contract_graph/pair_candidates.py:583`, `_COUNTS` ở `pair_projection.py:43`). Classifier
  nhận đúng 40 = 8×5 cặp (`pair_candidates.py:28`).
- NF1.5 — Overhead của phần đo chỉ gồm vài lệnh `perf_counter` cộng một lock ngắn mỗi lần thử. Không có I/O phụ
  trên đường xử lý chính.

## Related Code Files

- **Sửa**:
  - `ai-service/app/pipeline/runtime.py`
  - `ai-service/app/llm/client.py`
  - `ai-service/app/pipeline/idp.py`
  - `ai-service/app/api/main.py`
- **Tạo**:
  - `ai-service/fixtures/perf/__init__.py`
  - `ai-service/fixtures/perf/replay_job.py`
  - `ai-service/tests/test_llm_timing_coverage.py`
  - `ai-service/tests/test_job_timing_log.py`
  - `ai-service/tests/test_perf_replay_job.py`
- **Báo cáo** (trong plan): `plans/261017-1821-ai2-processing-time-optimization/reports/phase-1-measurement.md`
- **Xoá**: không có.

## File inventory (deep)

| Hành động | Path | Cỡ ước lượng | Ảnh hưởng test |
|---|---|---|---|
| Sửa | `ai-service/app/pipeline/runtime.py` | +60/−10 | `test_llm_complete_json.py`, `test_st067_bounded_jobs.py` phải xanh nguyên trạng |
| Sửa | `ai-service/app/llm/client.py` | +5 | `test_llm_complete_json.py:77-145` (trace) phải xanh |
| Sửa | `ai-service/app/pipeline/idp.py` | +3 | golden flag-off/graph-on phải giữ nguyên byte |
| Sửa | `ai-service/app/api/main.py` | +50 | `test_job_process_isolation.py`, `test_memory_bounds.py`, `test_st067_bounded_jobs.py:380,616` phải xanh |
| Tạo | `ai-service/fixtures/perf/__init__.py` | 1 | — |
| Tạo | `ai-service/fixtures/perf/replay_job.py` | ~220 | `test_perf_replay_job.py` |
| Tạo | `ai-service/tests/test_llm_timing_coverage.py` | ~180 | mới |
| Tạo | `ai-service/tests/test_job_timing_log.py` | ~140 | mới |
| Tạo | `ai-service/tests/test_perf_replay_job.py` | ~100 | mới |

Phase có 9 file, vượt ngưỡng 8. Lý do giữ: 3 file là test, 2 file là harness đo mà D8 bắt buộc cho mọi phase.
Không tách thêm phase vì D1 giới hạn 3 phase.

## Dependency map (deep)

- **Phụ thuộc vào**: không có phase nào.
- **Phase phụ thuộc vào P1**:
  - P2 dùng `replay_job.py`, `llm_timing.by_operation.pairs` (`llm_ms_max` xấp xỉ wave), `_state_lock` và baseline
    `p1-baseline`.
  - P3 dùng `replay_job.py` cho lần đo cuối và `cached_tokens` để quan sát cache.
- **Phụ thuộc ngoài**:
  - Router local `:20128`. Probe tại bước 1 và lần đo lại.
  - Container `ai2-graph-full-ai2-service` mount code read-only.
  - DB `ai2-graph-full-backend-db`.

## Implementation Steps

1. **Probe tên field cached tokens** (một lời gọi router, chạy trong container, có key hợp lệ):
   - Dùng script tạm ở `/tmp`, không commit.
   - Script tạo `NineRouterClient` từ env `AI2_CONTRACT_GRAPH_PAIRS_*`, assert base URL chứa `:20128`, gọi một prompt
     JSON tối giản, rồi chỉ in `sorted(usage.model_dump())` và `usage.prompt_tokens_details`.
   - Ghi kết quả OBSERVED vào `reports/phase-1-measurement.md`.
   - Không có field này thì `cached_tokens` luôn là `None`; code vẫn đúng.
2. **Viết test trước** (mục Tests Before). Chạy để xác nhận: các test khoá PASS, các test hành vi mới FAIL đúng lý do
   (`AttributeError`/`KeyError`/`ModuleNotFoundError`).
3. **`runtime.py`**:
   - Thêm hai field, cả hai `repr=False`, không đưa vào `snapshot()`:
     - `_state_lock: Any = field(default_factory=threading.Lock, repr=False)`
     - `_llm_timing: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)`
   - Thêm tham số `reserved: list[int] | None` cho `_reserve_http_request` (`runtime.py:411-421`). Reserve thành công
     thì append vào list đó. Đây là cách cục bộ theo luồng để biết lần thử đã gửi bao nhiêu HTTP request; không đọc
     `llm_calls_used`, vì sang P2 các thread khác cũng tăng bộ đếm này. Đã grep: không có caller nào ngoài file.
   - Trong vòng retry của `complete_json`:
     - Lấy `before = len(traces)`, `t = perf_counter()` ngay trước `call_with_timeout`.
     - Ở nhánh thành công và nhánh `except Exception` (không tính `LLMRequestBudgetExceeded`), nếu `reserved` không
       rỗng thì gọi `self._record_llm_attempt(operation or "unlabelled", elapsed_ms, len(reserved), trace)`.
     - `trace = traces[before:][-1]` nếu list có tăng, ngược lại là `None`.
   - `_record_llm_attempt` cập nhật `_llm_timing` dưới `_state_lock`.
   - `llm_timing()` copy kết quả dưới lock, làm tròn sang `int`, trả `None` khi tổng `llm_calls == 0`.
   - Đổi chữ ký thành `_log_call(client, attempt, operation, trace)`, dùng trace đã truyền vào (rỗng thì là `{}`).
     Định dạng log giữ nguyên.
4. **`client.py`**: sau khi đọc token ở `:249-256`, đọc
   `getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", None)`, khác `None` thì ghi vào
   `trace["cached_tokens"]`.
5. **`idp.py:627`**: `timing = runtime.llm_timing()`, merge `{"llm_timing": timing}` chỉ khi `timing` truthy, trong
   cùng biểu thức dựng coverage với `semantic_requested`. Không đụng `:558-571`.
6. **`main.py`**:
   - Thêm logger `ai2.timing` cùng hàm `_ensure_timing_handler()`, gọi ở module scope. Process con spawn import lại
     `app.api.main` nên handler cũng được gắn trong process con; bước 9 sẽ kiểm.
   - Đo mốc trong `_run_wire_job`. Trong `_execute_wire_job` đo mốc bằng `time.monotonic()`, thêm
     `_attach_job_timing(result, timing)` và log trong `finally`. Không đổi chữ ký `_job_process_entry`/target, để giữ
     `tests/test_job_process_isolation.py:8-19`.
7. **`fixtures/perf/replay_job.py`**:
   - Có `argparse` với hai subcommand `run`/`summarize`.
   - Các hàm thuần, test được: `nearest_rank(values, q)`, `rewrite_request(payload, label, i, secret, now)`,
     `assert_router(url)`, `summarize_rows(rows)`.
   - Kết nối DB qua `app.db.engine.get_engine()` (đọc `AI2_DATABASE_URL`).
   - Không in nội dung request.
8. **Chạy gate**: các test mới; suite pairs/runtime/trace/isolation; golden; suite đầy đủ `-m "not live"`; ruff trên 9
   file.
9. **Đo lại** theo `## Giao thức đo lại` trong plan.md, label `p1-baseline`, N=5.
   - **Trước replay đầu tiên**, chạy bước 3 của giao thức (F14): backup CSV 6 bảng `ai2` của
     `dos_01M4ZMW1F0MCE95QGPF04Y7MYM` vào `$HOME/.ai2-perf/backup-ref/`, rồi ghi số dòng từng file vào báo cáo.
     Chưa có backup thì không replay.
   - Cộng dồn `calls=` vào báo cáo. Ngân sách P1 là 41–101 lời gọi; vượt 1.5× thì dừng và hỏi user.
   - Kiểm tra thêm: `docker logs ai2-graph-full-ai2-service 2>&1 | grep "ai2.job_timing"` phải có 5 dòng
     `scope=worker` và 5 dòng `scope=dispatch` khớp các job id của replay.
   - Thiếu `scope=worker` thì gắn handler trong `_job_process_entry` rồi đo lại.
10. **Viết `reports/phase-1-measurement.md`**:
    - bảng p50/p90 so với bảng baseline trong plan.md;
    - phân rã theo từng job: `slot_wait`, `run_ms`, `snapshot_load`, `claim`, `pipeline`, `persist`, các stage trace,
      phần còn lại chưa giải thích;
    - kết quả probe `cached_tokens`;
    - kết luận về khoảng 59.5s ngoài pairs: có tái hiện không, và nằm ở đâu.

## Test scenario matrix (deep)

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Golden flag-off/graph-on không đổi byte, vì không có lời gọi LLM nên không có `llm_timing` | TB1.1 |
| Critical | `snapshot()` giữ nguyên tập key sau khi có lời gọi | TB1.2, R1.1 |
| Critical | Job có lời gọi thì `coverage.llm_timing.llm_calls == runtime.llm_calls_used` (job bắt đầu từ 0), `sum(by_operation.*.llm_calls) == llm_calls` | R1.2 |
| High | Lần thử lỗi (429/5xx/timeout) vẫn được tính; lần bị reserve từ chối thì không | R1.3, R1.4 |
| High | Gom timing an toàn khi 8 thread ghi cùng lúc | R1.5 |
| High | Log timing nhìn thấy được: logger có handler INFO; dòng `scope=worker`/`scope=dispatch` đủ field, không có payload | R1.9, R1.10, R1.11 |
| High | `coverage.job_timing` được gắn trước persist, có mặt trong cả `result` truyền vào `complete_with_snapshot` lẫn wire | R1.8 |
| Medium | `cached_tokens` có khi provider báo, vắng khi không báo | R1.6 |
| Medium | `_log_call` không dùng trace cũ khi lần thử hiện tại không tạo trace | R1.7 |
| Medium | Job thất bại vẫn có log `scope=worker`, mốc chưa tới là `None` | R1.9b |
| Medium | Harness: percentile nearest-rank đúng; request được ký lại verify được; từ chối URL không phải router; từ chối khi có job RUNNING | R1.12 |

### Tests Before

Các test khoá hành vi hiện có. Chạy trước khi sửa, phải PASS, và phải PASS lại sau khi sửa.

- [ ] TB1.1 `tests/test_contract_graph_flag_off_regression.py`, `tests/test_contract_graph_pairs_flag_regression.py`.
  Khoá hash golden (bẫy D2). OBSERVED baseline: 21 passed.
- [ ] TB1.2 `tests/test_llm_complete_json.py::test_runtime_snapshot_reports_remaining_budgets_without_payload_data`
  (`:147`). Khoá tập key của `snapshot()`.
- [ ] TB1.3 `tests/test_llm_complete_json.py::test_runtime_logs_each_successful_call_with_timing_and_tokens` (`:290`).
  Khoá định dạng `ai2.llm_call` khi đổi `_log_call`.
- [ ] TB1.4 `tests/test_job_process_isolation.py` (3 test). Khoá target 3 tham số và cách xử lý crash/timeout.
- [ ] TB1.5 `tests/test_st067_bounded_jobs.py`. Khoá retry, Retry-After, budget và deadline khi chèn timing vào vòng
  retry.

Các test hành vi mới, viết trước, phải **FAIL** khi chạy lần đầu:

- [ ] R1.1 `test_snapshot_keys_unchanged_after_llm_call`. Lần đầu PASS, giữ làm khoá cùng R1.2.
- [ ] R1.2 `test_llm_timing_present_only_after_llm_call`: `run_idp` với LLM giả, egress bật → có `llm_timing` và hai
  bất biến ở bảng trên; egress tắt → không có key.
- [ ] R1.3 `test_runtime_times_failed_attempts`: `RaisingLLM` 429 ×3 với `FakeClock` → `llm_calls == 3`.
- [ ] R1.4 `test_budget_refusal_is_not_timed`: `max_llm_calls=0` → `llm_timing() is None`.
- [ ] R1.5 `test_llm_timing_accumulation_is_thread_safe`: 8 thread × 50 lần `_record_llm_attempt` → tổng chính xác.
- [ ] R1.6 `test_trace_records_cached_tokens_when_reported`: fake response có `prompt_tokens_details.cached_tokens=1024`
  → trace có `1024`; không có field thì trace không có key.
- [ ] R1.7 `test_log_call_ignores_stale_trace`.
- [ ] R1.8 `test_worker_attaches_job_timing_before_persist`: `JOB_STORE` giả bắt `result` truyền vào
  `complete_with_snapshot`. Assert `coverage.job_timing` có đủ `snapshot_load_ms`, `claim_ms`, `pipeline_ms`.
- [ ] R1.9 `test_worker_logs_job_timing_line` và R1.9b `test_failed_job_still_logs_timing` (caplog, logger `ai2.timing`).
- [ ] R1.10 `test_dispatch_logs_slot_wait`: `JOB_ISOLATION="thread"`, `_execute_wire_job` được stub.
- [ ] R1.11 `test_timing_logger_has_info_stderr_handler`.
- [ ] R1.12 `tests/test_perf_replay_job.py`:
  - `[86.0, 101.4, 112.3, 115.5, 156.4]` → p50 `112.3`, p90 `156.4`;
  - request ký lại qua được `verify_service_envelope`;
  - harness từ chối `https://api.openai.com/v1`;
  - harness từ chối khi số job `RUNNING` khác 0.

### Implement

Làm theo bước 3–7 của Implementation Steps.

### Tests After

- [ ] Mọi test R1.x chuyển xanh. TB1.x vẫn xanh.
- [ ] Integration: suite pairs/runtime/trace/isolation (OBSERVED baseline 275 passed) xanh, không phải sửa test cũ.
- [ ] E2E: replay `p1-baseline` N=5 có 5/5 job SUCCEEDED; mỗi `result_json` có `coverage.llm_timing` với
  `by_operation.pairs.llm_calls ≥ 5` và có `coverage.job_timing`; `docker logs` có đủ 10 dòng `ai2.job_timing`.

### Regression Gate

```text
cd ai-service
AI2_REQUIRE_DATABASE=false uv run --no-sync pytest -q -p no:cacheprovider -m "not live" --basetemp="$TEMP/ai2-pytest-p1"
uv run --no-sync ruff check app/pipeline/runtime.py app/llm/client.py app/pipeline/idp.py app/api/main.py fixtures/perf tests/test_llm_timing_coverage.py tests/test_job_timing_log.py tests/test_perf_replay_job.py
uv run --no-sync ruff format --check app/pipeline/runtime.py app/llm/client.py app/pipeline/idp.py app/api/main.py fixtures/perf tests/test_llm_timing_coverage.py tests/test_job_timing_log.py tests/test_perf_replay_job.py
```

Gate phải PASS 100% thì mới commit P1 và sang P2.

## Success Criteria

- [ ] Regression gate xanh; golden 21/21 xanh, không phải chụp lại golden.
- [ ] Trước replay đầu tiên, `$HOME/.ai2-perf/backup-ref/` đã có đủ 6 file CSV, số dòng được ghi trong báo cáo (F14).
- [ ] 5/5 replay `p1-baseline` có `coverage.llm_timing` (với `llm_calls ≥ 1`) và
  `coverage.job_timing.{snapshot_load_ms, claim_ms, pipeline_ms}` là `int ≥ 0`.
- [ ] Mỗi replay có `wall_ms − (slot_wait_ms + run_ms) ≤ 2000`, tức wall được log dispatch giải thích tới sai số 2s.
  `run_ms − (snapshot_load_ms + claim_ms + pipeline_ms + persist_ms)` được báo cáo là chi phí spawn/import.
- [ ] `reports/phase-1-measurement.md` có: bảng p50/p90 wall/pairs của `p1-baseline` cạnh bảng baseline trong
  plan.md; phân rã theo từng job; kết quả probe `cached_tokens`; kết luận về khoảng 59.5s.
- [ ] `git diff --stat` của P1 không chạm `backend/`, `frontend/`, `ai-service/app/db/migrations/`,
  `docs/contracts/`.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| Handler `ai2.timing` không được gắn trong process con spawn, nên log vẫn vô hình | Thấp–TB × TB | Bước 9 kiểm `docker logs`; thiếu thì gắn handler trong `_job_process_entry` |
| Log bị in đôi nếu sau này có code cấu hình root logger (ví dụ `kafka_idp_worker.py:345`) | Thấp × Thấp | Chỉ gắn handler khi logger chưa có handler; chấp nhận khả năng in đôi trong process Kafka |
| Chèn timing vào vòng retry làm đổi hành vi retry/deadline | Thấp × Cao | Chỉ đọc đồng hồ và append dưới lock, không đổi luồng điều khiển; TB1.5 khoá hành vi |
| Đổi chữ ký `_reserve_http_request` làm hỏng caller | Thấp × TB | Đã grep: không có caller ngoài `runtime.py`; tham số mới có mặc định `None` |
| Replay ghi đè snapshot/relations AI2 của hồ sơ tham chiếu ở local | Chắc chắn × Thấp | Backup CSV trước replay đầu tiên, có quy trình khôi phục (giao thức bước 3, F14); chỉ chạy local |
| `request_json` lọt vào git | Thấp × Cao | Chỉ lưu ở `$HOME/.ai2-perf/` và `/tmp/ai2-perf/`; harness không in payload |
