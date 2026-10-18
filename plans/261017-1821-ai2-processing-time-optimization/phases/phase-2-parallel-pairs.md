---
phase: 2
title: "Parallel Pairs"
status: pending
plan: 261017-1821-ai2-processing-time-optimization
created: 2026-10-17
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 2 — Parallel Pairs

## Overview

Phase này cho stage pairs chạy tối đa 5 batch song song (`AI2_PAIRS_CONCURRENCY`, mặc định 5), thay cho vòng tuần tự ở
`ai-service/app/pipeline/contract_graph/pair_classifier.py:375`. Kết quả được thu theo chỉ số batch, và phần hậu xử
lý hiện có (`:416-527`) chạy lại nguyên văn. Phạm vi tương đương được giới hạn chính xác ở INV-1/INV-2; các sai khác
phụ thuộc thời điểm được ghi thành KD2/KD3/KD6.

Phase còn làm:
- Đưa runtime về trạng thái an toàn luồng.
- Đưa `AI2_PAIRS_CONCURRENCY` qua compose để công tắc quay về tới được container ở cả local lẫn prod (D9, F1).
- Lấy baseline `run_live` trước khi đổi code (F10).
- Chạy thí nghiệm có đo cho chính sách khi batch lỗi (D4/D14).

Phase phụ thuộc P1.

## Requirements

**Chức năng**

- F2.1 — **Knob**: `classify_pairs(..., concurrency: int | None = None)`. Khi giá trị là `None` thì đọc env
  `AI2_PAIRS_CONCURRENCY`:

  | Giá trị env | Kết quả |
  |---|---|
  | không đặt | 5 |
  | `1` | đường tuần tự hiện tại, giữ nguyên code, không tạo executor |
  | không parse được hoặc `< 1` | 5, kèm một warning |

  - Executor chỉ được tạo khi `concurrency > 1` **và** `n_planned ≥ 1`. Nếu `n_planned == 0` (không có ứng viên,
    budget hoặc DEADLINE đã chặn) thì chạy đường tuần tự, kết quả giống hệt bản hiện tại (F3).
  - Lý do: gọi `ThreadPoolExecutor(max_workers=0)` ném `ValueError` (repro ở F3); `gate()` không kiểm số ứng viên
    (`ai-service/app/pipeline/contract_graph/pair_builder.py:57-72`).
  - Số worker thực tế là `min(concurrency, n_planned)`.
- F2.2 — **Lập kế hoạch** bằng hàm thuần `_plan_batches(n_total, used0, max_llm_calls, max_calls, deadline_ok) ->
  (n_planned, cut_reason)`.
  - Thứ tự predicate giống bản tuần tự (`:377-382`): `BUDGET_EXHAUSTED` → `MAX_CALLS` → `DEADLINE`, dùng bộ đếm dự
    phóng `used0 + i`.
  - `DEADLINE` chỉ kiểm tại `i = 0`. Đây là nguồn của KD3.
- F2.3 — **Dựng message** theo từng batch trên thread điều phối. Kết quả gồm `by_id`, `messages`, `injection_count`.
  - Kích thước batch đọc `PAIRS_PER_CALL` của module **lúc gọi**. Không bind làm default arg, không chụp vào closure
    lúc import (F12). Nhờ vậy P3 có thể patch thuộc tính module để đổi kích thước.
  - `pairs_sent`/`injection_signals` chỉ được cộng khi consume.
- F2.4 — **Dispatch**: `ThreadPoolExecutor(max_workers, thread_name_prefix="ai2-pairs")`. Batch `i` gọi
  `runtime.complete_json(batch_client_i, …, operation="pairs", abort=gate.predicate(i), issue_sink=sink_i)`, với
  `batch_client_i = copy.copy(client)` và `traces = []`.
  - Bản sao nông dùng chung pool HTTP, nên nhánh có timeout vẫn được dùng (`ai-service/app/pipeline/runtime.py:436`).
  - Wrapper của worker gọi `gate.mark(i)` khi batch `i` trả về `None`, `ProcessingTimeout`, hoặc
    `classifier_family_ok(served_i)` sai.
- F2.5 — **Consume theo thứ tự** `i = 0..n_planned-1` trên thread điều phối, không dùng `as_completed`.
  - Lần lượt: `report_progress` → cộng `pairs_sent`/`injection` → `futures[i].result()`.
  - Gặp `ProcessingTimeout` thì `stop = "DEADLINE"` (giống `:416-417`).
  - Đi qua **cùng closure hậu xử lý** với đường tuần tự (tách từ `:418-527`), dùng `traces` của batch `i`.
  - Commit `sink_i` bằng `runtime.commit_issues(sink_i)`.
  - Tại `i = n_planned < n_total`: phát `not_sent` với `cut_reason` và `batch_id=f"batch-{batches + 1}"` (giống
    `:383-388`).
