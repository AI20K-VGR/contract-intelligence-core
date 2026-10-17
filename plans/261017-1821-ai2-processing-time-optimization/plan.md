---
id: 261017-1821-ai2-processing-time-optimization
title: "Tối ưu thời gian xử lý AI2"
description: "Đưa wall p90 của job AI2 hồ sơ lớn từ ~100s xuống <40s bằng đo đạc đủ, song song hoá batch pairs và tinh chỉnh lời gọi pairs, không giảm chất lượng phân loại."
status: completed
priority: P1
effort: "~5 ngày công + thời gian chạy LLM qua router local"
mode: hard
tdd: true
branch: feature/ai2-contract-graph
tags: [ai2, performance, contract-graph, pairs, concurrency, observability]
created: 2026-10-17
author: user:dungskbg2004@gmail.com
decisions: []
phases:
  - phases/phase-1-trace-instrumentation.md
  - phases/phase-2-parallel-pairs.md
  - phases/phase-3-pairs-call-tuning.md
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Plan: Tối ưu thời gian xử lý AI2

Evidence gốc: `plans/reports/perf-261017-1821-ai2-processing-time-debug-report.md` và
`research/00-summary.md` đến `research/06-external-guidance.md`.

Research đã ghi đè draft ban đầu ở bốn điểm:
- bỏ mục `stopped_reason MAX_CALLS`;
- không thêm `stage_id`;
- concurrency mặc định là 5 thay vì 4;
- thêm `reasoning_effort` vào bake-off.

Bản này đã sửa theo red-team (`reports/from-code-reviewer-to-planner-red-team-concurrency-budget-tests-ops-plan-review-report.md`,
F1–F14; xử lý từng mục ở `## Xử lý phát hiện red-team`) và theo các quyết định user vòng 2 (D9–D14).

Chế độ lập plan là `--hard --tdd --deep`. Không dùng `--parallel` vì ba phase là một chuỗi thẳng (xem `## Phụ thuộc`).

## Tổng quan

Job AI2 của hồ sơ lớn (400–800 ứng viên cặp) mất khoảng 100s. Stage `contract_graph_pairs` chiếm 85–90% thời gian đó,
vì nó gọi LLM tuần tự 5 lần, mỗi lần 8 cặp (`ai-service/app/pipeline/contract_graph/pair_classifier.py:375`;
`PAIRS_PER_CALL=8`, `PAIRS_MAX_CALLS=5` tại `:23-24`).

Plan có ba phase, làm lần lượt:
1. **Đo cho đủ.** Thêm timing từng lời gọi LLM và timing vòng đời job, không đổi hành vi.
2. **Song song hoá 5 batch pairs.** Output phải giống bản tuần tự trong phạm vi nêu ở INV-1/INV-2.
3. **Bake-off tinh chỉnh lời gọi pairs** trên router local, có cổng chất lượng. Không đổi default production nếu chưa
   có lần chạy xác nhận trên OpenAI `gpt-5.5` do user cho phép.

Mỗi phase kết thúc bằng việc đo lại cùng một hồ sơ lớn theo `## Giao thức đo lại`.

**Không** làm trong đợt này:
- Không đụng backend, FE, migration hay schema trace. Lý do:
  - Whitelist stage ở backend (`backend/src/contract_intelligence/infrastructure/ai_adapters.py:467-469`) làm hỏng
    toàn bộ trace khi gặp `stage_id` lạ (`:621-625`).
  - Schema trace khoá `stage_id` bằng enum (`docs/contracts/ai2.processing-trace.v1.schema.json:25`).
- File ops chỉ sửa trong phạm vi user cho phép (D9): `docker-compose.yml`, `deploy/compose.prod.yml`,
  `deploy/.env.prod.example`.

## Mục tiêu và baseline

**Mục tiêu**: hồ sơ tham chiếu đạt **wall p90 < 40s**, với N=10 lần chạy và percentile kiểu nearest-rank (phần tử thứ
`ceil(0.9·n)` sau khi sắp xếp; với n=5 thì p90 là max). Cổng chất lượng ở P3 phải xanh.

**Baseline** (OBSERVED 2026-10-17). Đọc `ai2.jobs` và `ai2.ai2_processing_trace_events` trong container
`ai2-graph-full-backend-db`, cùng nguồn với debug report:

| Tập | n | wall p50 | wall p90 | pairs p50 | pairs p90 |
|---|---|---|---|---|---|
| Debug report, stage pairs, mọi job | 24 | — | — | 4.2s | 95.4s |
| Job có `batches_completed=5` | 11 | 96.9s | 115.5s | 76.0s | 98.7s |
| Nhóm hồ sơ tham chiếu (~444KB, 468 ứng viên) | 5 | 112.3s | 156.4s | 96.9s | 100.7s |

- **Hồ sơ tham chiếu**: `job_8044308089444ed2ab436eb07d17528d` (`dos_01M4ZMW1F0MCE95QGPF04Y7MYM`).
  - `request_json` dài 444438 byte, có 468 ứng viên.
  - Wall 115.5s, trong đó pairs 98.7s.
  - `coverage.runtime.llm_calls_used=8` trước semantic, gồm 5 lời gọi pairs. Năm job cùng nhóm đều như vậy.
- **Thời gian ngoài pairs** (wall − pairs) của nhóm này: 9.6 / 10.0 / 11.6 / 16.8 / **59.5**s.
  - Con số 59.5s thuộc `job_dbf4b391…` và chưa giải thích được. P1 phải phân rã nó.
- **Ước lượng sau P2** [DERIVED từ 76–100s chia cho 5 lời gọi]:
  - pairs ≈ max của 5 lời gọi ≈ 20–25s;
  - wall ≈ 30–42s, tức sát ngưỡng;
  - P3 vẫn chạy để có biên an toàn (D11).

## Quyết định đã khoá

Đây là quyết định của user, áp dụng nguyên văn, không mở lại. D9–D14 là vòng 2, xem VL-8.