- F2.6 — **Chính sách prefix** (mặc định, D4/D14). Batch lỗi đầu tiên ở chỉ số `k`:
  - Xử lý như bản tuần tự, rồi `gate.mark(k)` và huỷ các future đang xếp hàng.
  - **Join mọi worker trước khi return.** Bỏ `sink_j` với mọi `j > k`.
  - Nếu gặp lỗi bất ngờ: `gate.mark(-1)`, join, rồi raise lại. `idp.py:527-546` sẽ ghi `PAIR_BUILD_FAILED`, giống bản
    tuần tự.
- F2.7 — **Hoàn tất**:
  - Gộp `traces` của mọi batch vào `client.traces` theo thứ tự chỉ số.
  - `stats.llm_calls` và token phản ánh chi tiêu thật (KD1).
  - `stats.served_model` lấy từ trace cuối của các batch **đã consume**.
- F2.8 — **Gate abort theo chỉ số** (`_AbortGate`, có lock). Gate lưu `failed_at = min(chỉ số lỗi)`; predicate của
  batch `j` trả `True` khi `failed_at is not None and j > failed_at`. Đây là **cơ chế duy nhất** chặn retry/request
  của batch pairs.
- F2.9 — **Runtime** (`runtime.py`):
  - **Lock**: `add_issue` và `_fall_back` chạy dưới `_state_lock`. Mỗi lần chỉ lấy lock một lần, không lồng nhau.
    Thêm `commit_issues(sink)`.
  - **API**: `complete_json(..., abort: Callable[[], bool] | None = None, issue_sink: list[tuple[str, str]] | None = None)`.
    Mọi `_fall_back` bên trong đi qua một closure: có sink thì ghi vào sink, không thì ghi vào runtime. Mặc định
    `None` giữ nguyên hành vi cho 5 caller hiện có.
  - **Reserve**: `_reserve_http_request`, dưới `_request_lock`, kiểm theo thứ tự deadline → cancelled → `abort()` →
    budget. Nếu `abort()` trả `True` thì raise `LLMRequestCancelled` (exception mới). `complete_json` bắt exception
    này và trả `None`, **không** thêm issue.
  - `abort()` còn được kiểm ở đầu mỗi lần thử và ngay sau `self.sleep(delay)`.
  - **Reserve không kiểm `provider_exhausted`** (F2). Batch `j < k` đang ngủ backoff khi một batch khác cạn quota vẫn
    retry tới provider thật:
    - provider phục vụ → batch thành công, giống bản tuần tự;
    - provider trả quota → `_quota_exhausted` → `LLM_QUOTA_EXHAUSTED` ghi vào sink **của chính batch đó**, batch đó
      thành `k` mới, issue được commit.

    Chốt `provider_exhausted` ở đầu `complete_json` (`:332-333`) vẫn giữ cho lời gọi mới, ví dụ stage semantic sau
    pairs.
  - **Jitter**: thêm field `jitter: Callable[[], float] = random.random`. Công thức
    `delay = base + jitter() * min(1.0, 0.5 * base)`, áp cho cả Retry-After (coi là mức tối thiểu) lẫn backoff mũ
    (`:388-390`).
- F2.10 — **Client**: `last_http_calls` thành biến local, gán vào `self.last_http_calls` ở mọi đường thoát
  (`ai-service/app/llm/client.py:182-243`; D12, không lock). Giữ được `tests/test_llm_gpt5_params.py:201`.
- F2.11 — **Thí nghiệm D4**. `classify_pairs(..., failure_policy="prefix")` nhận thêm `"keep_successful"`, chỉ dùng
  cho thí nghiệm:
  - Không đọc từ env. `build_pair_relations` (`pair_builder.py:172-180`) không truyền tham số này.
  - Đi kèm `concurrency == 1` thì báo `ValueError`.
  - Ngữ nghĩa: consume mọi batch đã lập kế hoạch; batch lỗi ghi `no_answer` với stop của chính nó; `stopped_reason` là
    stop đầu tiên; không dùng gate; commit mọi sink theo thứ tự chỉ số.
  - User bác bỏ thì xoá trong follow-up.