| ID | Quyết định |
|---|---|
| D1 | Đúng 3 phase: `phase-1-trace-instrumentation`, `phase-2-parallel-pairs`, `phase-3-pairs-call-tuning`. |
| D2 | P1 không migration, không đổi backend/FE, không thêm `stage_id`. Timing từng lời gọi (`llm_calls`, `llm_ms_total`, cached tokens) vào coverage trong `result_json`, **chỉ khi job có ≥1 lời gọi LLM** (bẫy hash golden flag-off). queue_wait, snapshot_load và persist vào log có cấu trúc, và vào coverage nếu đo được trước persist. Bỏ mục "stopped_reason MAX_CALLS". |
| D3 | P2 dùng `ThreadPoolExecutor`, env `AI2_PAIRS_CONCURRENCY` mặc định 5 (`1` = tuần tự). Mỗi batch có bản sao nông của client với `traces` riêng. Thu kết quả theo thứ tự, chạy lại phần hậu xử lý hiện có. Cờ abort dùng chung. An toàn luồng cho `add_issue`/`fallback_count`/`_log_call`/`last_http_calls`. Backoff có jitter. **Không** đặt trần budget riêng cho pairs. |
| D4 | Khi một batch lỗi, mặc định là chính sách tương đương tuần tự: bỏ các batch sau batch lỗi. Phương án "giữ batch thành công phía sau" chỉ là thí nghiệm có đo, chuyển cho user quyết định, không ship làm mặc định. |
| D5 | P3 bake-off theo thứ tự `reasoning_effort=low` → batch 10 → model nhỏ hơn cùng họ. Cổng chất lượng: `python -m fixtures.seeded.run_live --repeats 3`, score offline, toàn bộ suite ai-service. Theo ngữ nghĩa `/hs:bakeoff`: quyết bằng số, kết quả nằm trong dải nhiễu thì giao cho người. |
| D6 | Mọi lời gọi LLM đi qua router local (`cx/gpt-5.6-luna`). Không gọi OpenAI từ local nếu chưa hỏi. |
| D7 | Trước khi restart hay recreate container AI2, kiểm tra `ai2.jobs` không còn job `RUNNING`. |
| D8 | Mỗi phase kết thúc bằng việc đo lại cùng hồ sơ lớn, so wall p50/p90 với bảng của debug report. |
| D9 | Được phép sửa compose: thêm `AI2_PAIRS_CONCURRENCY` và `AI2_PAIRS_REASONING_EFFORT` vào `environment:` của `deploy/compose.prod.yml` và compose local (`docker-compose.yml`). Có test/check render `docker compose … config ai2-service` và assert cả hai key tới được container (không dùng `docker exec -e` làm bằng chứng). |
| D10 | Bake-off chạy trên router local. Ứng viên C3 local là `gh/gpt-5-mini` (proxy); production dùng OpenAI `gpt-5.5`. Kết quả local **không đủ** để ship thay đổi cấu hình production. Trước khi một thiết lập P3 thành default production, phải có lần chạy xác nhận trên OpenAI `gpt-5.5`, cần user cho phép tường minh **tại thời điểm đó**. Nếu C3 chỉ có ý nghĩa như đổi model khỏi `gpt-5.5` ở production thì đó là quyết định của user, không phải default. |
| D11 | P3 vẫn chạy, kể cả khi P2 đã đạt wall p90 ≤ 32s. |
| D12 | Được duyệt dùng state riêng theo từng lời gọi (không lock) cho `_log_call`/`last_http_calls`. |
| D13 | Không đụng `ai-service/.env`. Giữ guard chỉ cho phép router (router-only refusal guard). |
| D14 | Chính sách khi batch lỗi giữ như D4. Các claim về tương đương trên failure path phải đúng sự thật; nêu thẳng rằng KD2 không tất định. |

## Ràng buộc (constraint-scan)

**Zone**
- `harness/data/ownership.yaml:9 zone=docs -> docs/ai2/AI2-20-contract-graph-pairs.vi.md [IN]`
- `harness/data/ownership.yaml:16 zone=plans -> plans/261017-1821-ai2-processing-time-optimization/** [IN]`
- `ai-service/`, `deploy/` và `docker-compose.yml` không thuộc zone harness nào. Zone chỉ ràng buộc script của
  harness. Việc sửa compose dựa trên quyền user cấp ở D9.

**Stage policy**
- `harness/data/stage-policy.yaml:59`: push cần `verification`.
- `:64`: pr cần `verification`, `review-decision`, `plan-approval`.
- Mỗi node phát `verification-P<n>.json`. P3 phát thêm `review-decision.json`.

**Contract**
- Coverage là object mở (`docs/contracts/ai2.be.processing.result.v1.schema.json:542-544`).
- Backend nhận `coverage: dict[str, Any]` (`backend/src/contract_intelligence/shared/ai/persistence.py:113`).
- `prompt_version` là `Text` trong `ai2.contract_pair_relations`
  (`ai-service/app/db/migrations/versions/0006_ai2_contract_pair_relations.py:24`). Thêm hậu tố cấu hình (F7) không cần
  migration.

**Golden**
- `coverage.runtime = runtime.snapshot()` (`ai-service/app/pipeline/idp.py:568`) nằm trong hash golden flag-off
  (`ai-service/tests/test_contract_graph_pairs_flag_regression.py:32`). Vì vậy không thêm key vào `snapshot()`
  (`ai-service/app/pipeline/runtime.py:453-469`).
- Golden chạy với `egress_allowed=False` (`ai-service/scripts/capture_idp_golden.py:291`), nên **không phủ đường LLM
  của pairs** (F10). Đường đó được phủ bằng test P2 và `run_live`.

**Compose / deploy** (OBSERVED, F1)
- Production:
  - `deploy/compose.prod.yml:151` đặt `env_file: !reset []`. Container prod chỉ nhận các key trong `environment:`
    (`:152-180`). Hiện chưa có key `AI2_PAIRS_*` nào ở đó.
  - `deploy/deploy.sh:10`, `:19`, `:55` cho thấy prod nội suy từ `--env-file deploy/.env.prod`.
  - Comment ở `deploy/.env.prod.example:91-92` nói ai2-service đọc `ai-service/.env` qua `env_file`. Comment này sai
    với prod và sẽ được sửa.
- Local:
  - `docker-compose.yml:577-615` có `environment:` ghi đè `env_file` (`:572-576`). Giá trị nội suy lấy từ shell hoặc
    từ `.env` ở gốc repo (có `AI2_LLM_*`, OBSERVED tên key).
  - Hệ quả: knob local được đặt bằng shell env lúc recreate. Không sửa file secret nào.

**Log**
- App không cấu hình `logging`.
- OBSERVED: `docker logs ai2-graph-full-ai2-service` có **0** dòng `ai2.llm_call`, dù
  `job_0ff56a3b4a7040b6a38c374b55ebcdd0` đã dùng 4 lời gọi LLM.
- Vì vậy log timing phải có handler riêng.

**Code-standards**
- Không log prompt, answer hay raw contract.
- `request_json`, bản ghi lời gọi, file drift và backup đều chỉ nằm **ngoài repo** (`$HOME/.ai2-perf/`, `/tmp/ai2-perf/`).

**Môi trường đo** (OBSERVED)
- Container mount code read-only (`%TEMP%/ai2-live-source.override.yml`), nên restart là nạp code mới.
- Env hiệu lực: cả hai base URL là `http://host.docker.internal:20128/v1`, model `cx/gpt-5.6-luna`.
- Bẫy: `ai-service/.env:1` trỏ pairs về OpenAI, chỉ bị dòng `:18` che. Plan không sửa file này (D13). Mọi harness đều
  từ chối base URL không phải `:20128`.
- Key router chỉ hợp lệ trong container; từ host bị 401. Mọi lệnh LLM chạy bằng `docker exec`.

**Router** (probe trong container, 5 lời gọi JSON tối giản)

| Cách chạy | Wall |
|---|---|
| Tuần tự | 11.7s |
| Song song 5 | 2.2s |

- `served_model` giữ là `gpt-5.6-luna`, qua được cổng K-a (`ai-service/app/pipeline/contract_graph/model_family.py:35-36`).
- `copy.copy(NineRouterClient)` chạy đúng.
- Router không báo `reasoning_tokens`.
- Với batch thật thì vẫn [ASSUMED]. P2 bước 1 sẽ probe.
- Router có `gh/gpt-5-mini`.

**Failure path thật** (F11): local có 4/17 job ở chế độ LLM có `stopped_reason=LLM_FALLBACK`, `batches_completed=0`
(SQL ở P2 bước 11).

**Gate** (OBSERVED baseline)

| Gate | Kết quả |
|---|---|
| Suite `-m "not live"` (cần `AI2_REQUIRE_DATABASE=false`) | 2012 passed, 3 skipped, 6 deselected in 336.16s |
| Golden | 21 passed |
| Các suite pairs/runtime/trace/isolation | 275 passed |
| `ruff check .` toàn repo | 55 lỗi có sẵn |

Vì ruff toàn repo đã đỏ sẵn, lint chỉ chạy trên các file phase sửa. Các file đích hiện sạch.

## Features

- `llm-call-timing`: job có ≥1 lời gọi LLM thì `coverage.llm_timing` có mặt.
- `job-lifecycle-timing`: log `ai2.job_timing` nhìn thấy được; có `coverage.job_timing {snapshot_load_ms, claim_ms, pipeline_ms}`.
- `perf-replay`: một lệnh đo lại hồ sơ tham chiếu N lần, in p50/p90.
- `parallel-pairs`: 5 batch chạy song song. `AI2_PAIRS_CONCURRENCY` là công tắc quay về, tới được container cả local
  lẫn prod (D9).
- `failure-policy-experiment`: báo cáo số liệu hai chính sách khi batch lỗi, để user quyết định.
- `pairs-call-tuning`: knob `AI2_PAIRS_REASONING_EFFORT`, provenance cấu hình trong `prompt_version`, bake-off có cổng
  chất lượng, xác nhận trên OpenAI trước khi đổi default prod.

## Kiến trúc và data flow

Vòng đời job, kèm các điểm đo P1:

```text
POST /jobs/idp ─ create_or_get(created_ms) ─ BackgroundTasks
  └─ _run_wire_job (main.py:276) ─ with _JOB_SLOTS ─ [slot_wait_ms]
       └─ _run_isolated_job → spawn child (main.py:321)                 [run_ms = thời gian giữ slot]
            └─ _execute_wire_job (main.py:414)
                 verify_service_envelope + adapt (main.py:418-423)        [snapshot_load_ms]
                 JOB_STORE.claim + set_wire RUNNING (main.py:431-454)     [claim_ms]
                 run_idp (main.py:482) ─ extraction → graph → pairs → semantic → propose(coverage idp.py:627)
                                                                          [pipeline_ms; coverage.llm_timing nếu ≥1 call]
                 attach coverage.job_timing {snapshot_load_ms, claim_ms, pipeline_ms}   (trước main.py:495)
                 complete_with_snapshot (main.py:496)                     [persist_ms → chỉ log]
                 log ai2.job_timing scope=worker (finally)
       log ai2.job_timing scope=dispatch
```

Stage pairs sau P2 (`AI2_PAIRS_CONCURRENCY > 1` và `n_planned ≥ 1`):

```text
classify_pairs(pairs, client, runtime)
  plan  : (n_planned, cut_reason) = _plan_batches(...)   # predicate tuần tự, bộ đếm dự phóng used0+i; DEADLINE kiểm 1 lần
          n_planned == 0 hoặc concurrency == 1 → đường tuần tự hiện tại, không tạo executor (F3)
  build : thread điều phối dựng message theo batch (đọc PAIRS_PER_CALL lúc gọi, không bind default arg)
  submit: ThreadPoolExecutor(min(conc, n_planned)); batch i gọi runtime.complete_json(copy(client) với traces=[],
          abort=gate.predicate(i), issue_sink=sink_i)
  consume (theo thứ tự i=0..n-1): kết quả_i = futures[i].result() → closure hậu xử lý dùng chung với đường tuần tự
          → batch lỗi đầu tiên k: phát not_sent như tuần tự, gate.mark(k), huỷ future đang xếp hàng
  join  : chờ mọi worker; sau khi return, không còn mutation nào lên runtime
  commit: sink_0..k vào runtime theo thứ tự; gộp traces mọi batch vào client.traces theo chỉ số
runtime._reserve_http_request (dưới _request_lock): deadline → cancelled → abort predicate → budget → used += 1
  (KHÔNG chặn theo provider_exhausted toàn cục; batch j<k vẫn retry tới provider thật, F2)
```