- F2.12 — **Harness** `ai-service/fixtures/perf/pairs_replay.py`. Có guard router-only (D13). File ghi ra luôn nằm
  ngoài repo. Mỗi lệnh in `calls=`.
  - `record --request-file F --runs N --label L`: dùng `RecordingClient` (subclass `NineRouterClient`), concurrency
    5, ghi theo batch các trường: tập pair id, response, `served_model`, `latency_ms`. Kết quả ghi ra
    `$HOME/.ai2-perf/pairs-rec-<L>-<i>.json`.
  - `measure --request-file F`: chạy in-process, in wall của stage pairs với concurrency hiệu lực. Dùng để so sánh
    tuần tự với song song khi chẩn đoán. Lệnh này **không** dùng làm bằng chứng cho công tắc quay về (F1).
  - `simulate --recordings <glob>`: chạy offline. Ma trận gồm `k` × kind {provider_error, deadline,
    served_model_rejected, quota} × policy {prefix, keep_successful}, cộng một lượt không lỗi.
- F2.13 — **Compose và docs** (D9, F1):
  - Thêm `AI2_PAIRS_CONCURRENCY: ${AI2_PAIRS_CONCURRENCY:-5}` vào `environment:` của `ai2-service` trong
    `docker-compose.yml` (`:577-615`) và `deploy/compose.prod.yml` (`:152-180`).
  - Thêm vào `deploy/.env.prod.example` dòng `AI2_PAIRS_CONCURRENCY=5` kèm chú thích "1 = quay về tuần tự".
  - Sửa comment sai ở `deploy/.env.prod.example:91-92`: ai2-service ở prod chỉ nhận key trong `environment:` của
    `deploy/compose.prod.yml`, vì `env_file` đã bị reset ở `:151`.
  - `docs/ai2/AI2-20-contract-graph-pairs.vi.md`: thêm dòng env (`:12-18`), thêm mục "Song song hoá phân loại cặp"
    gồm INV, KD1–KD6 và cách quay về ở prod/local.
  - `ai-service/.env.example`: thêm một dòng mô tả, chỉ có giá trị khi chạy ngoài compose.
- F2.14 — **Test render compose**: tạo `deploy/tests/test_ai2_pairs_env_passthrough.py`, chạy trong CI ở
  `.github/workflows/deploy-config.yml:65-72` (đã có PyYAML).
  - (a) **Tĩnh, luôn chạy**: parse YAML của cả hai file compose (loader nhận tag `!reset`), assert key
    `AI2_PAIRS_CONCURRENCY` có trong `services.ai2-service.environment`.
  - (b) **Render**, skip khi không có `docker` CLI:
    - Lệnh prod: `docker compose -f docker-compose.yml -f deploy/compose.prod.yml --env-file deploy/.env.prod.example config ai2-service`.
      Các biến `:?` bắt buộc được đặt giá trị giả trong env của subprocess, theo repro F1.
    - Lệnh local: `docker compose -f docker-compose.yml config ai2-service`.
    - Assert env đã render chứa `AI2_PAIRS_CONCURRENCY: "1"` khi subprocess đặt `AI2_PAIRS_CONCURRENCY=1`, và `"5"`
      khi không đặt.
    - Cũng assert render prod **không** có `OPENAI_API_KEY`, vì `env_file` đã bị reset.

**Sai khác đã biết** (ghi vào docs và báo cáo D4, F6/D14)

| ID | Sai khác so với tuần tự | Tất định? | Khi nào |
|---|---|---|---|
| KD1 | `llm_calls_used`, `stats.llm_calls`, token và `llm_timing` gồm cả HTTP đã chi cho batch bị bỏ, nên cao hơn | có (theo vector kết quả) | failure path |
| KD2 | Tranh chấp slot budget cuối khi có retry. Tuần tự: batch `k+1` dừng với `BUDGET_EXHAUSTED`, không phát issue. Song song: batch nào thức dậy sau thì reserve raise `LLMRequestBudgetExceeded`, ra `LLM_FALLBACK` kèm issue `LLM_BUDGET_EXCEEDED`. **Batch nào thua phụ thuộc thứ tự thức dậy có jitter**, nên relation/stop/issue có thể khác giữa các lần chạy | **không** | budget sát trần, có retry |
| KD3 | DEADLINE kiểm lúc submit, nên song song có thể hoàn tất các batch mà bản tuần tự đã cắt (phủ nhiều hơn) | có (theo đồng hồ) | `remaining()` nằm trong khoảng [165s, 165s + tổng latency trước đó] |
| KD4 | HTTP đang bay khi abort vẫn chạy xong và vẫn tính phí; chỉ retry và request mới bị chặn. Join chờ tối đa 1 latency | có | failure path |
| KD5 | Batch bị bỏ vẫn mang event `not_sent` dù thực tế đã gửi. Giữ vậy để event giống bản tuần tự | có | failure path |
| KD6 | Quota cạn giữa chừng: batch `j < k` retry sau thời điểm cạn có thể nhận quota thật và thành `k`, nên mất relation `j..k-1` mà bản tuần tự (retry sớm hơn) giữ được. Issue `LLM_QUOTA_EXHAUSTED` vẫn có mặt | **không** (phụ thuộc trạng thái provider lúc retry) | 429 tạm thời trùng thời điểm quota bị lật |