Dữ liệu vào và ra theo thành phần:

| Thành phần | Vào | Biến đổi | Ra / side effect |
|---|---|---|---|
| `NineRouterClient.complete_json` (`client.py:155-275`) | system, user, timeout, `before_request` | 1–2 HTTP | dict; trace (`latency_ms`, `served_model`, token, `cached_tokens`) vào `traces` của **bản sao batch** |
| `ProcessingRuntime.complete_json` (`runtime.py:280-409`) | client, prompt, `operation`, `abort`, `issue_sink` (P2) | retry, backoff có jitter, reserve có lock | dict hoặc `None`; `llm_calls_used` (có lock); `_llm_timing` (có lock); issue vào runtime hoặc sink |
| `classify_pairs` (`pair_classifier.py:315-535`) | pairs, client, runtime, `concurrency` | plan → dispatch → consume theo thứ tự | `ClassifierOutcome` + event; `stats.prompt_version` có hậu tố cấu hình (P3) |
| `build_pair_relations` (`pair_builder.py:172-246`) | outcome | citation, dựng relation | `PairRelation.prompt_version` có hậu tố cấu hình (P3, F7) |
| `_run_idp` (`idp.py:558-627`) | `runtime.llm_timing()` | merge có điều kiện | `coverage.llm_timing` |
| `_execute_wire_job` (`main.py:414-506`) | các mốc thời gian | đo, attach | `coverage.job_timing`, log |
| Compose (`docker-compose.yml`, `deploy/compose.prod.yml`) | shell env / `deploy/.env.prod` | nội suy | `AI2_PAIRS_CONCURRENCY`, `AI2_PAIRS_REASONING_EFFORT` trong env container |

## Phases

| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | Trace Instrumentation: timing LLM và vòng đời job, harness đo lại, backup dữ liệu hồ sơ tham chiếu, baseline mới | — | M (sửa 4, tạo 5 file) |
| 2 | Parallel Pairs: song song, an toàn luồng ở runtime, compose cho `AI2_PAIRS_CONCURRENCY`, baseline `run_live`, thí nghiệm D4 | P1 | L (sửa 11, tạo 4 file) |
| 3 | Pairs Call Tuning: knob effort, provenance, bake-off theo stage, cổng chất lượng, xác nhận OpenAI có cổng, đo cuối N=10 | P2 | L (sửa 9, sửa có điều kiện 1, tạo 3 file) |

## Phụ thuộc

Chuỗi `P1 → P2 → P3`:
- P2 cần harness, `llm_timing` và baseline từ P1.
- P3 cần đường song song và `pairs_replay` của P2.
- File dùng chung chỉ bị sửa nối tiếp. Không có cặp phase nào chạy song song được, nên không áp dụng `--parallel`.
- Áp dụng `--deep` vì P2 đụng concurrency của runtime budget/fallback.

| File | P1 | P2 | P3 |
|---|---|---|---|
| `ai-service/app/pipeline/runtime.py` | sửa | sửa | sửa |
| `ai-service/app/llm/client.py` | sửa | sửa | — |
| `ai-service/app/pipeline/idp.py`, `ai-service/app/api/main.py` | sửa | — | — |
| `ai-service/app/pipeline/contract_graph/pair_classifier.py` | — | sửa | sửa (provenance; đổi hằng số nếu C2 được ship) |
| `ai-service/app/pipeline/contract_graph/pair_builder.py` | — | — | sửa (provenance) |
| `ai-service/tests/test_contract_graph_pair_classifier.py` | — | sửa | sửa nếu C2 được ship |
| `ai-service/tests/test_st067_bounded_jobs.py`, `ai-service/tests/test_contract_graph_pairs_idp_integration.py` | — | sửa | — |
| `docker-compose.yml`, `deploy/compose.prod.yml`, `deploy/.env.prod.example` | — | sửa (concurrency) | sửa (effort) |
| `deploy/tests/test_ai2_pairs_env_passthrough.py` | — | tạo | sửa |
| `ai-service/.env.example`, `docs/ai2/AI2-20-contract-graph-pairs.vi.md` | — | sửa | sửa |
| `ai-service/fixtures/perf/*` | tạo `__init__.py`, `replay_job.py` | tạo `pairs_replay.py` | tạo `pairs_bakeoff.py` |

## Giao thức đo lại (dùng chung, D7/D8)

Chạy trên Git Bash, từ gốc repo. Không chạy hai phép đo cùng lúc.

1. **Preflight**:
   - `docker exec ai2-graph-full-backend-db psql -U ci -d contract_intelligence -tAc "select count(*) from ai2.jobs where status='RUNNING'"` phải ra `0`.
   - `MSYS_NO_PATHCONV=1 docker exec ai2-graph-full-ai2-service printenv AI2_LLM_BASE_URL AI2_CONTRACT_GRAPH_PAIRS_BASE_URL AI2_CONTRACT_GRAPH_PAIRS_MODEL AI2_PAIRS_CONCURRENCY AI2_PAIRS_REASONING_EFFORT`: cả hai URL phải chứa `:20128`. Hai knob chỉ xuất hiện từ P2/P3 trở đi.
2. **Nạp code hoặc đổi env**:
   - Chỉ đổi code: `docker restart ai2-graph-full-ai2-service`.
   - Đổi knob: recreate với shell env, ví dụ `AI2_PAIRS_CONCURRENCY=1 docker compose -p ai2-graph-full -f docker-compose.yml -f "$TEMP/ai2-graph-full-compose.override.yml" -f "$TEMP/ai2-live-source.override.yml" up -d ai2-service`.
   - Danh sách file compose phải khớp nhãn `com.docker.compose.project.config_files` của container. Kiểm bằng `docker inspect` trước khi chạy.
   - Chờ container healthy.
3. **Backup và export** (một lần, ở P1, trước replay đầu tiên; F14):
   - `mkdir -p "$HOME/.ai2-perf/backup-ref"`
   - Rồi chạy, cho từng bảng `t ∈ {jobs, ai2_processing_trace_events, contract_edges, contract_graph_write_receipts, contract_pair_relations, dossier_query_snapshots}`:
     `docker exec ai2-graph-full-backend-db psql -U ci -d contract_intelligence -c "\copy (select * from ai2.$t where dossier_id='dos_01M4ZMW1F0MCE95QGPF04Y7MYM') to stdout with csv header" > "$HOME/.ai2-perf/backup-ref/$t.csv"`
   - Ghi số dòng của từng file vào `reports/phase-1-measurement.md`.
   - Export request: `docker exec ai2-graph-full-backend-db psql -U ci -d contract_intelligence -tAc "select request_json from ai2.jobs where job_id='job_8044308089444ed2ab436eb07d17528d'" > "$HOME/.ai2-perf/ref-request.json"`.
   - `MSYS_NO_PATHCONV=1 docker exec ai2-graph-full-ai2-service mkdir -p /tmp/ai2-perf && docker cp "$HOME/.ai2-perf/ref-request.json" ai2-graph-full-ai2-service:/tmp/ai2-perf/ref-request.json`.
   - **Khôi phục** (chỉ khi user yêu cầu): xoá các dòng của dossier mà replay tạo ra (`jobs.request_id like 'perf-%'` cùng trace events của các job đó). Với `contract_edges`, `contract_pair_relations`, `contract_graph_write_receipts`, `dossier_query_snapshots`: xoá dòng hiện tại của dossier, rồi `\copy ai2.<t> from stdin with csv header` từ backup. Thứ tự xoá và nạp lại theo FK là [ASSUMED]; chạy thử trong một transaction rồi rollback trước khi chạy thật.
4. **Replay**: `MSYS_NO_PATHCONV=1 docker exec -w /app ai2-graph-full-ai2-service uv run --no-sync python -m fixtures.perf.replay_job run --request-file /tmp/ai2-perf/ref-request.json --runs <N> --label <phase-label>`. Dùng N=5 cho P1/P2, N=10 cho `p3-final`.
5. **Tổng hợp**: `… replay_job summarize --label <phase-label>` in ra wall/pairs p50/p90, phần ngoài pairs (`wall_ms − pipeline_ms` và `wall − pairs`), `job_timing`, `llm_timing.by_operation.pairs`, `batches_completed`/`stopped_reason` và số lời gọi. Kết quả dán vào `reports/phase-<n>-measurement.md`.
6. **Hậu quả phụ đã chấp nhận**: replay ghi đè snapshot/relations AI2 của hồ sơ tham chiếu ở local. Có backup ở bước 3. Chỉ chạy ở local.

## Ngân sách lời gọi (F9)

Một job của hồ sơ tham chiếu tốn 8 lời gọi trước semantic, cộng semantic (0–12), tức **8–20 lời gọi**. Một lượt
`run_live` seeded tốn khoảng 6–20 lời gọi mỗi hồ sơ [ASSUMED theo seeded job OBSERVED 4 lời gọi trước semantic].

| Phase | Hạng mục | Lời gọi router |
|---|---|---|
| P1 | probe cached_tokens 1; replay 5 × (8–20) | 41–101 |
| P2 | probe tải 10; `run_live --repeats 1` ×3 (B0, conc 1, conc 5) × 5 hồ sơ × (6–20); replay 5 × (8–20); record 15; measure 10; replay kiểm công tắc 1 × (8–20) | 173–455 |
| P3, chỉ stage 1 | gate C0 dry-run 90–300; stage 1: 2 × 10 trial × (8–20); gate ứng viên thắng 90–300 (dùng lại cho G1/Regression); `p3-final` 10 × (8–20) | 420–1200 |
| P3, đủ 3 stage | cộng thêm 2 × (160–400 trial + 90–300 gate) | tới 920–2600 |
| P3, xác nhận OpenAI | chỉ khi user cho phép (D10): 3+3 trial trên hồ sơ seeded 40 ứng viên × (6–20) cộng `run_live --repeats 1` cho C0 và Cw (2 × 5 × 6–20) | 96–320 **lời gọi OpenAI** |

Cách kiểm soát:
- Tổng router là **634–1756** khi chỉ chạy stage 1, và **1134–3156** khi chạy đủ 3 stage.
- Mỗi lệnh harness in `calls=<n>`. Cook cộng dồn vào báo cáo của phase.
- Đầu P3, cook trình ước lượng cho user (AskUserQuestion) để xác nhận quota router.
- Phase nào vượt cận trên ×1.5 thì **dừng và hỏi** user.

## Ma trận test (toàn plan)

| Tầng | P1 | P2 | P3 |
|---|---|---|---|
| Unit | gom timing, `cached_tokens`, coverage có điều kiện, log timing, harness | tương đương INV-1/INV-2; KD2/KD3/KD6 có test riêng; `pairs=[]`; gate; reserve; jitter; issue sink; gán model theo batch | knob và sentinel `provider_default`, provenance `prompt_version`, guard router, quy tắc quyết định p90, assert kích thước batch |
| Integration | golden không đổi; worker có `coverage.job_timing` | suite pairs/runtime với mặc định 5 (không ghim đại trà); `deploy/tests` render compose | suite đầy đủ; `deploy/tests` render cả hai key |
| E2E/live (router) | replay N=5; log hiện | B0 cùng `run_live` conc 1/5; replay N=5; record/measure; kiểm công tắc qua recreate | trial bake-off; `gate`; `p3-final` N=10; xác nhận OpenAI (có cổng) |

## Backwards compatibility

**Wire/backend**
- Chỉ thêm key trong object mở `coverage`.
- `prompt_version` giữ nguyên `pairs-v13` khi cấu hình mặc định. Chỉ cấu hình không mặc định mới có hậu tố
  (`pairs-v13+effort-low`, `pairs-v13+batch-10`; F7).