**Bất biến** (test phải khoá)

- INV-1 — Happy path, bất kể thứ tự hoàn tất: song song (5) và tuần tự (1) giống nhau ở `decisions`, chuỗi event,
  toàn bộ `stats`, `stopped_reason`, `batches_completed`, `runtime.issues`, `fallback_count` và thứ tự
  `client.traces`.
- INV-2 — Failure path **không phụ thuộc thời điểm**, tức kết quả của mỗi batch chỉ là hàm của nội dung batch đó.
  - Các loại được tính: lỗi provider cố định, `None`, K-a, `ProcessingTimeout` do fake ném, và quota khi các batch
    `j < k` thành công ngay lần thử đầu.
  - Song song và tuần tự giống nhau ở mọi trường của INV-1, trừ `{stats.llm_calls, stats.prompt_tokens,
    stats.completion_tokens, runtime.llm_calls_used}`; các trường này chỉ được phép ≥ (KD1).
  - **Không áp dụng** cho KD2, KD3, KD6.
- INV-3 — Sau khi return, không còn thread `ai2-pairs*` nào sống, và `llm_calls_used` không đổi nữa.
- INV-4 — `served_model` và dòng log `ai2.llm_call` của batch `i` chỉ đến từ chính lời gọi của batch `i`.
- INV-5 — `llm_calls_used ≤ max_llm_calls` luôn đúng.

**Quy ước test** (F3/F13)

- Chỉ được ghim `concurrency=1` cho một test khi đủ cả ba điều kiện:
  - (a) fake phụ thuộc thứ tự gọi do thiết kế của chính test;
  - (b) có comment ghi root cause;
  - (c) có test tương đương ở `test_contract_graph_pairs_parallel.py`.
- **Cấm** ghim một test đỏ vì lỗi production. Ví dụ: `test_luong1_edges_excluded_from_candidates`
  (`tests/test_contract_graph_pair_builder.py:137-140`) phải xanh ở mặc định 5. Không ghim cả module.
- Assert "không gọi LLM" phải dùng `runtime.llm_calls_used` hoặc state dùng chung giữa các bản sao (`llm.prompts`),
  không dùng bộ đếm int trên instance client (`llm.calls`).

**Phi chức năng**

- NF2.1 — Không có trần budget riêng cho pairs (D3).
- NF2.2 — Không đổi wire, schema, event schema hay tập key `stats`.
- NF2.3 — `report_progress` chỉ gọi từ thread điều phối.
- NF2.4 — Không thêm dependency mới.
- NF2.5 — Không sửa `ai-service/.env` hay `.env` gốc (D13).

## Related Code Files

- **Sửa**:
  - `ai-service/app/pipeline/contract_graph/pair_classifier.py`
  - `ai-service/app/pipeline/runtime.py`
  - `ai-service/app/llm/client.py`
  - `ai-service/tests/test_contract_graph_pair_classifier.py`
  - `ai-service/tests/test_st067_bounded_jobs.py`
  - `ai-service/tests/test_contract_graph_pairs_idp_integration.py`
  - `ai-service/.env.example`
  - `docs/ai2/AI2-20-contract-graph-pairs.vi.md`
  - `docker-compose.yml`
  - `deploy/compose.prod.yml`
  - `deploy/.env.prod.example`
- **Tạo**:
  - `ai-service/tests/test_contract_graph_pairs_parallel.py`
  - `ai-service/tests/test_runtime_concurrency.py`
  - `ai-service/fixtures/perf/pairs_replay.py`
  - `deploy/tests/test_ai2_pairs_env_passthrough.py`
- **Báo cáo** (trong thư mục plan): `reports/phase-2-measurement.md`, `reports/phase-2-failure-policy-experiment.md`.
- **Xoá**: không có.

## File inventory (deep)