- Không có migration, không thêm stage trace.

**Golden**
- `llm_timing` chỉ có khi có lời gọi. `job_timing` chỉ có trên đường worker.
- Golden không chạy đường LLM của pairs.

**Hành vi pairs**
- `AI2_PAIRS_CONCURRENCY=1` và trường hợp `n_planned == 0` chạy đúng đường tuần tự hiện tại.
- Mặc định 5:
  - **Happy path**: giống hệt bản tuần tự (INV-1).
  - **Failure path có kết quả từng batch không phụ thuộc thời điểm** (lỗi provider cố định, `None`, K-a, timeout do fake
    ném, quota khi batch nhỏ hơn không retry): mức cặp và issue giống hệt; chỉ bộ đếm chi tiêu khác (INV-2, KD1).
  - **Failure path phụ thuộc thời điểm** thì **không** giống, và được nêu thẳng:
    - KD2: tranh chấp slot budget cuối. **Không tất định**, vì thứ tự thức dậy có jitter.
    - KD3: DEADLINE đo tại lúc submit.
    - KD6: quota cạn giữa chừng trong khi batch nhỏ hơn đang retry.

**Compose**
- Thêm hai key vào `environment:`. Default prod giữ hành vi hiện tại:
  - `AI2_PAIRS_CONCURRENCY` mặc định `5` (hành vi mới của P2);
  - `AI2_PAIRS_REASONING_EFFORT` mặc định rỗng, nghĩa là không gửi effort, tức hành vi cũ.
- Default prod chỉ đổi sau khi xác nhận trên OpenAI (D10).

**API nội bộ**
- `ProcessingRuntime.complete_json(..., abort=None, issue_sink=None)` giữ hành vi cũ cho 5 caller hiện có.
- `classify_pairs(..., concurrency=None, failure_policy="prefix")`. `build_pair_relations` không truyền `failure_policy`.

**Không đổi**: `ai2.be.processing.result.v1`, `be.ai2.processing.request.v1`, `ai2.processing-trace.v1`.

## Out of scope

- Draft P3: chạy pairs song song với stage khác. Draft P4: xử lý Bottleneck #2. P1 chỉ đặt điểm đo cho nó.
- Trần budget riêng cho pairs (D3). Chính sách budget 20 lời gọi còn treo ở
  `plans/261016-1624-ai2-measure-classify-optimize/plan.md:47`, `:81`.
- Đổi `PAIRS_TOP_K` (`ai-service/app/pipeline/contract_graph/pair_candidates.py:28`, `:33`).
- Ship chính sách "giữ batch thành công" (D4). Stage trace mới trên UI. Migration 0009.
- Đổi model production khỏi `gpt-5.5` (D10, quyết định của user). Plan chỉ khuyến nghị.
- Sửa `ai-service/.env` hay `.env` gốc (D13). Dọn 55 lỗi ruff có sẵn.

## Acceptance (toàn plan)

- [ ] Mỗi phase red→green. Regression gate xanh:
  `cd ai-service && AI2_REQUIRE_DATABASE=false uv run --no-sync pytest -q -p no:cacheprovider -m "not live" --basetemp="$TEMP/ai2-pytest-<phase>"`
  cùng `python -m pytest deploy/tests -q` từ gốc repo (P2, P3).
- [ ] Ruff check và ruff format --check sạch trên các file phase sửa.
- [ ] Golden flag-off/graph-on xanh sau mọi phase.
- [ ] Có `reports/phase-{1,2,3}-measurement.md` với p50/p90 so với baseline (D8).
- [ ] `deploy/tests/test_ai2_pairs_env_passthrough.py` xanh: render config của local và prod, cả hai key có trong env
  container của `ai2-service` (D9).
- [ ] `p3-final` (N=10, nearest-rank) có **wall p90 < 40s**. Nếu không đạt: ghi `NOT_MET` kèm phân rã và follow-up,
  không đổi ngưỡng, không tự mở rộng scope.
- [ ] Chất lượng của cấu hình được dùng ở local:
  - `gate` (`run_live --repeats 3`) exit 0;
  - `SCORE` bằng baseline ở P3 bước 0;
  - `run_live` cuối P2 không có must-miss quy được cho P2 khi so với B0.
- [ ] Default production chỉ đổi khi có xác nhận OpenAI được user cho phép và đạt (D10). Nếu không, ghi
  `PROD_UNCHANGED` kèm lý do.
- [ ] `reports/phase-2-failure-policy-experiment.md` có 4 nhóm số liệu, tần suất thật, phạm vi tất định (KD2/KD3/KD6),
  kèm quyết định của user hoặc `PENDING_USER`. Mặc định vẫn là prefix.

## Rollback

Mỗi phase commit riêng, không squash.

| Phase | Quay về nhanh (không build) | Quay về triệt để | Tác động dây chuyền |
|---|---|---|---|
| P1 | Không cần (chỉ thêm key/log) | `git revert <P1>` rồi restart | Coverage cũ vẫn đọc được. Mất harness `fixtures/perf` |
| P2 | **Prod**: đặt `AI2_PAIRS_CONCURRENCY=1` trong `deploy/.env.prod`, chạy lại `deploy/deploy.sh` (nội suy qua `deploy/compose.prod.yml`, có sau P2). **Local**: recreate với shell env `AI2_PAIRS_CONCURRENCY=1` (giao thức bước 2) | `git revert <P2>` rồi redeploy | Không có dữ liệu bền nào phụ thuộc vào P2 |
| P3 | Đặt `AI2_PAIRS_REASONING_EFFORT=provider_default` (sentinel: không gửi effort, đúng hành vi cũ), rồi recreate hoặc redeploy. C2 (nếu đã ship) thì chỉ quay về bằng revert | `git revert <P3>` | Relation sinh ra bằng cấu hình mới có hậu tố `prompt_version` (`pairs-v13+…`), nên lọc được để chạy lại có chọn lọc (F7) |

Sau mỗi lần revert: chạy regression gate, golden và `deploy/tests`, rồi giao thức đo lại với N=3.