| Hành động | Path | Cỡ ước lượng | Ảnh hưởng test |
|---|---|---|---|
| Sửa | `.../contract_graph/pair_classifier.py` | +180/−60 | toàn bộ test classifier và file song song mới |
| Sửa | `ai-service/app/pipeline/runtime.py` | +70/−15 | st067, frame_context, budget_fairness, llm_complete_json |
| Sửa | `ai-service/app/llm/client.py` | +8/−8 | `test_llm_gpt5_params.py:201` |
| Sửa | `ai-service/tests/test_contract_graph_pair_classifier.py` | +15 | fake `Runtime` (`:38-69`) có lock; ghim từng test theo quy ước, ứng viên: `:383`, `:429`, `:441` |
| Sửa | `ai-service/tests/test_st067_bounded_jobs.py` | +1 | `_runtime` (`:101`) thêm `jitter=lambda: 0.0`, giữ assert `:132` |
| Sửa | `ai-service/tests/test_contract_graph_pairs_idp_integration.py` | 2 dòng | `:34` thành `llm.prompts == []`; `:152` thành `runtime.llm_calls_used == 0` (F13) |
| Sửa | `docker-compose.yml`, `deploy/compose.prod.yml` | mỗi file +1 | `deploy/tests` |
| Sửa | `deploy/.env.prod.example` | +3/−2 | — |
| Sửa | `ai-service/.env.example`, `docs/ai2/AI2-20-…` | +3 / +40 | — |
| Tạo | `ai-service/tests/test_contract_graph_pairs_parallel.py` | ~450 | mới |
| Tạo | `ai-service/tests/test_runtime_concurrency.py` | ~200 | mới |
| Tạo | `ai-service/fixtures/perf/pairs_replay.py` | ~280 | R2.13 |
| Tạo | `deploy/tests/test_ai2_pairs_env_passthrough.py` | ~110 | mới, chạy trong CI deploy-config |

Phase có 15 file, vượt ngưỡng 8. Lý do giữ nguyên trong một phase:
- 8 trong số đó là sửa từ 1 đến 40 dòng (compose, env example, docs, ghim/assert test).
- D1 giới hạn 3 phase.
- Compose và test render phải đi cùng code đọc knob, nếu không công tắc quay về sẽ không có thật.

## Dependency map (deep)

- **Phụ thuộc vào**: P1, cụ thể là `replay_job.py`, `_state_lock`, `_reserve_http_request(reserved=…)`,
  `_log_call(…, trace)`, `llm_timing`, `job_timing.pipeline_ms` và baseline `p1-baseline`.
- **Phase phụ thuộc vào P2**: P3. P3 cần đường song song, các primitive của `pairs_replay`, `p2-parallel` (phần
  overhead), và file test render (P3 mở rộng thêm key effort).
- **Phụ thuộc ngoài**:
  - Router chịu được 5 request đồng thời với batch thật. Hiện là [ASSUMED]; bước 1 sẽ probe.
  - Docker CLI để chạy render test. Ở CI đã có, local cũng đã có.

## Implementation Steps

0. **Baseline chất lượng trước khi đổi code** (F10). Chạy trên code P1, trong container:
   `MSYS_NO_PATHCONV=1 docker exec -w /app ai2-graph-full-ai2-service uv run --no-sync python -m fixtures.seeded.run_live --repeats 1`.
   - Ghi exit code và bảng `hits`/`miss_stage` theo từng must-relation (B0) vào `reports/phase-2-measurement.md`.
   - B0 đỏ thì đó là trạng thái có sẵn từ trước, không quy cho P2, nhưng phải ghi lại.
   - Lý do cần B0: golden không phủ đường LLM của pairs.
1. **Probe tải thật trước khi refactor** (F8). Dùng script tạm ở `/tmp/ai2-perf/probe_batches.py`, không commit, chạy
   trên code P1:
   - Lấy 40 `ClassifierPair` của hồ sơ tham chiếu bằng cách spy `classify_pairs` trong `build_pair_relations`.
   - Dựng 5 user message theo đúng format `:392-406`.
   - Gọi `client.complete_json(SYSTEM_PROMPT, user)` trên 5 bản sao client: một lần tuần tự, một lần song song bằng
     `ThreadPoolExecutor`.
   - Script có guard router. Ghi latency và served model từng lời gọi.
   - Dừng và báo user (R3) nếu song song không nhanh hơn ít nhất 2×, hoặc served model đổi họ.
2. **Viết test trước** (Tests Before).
3. **`runtime.py`** theo F2.9.
4. **`client.py`** theo F2.10.
5. **`pair_classifier.py`**:
   - Tách `_plan_batches`, `_batch_messages` (đọc `PAIRS_PER_CALL` lúc gọi) và closure `consume` (không đổi logic).
   - Thêm `_pairs_concurrency()`, `_AbortGate`, dispatcher, guard `n_planned == 0` và `failure_policy`.
6. **Test**:
   - Làm fake `Runtime` trong `test_contract_graph_pair_classifier.py` an toàn luồng.
   - Ghim từng test theo quy ước, có comment root cause.
   - Thêm jitter 0 cho helper st067.
   - Sửa 2 assert F13.
   - Chạy suite pairs builder/consent/idp/projection/wire ở mặc định 5, 3 lần liên tiếp để bắt flaky.
7. **`fixtures/perf/pairs_replay.py`** theo F2.12.
8. **Compose, env example, docs, `deploy/tests`** theo F2.13–F2.14.
9. **Gate**:
   - Regression gate.
   - `python -m pytest deploy/tests -q` từ gốc repo.
   - Golden.
   - Ruff.