## Risks

| # | Rủi ro | Khả năng | Tác động | Giảm thiểu |
|---|---|---|---|---|
| R1 | Phần ngoài pairs lớn (59.5s) lặp lại, khiến <40s không đạt | TB | Cao | P1 phân rã. Nếu sau P2 p90 phần ngoài pairs > 20s, báo user (P3 vẫn chạy, D11) |
| R2 | Song song phá tính tất định | TB | Cao | Consume theo chỉ số; closure dùng chung; issue sink; join; INV-1/INV-2; test KD2/KD3/KD6 |
| R3 | Router throttle hoặc đổi provider khi chạy batch thật | Thấp–TB | Cao | P2 bước 1 probe trước refactor (script tạm); tiêu chí `batches_completed=5`; công tắc quay về tới được container (D9) |
| R4 | Lỗi provider khi song song làm tốn thêm lời gọi và thời gian chờ (KD1/KD4) | **TB** (4/17 job local lỗi ở k=0, F11) | TB | Gate theo chỉ số; jitter; báo cáo D4 lượng hoá theo tần suất thật; user ký nhận. Không có trần riêng (D3) |
| R5 | Kết quả router không chuyển sang `gpt-5.5` được | Cao | TB | Xác nhận OpenAI có cổng trước khi đổi default prod (D10); C3 chỉ là khuyến nghị |
| R6 | Router bỏ qua `reasoning_effort` | TB | TB | Stage 1 đo trực tiếp; bằng chứng phụ là median latency từng lời gọi và `completion_tokens`; kết luận `NOT_EFFECTIVE_ON_ROUTER` |
| R7 | Nhiễu đo | Cao | TB | p90 trên 10 trial xen kẽ, band bootstrap; hoà thì giao người; so với baseline cùng ngày |
| R8 | Harness gọi nhầm OpenAI | Thấp | Cao | Guard router-only ở mọi subcommand (D13); xác nhận OpenAI là subcommand riêng, có cổng ngày và quyền của user |
| R9 | Nội dung hợp đồng lọt vào git | Thấp | Cao | Mọi file dữ liệu nằm ngoài repo; báo cáo chỉ chứa số |
| R10 | Đổi default local trong `docker-compose.yml` rò sang prod | Thấp | Cao | Prod liệt kê key với default riêng (D9); `deploy/tests` assert prod render rỗng khi `.env.prod` không đặt |
| R11 | Quota router không đủ (634–3156 lời gọi) | Thấp–TB | TB | Xác nhận đầu P3; dừng khi vượt ×1.5 (F9) |

## Xử lý phát hiện red-team

Nguồn: `reports/from-code-reviewer-to-planner-red-team-concurrency-budget-tests-ops-plan-review-report.md`.
`reports/from-code-reviewer-to-planner-red-team-unattributed-plan-review-report.md` có cùng nội dung, chỉ khác ký tự xuống dòng.

| ID | Mức | Xử lý | Thay đổi / lý do chấp nhận |
|---|---|---|---|
| F1 | High | Đã sửa | D9: thêm hai key vào `environment:` của `docker-compose.yml` và `deploy/compose.prod.yml` (P2: concurrency; P3: effort), cùng `deploy/.env.prod.example` (sửa comment sai `:91-92`). `deploy/tests/test_ai2_pairs_env_passthrough.py` gồm parse tĩnh (luôn chạy) và render `docker compose … config ai2-service` (skip khi không có docker CLI), assert key tới env container. Công tắc kiểm qua recreate thật, không qua `docker exec -e`. Thêm sentinel `provider_default` để quay về "không gửi effort". Bảng Rollback đã sửa đúng cơ chế |
| F2 | Medium | Đã sửa | Bỏ kiểm `provider_exhausted` trong reserve. Chỉ gate theo chỉ số chặn batch `j > k`; batch `j < k` vẫn retry tới provider thật. Nếu provider trả quota thì `LLM_QUOTA_EXHAUSTED` vào sink của chính batch đó, và batch đó thành `k`. RC2 viết lại; thêm R2.16 (batch 1 ngủ backoff 429, batch 3 quota; hai nhánh). Sai khác còn lại do thời gian ghi là KD6 |
| F3 | Medium | Đã sửa | `n_planned == 0` thì đi đường tuần tự, không tạo executor. R2.17 (`pairs=[]`, và cạn budget nên `n_planned=0`). Bỏ ghim cả module. Quy tắc ghim: chỉ được ghim test khi fake phụ thuộc thứ tự theo thiết kế, có comment root cause, và có test tương đương ở file song song. **Cấm** ghim test đỏ do lỗi production; `test_luong1_edges_excluded_from_candidates` phải xanh ở mặc định 5 |
| F4 | Medium | Đã sửa | Metric là wall từng job (`run_idp` in-process trên hồ sơ tham chiếu), 10 trial xen kẽ mỗi ứng viên. Quyết định bằng p90 nearest-rank, band là CI bootstrap 90% của Δp90 cộng `rel_band` 5%. `bakeoff_rank.py` dùng cho preflight/ledger, verdict của nó chỉ báo cáo phụ (VL-10). Bằng chứng phụ khi hoà: median latency từng lời gọi pairs |
| F5 | Medium | Đã sửa | Điều kiện dừng dùng p90: `p90(trial incumbent) + p90(wall_ms − pipeline_ms của p2-parallel) ≤ 38s`. `pipeline_ms` được persist trong `coverage.job_timing` từ P1 |
| F6 | Medium | Đã sửa | INV-2 giới hạn ở failure không phụ thuộc thời điểm. KD2 ghi là **không tất định**, KD3 và KD6 tách riêng; test R2.14 (KD2: assert bất biến đúng, không assert batch nào thua), R2.15 (KD3), R2.16 (KD6). Backwards-compat và báo cáo D4 nêu điều này cho user |
| F7 | Medium | Đã sửa | P3: `effective_prompt_version()` gắn hậu tố `+effort-<x>` / `+batch-<n>` khi cấu hình khác mặc định; dùng cho `stats.prompt_version` và `PairRelation.prompt_version`/`PairResult.prompt_version` (`pair_builder.py:231`, `:246`). Có trước khi đổi bất kỳ default nào |
| F8 | Low | Đã sửa | P2 bước 1 dùng script tạm `/tmp` trên code P1 (dựng 5 batch thật, dispatch bản sao client). Không phụ thuộc `pairs_replay` |
| F9 | Low | Đã sửa | Bảng `## Ngân sách lời gọi`. Gate dùng lại theo SHA khi code ảnh hưởng tới pairs không đổi. Xác nhận quota đầu P3. Dừng khi vượt ×1.5 |
| F10 | Low | Đã sửa | P2 bước 0: `run_live --repeats 1` trên code P1 làm B0. Cuối P2: `run_live --repeats 1` với conc 1 và 5. Ghi rõ golden không phủ đường LLM của pairs |
| F11 | Low | Đã sửa | R4 nâng lên TB; báo cáo D4 lượng hoá KD1/KD4 theo tần suất 4/17 (đo lại lúc chạy) |
| F12 | Low (ASSUMED) | Đã sửa | P2 F2.3: đọc `PAIRS_PER_CALL` lúc gọi, không bind default arg. P3: `trial` assert kích thước batch quan sát được bằng 10 với C2, sai thì trial lỗi. Ghi kỳ vọng C2 không thắng về wall (một wave), chỉ tiết kiệm 1 lời gọi; vẫn chạy theo D5 nếu điều kiện stage đòi |
| F13 | Low | Đã sửa | Quy ước: assert "không gọi LLM" phải dùng `runtime.llm_calls_used` hoặc state chung giữa các bản sao (`llm.prompts`), không dùng `llm.calls`. Sửa `tests/test_contract_graph_pairs_idp_integration.py:34`, `:152` |
| F14 | Low | Đã sửa | Giao thức bước 3: backup CSV 6 bảng `ai2` của dossier trước replay đầu tiên, kèm quy trình khôi phục |