10. **Đo lại**:
    - Preflight `RUNNING=0`, rồi recreate container bằng compose (lần đầu có knob trong `environment:`).
    - `printenv AI2_PAIRS_CONCURRENCY` phải ra `5`.
    - Replay `p2-parallel` N=5.
    - Ghi `reports/phase-2-measurement.md`: so với `p1-baseline` và với bảng baseline của plan.md; thêm `llm_ms_max`
      của pairs và `calls=`.
11. **Kiểm công tắc quay về qua đường cấu hình thật** (F1):
    - Preflight `RUNNING=0`.
    - Recreate với shell env `AI2_PAIRS_CONCURRENCY=1` (giao thức bước 2), kiểm `printenv AI2_PAIRS_CONCURRENCY` ra
      `1`, chạy replay N=1, rồi recreate về mặc định và kiểm lại ra `5`.
    - Kết quả mong đợi: pairs wall ≥ 3× median pairs của `p2-parallel`.
12. **Quality cuối P2** (F10):
    - Chạy `run_live --repeats 1` hai lần, lần lượt với `AI2_PAIRS_CONCURRENCY=1` và `=5`. Dùng
      `docker exec -e AI2_PAIRS_CONCURRENCY=<n>`; ở đây chạy in-process là phù hợp, vì mục đích không phải chứng minh
      cấu hình deploy.
    - So với B0. Nếu một must-relation trượt ở `=5` trong khi trúng ở cả B0 và `=1`: chạy lại riêng hồ sơ đó 2 lần
      trước khi kết luận lỗi do P2.
13. **Thí nghiệm D4**:
    - Chạy `pairs_replay record --runs 3` rồi `simulate`.
    - Chạy SQL tần suất:
      `select count(*) filter (where s in ('LLM_FALLBACK','DEADLINE')), count(*) from (select jsonb_path_query_first(result_json::jsonb, 'strict $.**.pairs.stopped_reason')#>>'{}' s from ai2.jobs where jsonb_path_query_first(result_json::jsonb, 'strict $.**.pairs.mode')#>>'{}' = 'llm') t`.
      Giá trị tham chiếu của red-team là `4|17`.
    - Viết `reports/phase-2-failure-policy-experiment.md` gồm:
      - bảng metric (mục dưới);
      - tần suất thật;
      - KD1/KD4 quy đổi theo tần suất, tức số HTTP thêm và thời gian chờ trên mỗi job lỗi (F11);
      - phạm vi tất định: INV-2 đúng ở đâu, KD2/KD3/KD6 không đúng ở đâu (F6/D14);
      - khuyến nghị.
    - Hỏi user bằng AskUserQuestion. Không có TTY thì ghi `PENDING_USER`. Mặc định vẫn là prefix.
14. **Ngân sách**:
    - Cộng dồn `calls=` vào báo cáo. Ngân sách P2 là 173–455 lời gọi; vượt 1.5× thì dừng và hỏi user.
    - Nếu p90 phần ngoài pairs > 20s thì báo user (R1). P3 vẫn chạy (D11).

### Thí nghiệm D4: số liệu bắt buộc

Mỗi ô là median qua 3 bản ghi, tính cho từng `(k, kind)` và cho cả hai policy.

| Nhóm | Metric |
|---|---|
| Lời gọi lãng phí | `calls_wasted` (HTTP chi cho batch có kết quả bị bỏ) và `http_calls_spent` |
| Relation giữ được | `relations_total`, `relations_by_label`, chênh lệch so với lượt không lỗi, `pairs_unclassified`, `batches_completed` |
| Cổng họ model | Dưới keep với `served_model_rejected`: số batch được chấp nhận sau batch bị K-a chặn |
| Ngữ nghĩa `PARTIAL_*` | `stopped_reason`, reason code (`ai-service/app/pipeline/idp.py:721-728`), `pair_relations_ran` (`idp.py:643-649`), issue `LIMITED_COVERAGE`, và câu trả lời có/không cho câu hỏi "PARTIAL còn nghĩa là phần còn lại chưa được phân loại không" |