## Validation Log

- VL-1 | complexity: complex · 3 phase · risk: concurrency trong runtime budget/fallback | khớp `mode: hard` | giữ nguyên.
- VL-2 | Đã đóng bởi D12: dùng state riêng theo từng lời gọi cho `_log_call`/`last_http_calls`. `add_issue`/`fallback_count` dùng lock thật.
- VL-3 | queue_wait đo ở process cha nên chỉ ghi log. snapshot_load/claim/pipeline vào coverage. Chữ ký target 3 tham số được giữ (`tests/test_job_process_isolation.py:8-19`).
- VL-4 | Thí nghiệm D4 dùng ghi-rồi-phát-lại: chỉ một lần gọi router thật, các tổ hợp lỗi chạy offline.
- VL-5 | Ứng viên bake-off là biến thể cấu hình trong cùng một harness, không cần worktree cho từng ứng viên.
- VL-6 | Cờ abort dùng chung được làm theo chỉ số (`_AbortGate`). Batch `j < k` giữ quyền retry. F2 gỡ đường vòng qua `provider_exhausted`, để nguyên tắc này đúng thật.
- VL-7 | `hs-run --fact-subjects` báo `no codemap.yaml`, nên caller liệt kê bằng grep: `classify_pairs` có 1 caller production (`pair_builder.py:172`); `ProcessingRuntime.complete_json` có 5 caller trong app; các hàm nội bộ runtime không có caller nào ngoài file.
- VL-8 | Quyết định user vòng 2 (2026-10-17), trả lời red-team: D9 cho phép sửa compose cùng test render (F1). D10: bake-off local với C3=`gh/gpt-5-mini` làm proxy; prod dùng `gpt-5.5`; xác nhận OpenAI có cổng trước khi đổi default prod; C3 đổi model là quyết định của user. D11: P3 bắt buộc. D12: state riêng theo từng lời gọi. D13: không đụng `ai-service/.env`, giữ guard router. D14: chính sách lỗi giữ nguyên, claim tương đương phải đúng, KD2 không tất định. Các câu hỏi mở 1–4 của bản trước đã đóng.
- VL-9 | Ngân sách lời gọi xem ở bảng riêng (F9). Cook xác nhận quota với user đầu P3 và dừng khi vượt ×1.5.
- VL-10 | Quy tắc quyết định bake-off (F4/F5) được đăng ký trước: p90 nearest-rank trên 10 trial; band là CI bootstrap 90% (2000 lần lấy mẫu lại cho mỗi ứng viên, seed 0) của Δp90 cộng `rel_band` 0.05. Không dùng band `max−min` của `bakeoff_rank.py` làm quyết định, vì band đó thoái hoá thành hoà với thống kê đuôi (repro F4). Vẫn chạy `bakeoff_rank.py preflight`/`record`/`rank` để có ledger và báo cáo phụ. Ngữ nghĩa `/hs:bakeoff` giữ nguyên: quyết bằng số, hoà thì giao người, scoreboard đủ cả ứng viên thua.
- VL-11 | Hoà giải D10 với D13: mọi subcommand đo giữ guard router-only. Lần xác nhận OpenAI là subcommand riêng `confirm-openai`. Nó chỉ chạy khi có `--user-permission <YYYY-MM-DD>` bằng ngày hôm nay, `AI2_PERF_PROVIDER=openai`, base URL đúng `https://api.openai.com/v1` và model `gpt-5.5`. Key do user cung cấp lúc cho phép, truyền qua `docker exec -e`, không ghi log. Dữ liệu gửi đi chỉ là hồ sơ seeded (synthetic); hồ sơ tham chiếu thật không bao giờ gửi tới OpenAI.

## Câu hỏi mở

Không còn câu hỏi nào chặn việc duyệt. Cook phải hỏi user tại các cổng lúc chạy:
1. Quyết định D4 (cuối P2).
2. Xác nhận quota router (đầu P3).
3. Ứng viên hoà hoặc drift vượt band trong bake-off (P3).
4. Cho phép chạy xác nhận OpenAI trước khi đổi default prod (P3).
5. Đổi model prod nếu C3 thắng (P3, chỉ khuyến nghị).