## Test scenario matrix (deep)

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | INV-1: happy path, thứ tự hoàn tất đảo ngược | R2.1 |
| Critical | INV-2: `k ∈ {0,2,4}` × {provider None, DEADLINE fake, served_model_rejected, quota với `j<k` thành công ngay lần đầu} | R2.2 |
| Critical | INV-3: không mutation sau khi return | R2.3 |
| Critical | INV-4: served model gán đúng batch khi trace xen kẽ | R2.4 |
| Critical | INV-5 và KD2: cap đúng; batch thua có `LLM_BUDGET_EXCEEDED`; các batch trước batch lỗi đầu tiên giống tuần tự; **không** assert batch nào thua | R2.5, R2.14 |
| Critical | F3: `pairs=[]` và `n_planned=0` (budget) → không tạo executor, output giống tuần tự | R2.17 |
| Critical | F2/KD6: batch 1 ngủ backoff 429, batch 3 nhận `insufficient_quota`. Nhánh (a): retry của batch 1 thành công → `k=3`, có issue quota. Nhánh (b): retry nhận quota → `k=1`, issue quota nằm trong sink của batch 1 | R2.16, RC2 |
| High | KD3: deadline đủ lúc submit nhưng bản tuần tự sẽ cắt ở batch 2 → song song hoàn tất 5 batch. Khoá đúng sai khác này | R2.15 |
| High | Gate chặn batch 2–4, không chặn batch 0 | R2.6 |
| High | Issue/fallback an toàn luồng; issue sink và commit | RC1, RC4 |
| High | `_plan_batches` khớp predicate tuần tự | R2.11 |
| High | Render compose: key tới env container ở local và prod | D1–D3 (`deploy/tests`) |
| Medium | Wall 5×0.3s; parse env; progress; keep_successful; log theo batch; harness | R2.7–R2.10, R2.12, R2.13 |
| Medium | Jitter; `last_http_calls` theo từng lời gọi | RC5, RC6 |

### Tests Before

Các test khoá, phải PASS trước và sau khi sửa:

- [ ] TB2.1 `tests/test_contract_graph_pair_classifier.py` (sau khi làm fake an toàn luồng và ghim theo quy ước).
- [ ] TB2.2 `tests/test_contract_graph_pair_builder.py` (gồm `:137-140`, 0 ứng viên),
  `test_contract_graph_pairs_consent.py`, `test_contract_graph_pairs_idp_integration.py` (sau sửa F13),
  `test_contract_graph_pair_projection.py`, `test_contract_graph_pairs_wire.py`. Tất cả chạy ở mặc định 5, không ghim.
- [ ] TB2.3 `tests/test_st067_bounded_jobs.py`, `test_frame_context_runtime.py`, `test_context_budget_fairness.py`,
  `test_llm_complete_json.py`, `test_llm_gpt5_params.py`.
- [ ] TB2.4 Golden.

Các test hành vi mới, phải FAIL ở lần chạy đầu:

Các test dưới đây nằm trong `tests/test_contract_graph_pairs_parallel.py`, trừ RC* và D*:

- [ ] R2.1 `test_parallel_equals_sequential_happy_path_reverse_completion`. Fake tất định theo batch (key là tập
  pair id), phủ mọi nhánh hậu xử lý: accepted, unrelated, ungrounded, duplicate/unknown/missing id, abstain, explicit
  reference fallback.
- [ ] R2.2 `test_parallel_equals_sequential_with_failure[k-kind]` (chỉ các loại thuộc INV-2)
- [ ] R2.3 `test_no_runtime_mutation_after_return`
- [ ] R2.4 `test_served_model_attributed_per_batch`
- [ ] R2.5 `test_budget_cap_holds_under_parallel_retries`
- [ ] R2.6 `test_failure_blocks_only_later_batches`
- [ ] R2.7 `test_parallel_wall_time_beats_sequential` (5×0.3s: song song < 0.9s, tuần tự ≥ 1.5s)
- [ ] R2.8 `test_concurrency_env_parsing_and_sequential_fallback`
- [ ] R2.9 `test_progress_reported_in_order_from_coordinator`
- [ ] R2.10 `test_keep_successful_experiment_semantics` và `test_build_pair_relations_uses_default_policy`
- [ ] R2.11 `test_plan_batches_matches_sequential_predicate`
- [ ] R2.12 `test_llm_call_log_lines_attribute_each_batch`
- [ ] R2.13 `test_pairs_replay_guard_and_replay_matching`
- [ ] R2.14 `test_kd2_budget_contention_invariants`
- [ ] R2.15 `test_kd3_deadline_checked_at_submit`
- [ ] R2.16 `test_quota_during_lower_batch_backoff[retry_ok|retry_quota]`
- [ ] R2.17 `test_zero_planned_batches_take_sequential_path[empty|budget]`
- [ ] RC1, RC3–RC6 trong `tests/test_runtime_concurrency.py`. RC2 viết lại thành
  `test_reserve_does_not_block_on_global_provider_exhausted`: batch `j<k` vẫn retry; khi bị chặn thì chỉ bị chặn bởi
  abort predicate.
- [ ] D1 `test_compose_static_has_pairs_concurrency[local|prod]`, D2
  `test_compose_render_prod_passes_pairs_concurrency`, D3 `test_compose_render_local_passes_pairs_concurrency`, nằm
  trong `deploy/tests/test_ai2_pairs_env_passthrough.py`.

### Implement

Làm theo bước 3–8.

### Tests After

- [ ] R2.x, RC*, D1–D3 xanh; TB2.x xanh. Suite pairs chạy 3 lần liên tiếp không flaky.
- [ ] E2E `p2-parallel` N=5: 5/5 SUCCEEDED, `batches_completed=5`, `stopped_reason=null`.
- [ ] Kiểm công tắc quay về qua recreate thật đạt (bước 11).
- [ ] `run_live` cuối P2 (bước 12) không có must-miss nào quy được cho P2.

### Regression Gate

```text
cd ai-service
AI2_REQUIRE_DATABASE=false uv run --no-sync pytest -q -p no:cacheprovider -m "not live" --basetemp="$TEMP/ai2-pytest-p2"
uv run --no-sync ruff check app/pipeline/contract_graph/pair_classifier.py app/pipeline/runtime.py app/llm/client.py fixtures/perf tests/test_contract_graph_pair_classifier.py tests/test_st067_bounded_jobs.py tests/test_contract_graph_pairs_idp_integration.py tests/test_contract_graph_pairs_parallel.py tests/test_runtime_concurrency.py
uv run --no-sync ruff format --check app/pipeline/contract_graph/pair_classifier.py app/pipeline/runtime.py app/llm/client.py fixtures/perf tests/test_contract_graph_pair_classifier.py tests/test_st067_bounded_jobs.py tests/test_contract_graph_pairs_idp_integration.py tests/test_contract_graph_pairs_parallel.py tests/test_runtime_concurrency.py
cd .. && python -m pytest deploy/tests -q
```

Gate phải PASS 100%. Khuyến nghị chạy `hs:code-review` trên diff P2 trước khi sang P3.

## Success Criteria

- [ ] Regression gate xanh (gồm `deploy/tests`); golden 21/21.
- [ ] `p2-parallel` N=5: pairs p90 ≤ 0.4 × pairs p90 của `p1-baseline`; 5/5 có `batches_completed=5` và
  `stopped_reason=null`.
- [ ] Công tắc quay về được chứng minh qua compose: `printenv` ra `1`, pairs wall ≥ 3× median `p2-parallel`, sau đó
  trả về `5`. Không dùng `docker exec -e` làm bằng chứng.
- [ ] `reports/phase-2-measurement.md` có: B0, probe bước 1, p50/p90 so với baseline, `llm_ms_max`, kết quả kiểm công
  tắc, `run_live` conc 1/5 so với B0, tổng `calls=`.
- [ ] `reports/phase-2-failure-policy-experiment.md` có 4 nhóm metric, tần suất, KD1/KD4 quy đổi, phạm vi tất định
  (INV-2 so với KD2/KD3/KD6), kèm quyết định của user hoặc `PENDING_USER`.
- [ ] `grep -n "failure_policy" ai-service/app/pipeline/contract_graph/pair_builder.py` không có kết quả.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| Phá tính tất định | TB × Cao | Consume theo chỉ số, closure dùng chung, issue sink, join; INV-1/INV-2; KD2/KD3/KD6 có test và được nêu thẳng |
| Router throttle hoặc đổi provider khi chạy batch thật | Thấp–TB × Cao | Probe bước 1 trước refactor; tiêu chí `batches_completed=5`; công tắc tới được container (D9) |
| Lỗi provider làm tốn thêm HTTP và thời gian chờ (KD1/KD4) | **TB** × TB (4/17 job local lỗi ở k=0, F11) | Gate theo chỉ số, jitter; báo cáo D4 quy đổi theo tần suất; user ký nhận |
| Mất `LLM_QUOTA_EXHAUSTED` hoặc mất batch `j<k` (F2) | Thấp × TB | Reserve không chặn theo cờ toàn cục; quota ghi vào sink của chính batch; R2.16 |
| `max_workers=0` khi 0 ứng viên (F3) | TB × TB | Guard `n_planned == 0`; R2.17; cấm ghim che lỗi |
| Deadlock vì lock lồng | Thấp × Cao | Một lần lấy lock; RC1 có timeout |
| Test flaky vì fake phụ thuộc thứ tự | TB × TB | Fake an toàn luồng; ghim có điều kiện; chạy 3 lần liên tiếp |
| Render test cần docker CLI | Thấp × Thấp | Phần tĩnh luôn chạy; phần render skip khi không có CLI; CI ubuntu có docker [PRIOR] |
| Recreate container làm đổi env khác (đọc lại `.env` gốc) | Thấp × TB | Kiểm `config_files` qua `docker inspect`; preflight `printenv` cả 5 key sau recreate |
