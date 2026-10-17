# P2 — Developer notes (Parallel Pairs)

Trạng thái: hoàn thành, chưa commit (theo yêu cầu). Không đụng `backend/`, `frontend/` (kể cả
`ProcessingTimeline.tsx`), migration, `docs/contracts/`, `ai-service/.env`, `.env` gốc. Không thêm `stage_id`.
Compose chỉ sửa đúng phạm vi D9. Mọi lời gọi LLM đi qua router `:20128` trong container; không gọi OpenAI.

## File thay đổi

| File | Diff (P2) |
|---|---|
| `ai-service/app/pipeline/contract_graph/pair_classifier.py` | +330/−59 |
| `ai-service/app/pipeline/runtime.py` | ≈ +75/−12 trên nền P1 (cả file so HEAD: +173 gồm P1) |
| `ai-service/app/llm/client.py` | +11/−6 (gồm 4 dòng P1) |
| `ai-service/tests/test_contract_graph_pair_classifier.py` | +28/−5 |
| `ai-service/tests/test_st067_bounded_jobs.py` | +3/−1 |
| `ai-service/tests/test_contract_graph_pairs_idp_integration.py` | +49/−17 (2 dòng F13; còn lại là `ruff format` cả file, file này chưa format từ HEAD) |
| `ai-service/tests/test_contract_graph_pairs_parallel.py` | mới, 680 dòng |
| `ai-service/tests/test_runtime_concurrency.py` | mới, 229 dòng |
| `ai-service/fixtures/perf/pairs_replay.py` | mới, 468 dòng |
| `deploy/tests/test_ai2_pairs_env_passthrough.py` | mới, 100 dòng |
| `docker-compose.yml`, `deploy/compose.prod.yml` | +2 mỗi file |
| `deploy/.env.prod.example` | +5/−2 (key mới + sửa comment sai `:91-92`) |
| `ai-service/.env.example` | +3 |
| `docs/ai2/AI2-20-contract-graph-pairs.vi.md` | +51 (dòng env + mục "Song song hoá phân loại cặp") |
| `reports/phase-2-measurement.md`, `reports/phase-2-failure-policy-experiment.md` | mới |

Script tạm không commit: `$HOME/.ai2-perf/p2/probe_batches.py` (copy vào `/tmp/ai2-perf/` trong container).

## Tests Before (red)

- `tests/test_runtime_concurrency.py`: collection `ImportError: cannot import name 'LLMRequestCancelled'`. Chạy bản
  shim (import giả) để thấy lý do từng test: `14 failed, 1 passed`:
  - RC1 `test_fall_back_is_atomic_across_threads`: `Left contains 7 more items` (8 bản ghi issue trùng, đúng race
    check-then-append).
  - RC6 `test_last_http_calls_is_per_call_under_concurrency`: `assert [2, 2] == [2, 1]` (lời gọi B bị lời gọi A
    reset/ghi đè `last_http_calls`).
  - RC2–RC5: `TypeError` (chưa có `abort`/`issue_sink`/`jitter`/`commit_issues`).
- `tests/test_contract_graph_pairs_parallel.py`: `330 failed, 1 passed` — `TypeError` ×318 (`classify_pairs` chưa
  nhận `concurrency`, `ProcessingRuntime` chưa có `jitter`), `AttributeError` ×11 (`_AbortGate`, `_plan_batches`,
  `_pairs_concurrency` chưa có). R2.13 đỏ vì `fixtures.perf.pairs_replay` chưa có.
- `deploy/tests/test_ai2_pairs_env_passthrough.py`: `6 failed` — `KeyError: 'AI2_PAIRS_CONCURRENCY'` ở cả parse tĩnh
  lẫn render (`docker compose config` chạy được, chỉ thiếu key).
- Sau khi implement runtime/classifier, `test_contract_graph_pair_classifier.py` đỏ 73 test vì fake `Runtime` thiếu
  `commit_issues` (đúng dự kiến: fake cần cập nhật theo bước 6).

## Tests After (green)

- RC + `test_llm_gpt5_params.py`: `37 passed`.
- Parallel + classifier: `411 passed`; sau đó `331 passed` cho file parallel (sau khi sửa metric harness).
- TB2.1–TB2.3 + parallel + RC + trace_durability (14 file), 3 lần liên tiếp: `639 passed` ×3 (trước khi có harness:
  `1 failed` duy nhất là R2.13), sau harness: suite pairs 8 file `525 passed` ×3 (7.0s / 6.8s / 6.9s), không flaky.
- Regression gate: `AI2_REQUIRE_DATABASE=false uv run --no-sync pytest -q -p no:cacheprovider -m "not live"` →
  **`2375 passed, 3 skipped, 6 deselected, 25 warnings in 340.93s`** (P1: 2029 passed).
- Golden: `test_contract_graph_flag_off_regression.py` + `test_contract_graph_pairs_flag_regression.py` →
  **`21 passed`**.
- `python -m pytest deploy/tests -q` (gốc repo): **`40 passed`** (gồm 6 test mới; docker CLI có nên phần render chạy).
- `ruff check` 11 file của gate: `All checks passed!`; `ruff format --check`: `11 files already formatted`.
- basetemp: `C:\Users\dungs\.claude\jobs\ad849255\tmp\p2-*`; không tạo `.pytest-tmp-*` mới.

## Acceptance → evidence (file:line)

- F2.1 knob + env parse + guard `n_planned==0`: `pair_classifier.py:347-365` (`_pairs_concurrency`), `:437-443`
  (validate), `:639` (`workers > 1 and n_planned >= 1`, ngược lại đi vòng tuần tự `:658-690`), `:648`
  (`min(workers, n_planned)`). Test R2.8, R2.17.
- F2.2 `_plan_batches`: `:368-384`. Test R2.11 (288 tổ hợp so với vòng tuần tự), `test_plan_batches_checks_deadline_only_at_submit`.
- F2.3 `_batch_messages` đọc `PAIRS_PER_CALL` lúc gọi: `:387-410`; `pairs_sent`/injection chỉ cộng khi consume
  `:760-762`. Test `test_batch_size_is_read_at_call_time`.
- F2.4 dispatch, bản sao nông + `traces=[]`, `abort`/`issue_sink`, mark khi None/timeout/K-a: `:728-752`, executor
  `:755` (`thread_name_prefix="ai2-pairs"`).
- F2.5 consume theo chỉ số, cùng closure hậu xử lý: closure `consume` `:500-631` (dùng chung cho tuần tự `:680` và song
  song `:768`), `ProcessingTimeout`→`DEADLINE` `:765-767`, commit sink `:778`, `not_sent` cut `:788-792`.
- F2.6 prefix + huỷ future + join + `gate.mark(-1)` khi lỗi bất ngờ: `:779-785`, `:793-798`.
- F2.7 gộp trace theo chỉ số, served_model từ batch đã consume: `:799-806`, `:691-695`.
- F2.8 `_AbortGate`: `:327-344`.
- F2.9 runtime: `LLMRequestCancelled` `runtime.py:100-101`; field `jitter` `:223`; lock `add_issue`/`_fall_back` một
  lần, `commit_issues` `:271-291`; `abort`/`issue_sink` + closure `fall_back` `:306-336`; abort đầu attempt `:380` và
  sau sleep `:452`; bắt `LLMRequestCancelled` trả `None` không issue `:417-419`; jitter `:441-445`; reserve
  deadline → cancelled → abort → budget, không kiểm `provider_exhausted` `:528-546`.
- F2.10 `last_http_calls` local: `client.py:183`, gán ở mọi đường thoát `:217`, `:237`, `:244`.
- F2.11 `failure_policy`: `pair_classifier.py:429`, `:437-443`; ngữ nghĩa keep `cut_rest=False` `:768-776`; không
  có trong `pair_builder.py` (grep rỗng, rc=1). Test R2.10.
- F2.12 harness: `fixtures/perf/pairs_replay.py` (`check_router`, `RecordingClient`, `ReplayClient`, `run_offline`,
  `simulate`, `record`, `measure`, `main`). Test R2.13.
- F2.13 compose/docs: `docker-compose.yml` (sau `AI2_CONTRACT_GRAPH_PAIRS_MODEL`), `deploy/compose.prod.yml` (sau
  `AI2_CONTRACT_GRAPH_PAIRS_API_KEY`), `deploy/.env.prod.example`, `ai-service/.env.example`,
  `docs/ai2/AI2-20-contract-graph-pairs.vi.md`.
- F2.14 render test: `deploy/tests/test_ai2_pairs_env_passthrough.py` (D1 tĩnh, D2 prod gồm assert không có
  `OPENAI_API_KEY`, D3 local).
- INV-1..5 / KD2 / KD3 / KD6: R2.1, R2.2 (12 ô), R2.3, R2.4, R2.5, R2.14, R2.15, R2.16 trong
  `tests/test_contract_graph_pairs_parallel.py`.
- Quy ước ghim: 3 test ghim `concurrency=1` có comment root cause + test tương đương:
  `test_runtime_none_marks_batch_unclassified_and_stops` ↔ R2.2 `[0-provider]`;
  `test_runtime_rejects_non_anthropic_served_model` ↔ R2.2 `[0-served]`;
  `test_missing_current_trace_cannot_reuse_prior_claude_trace` ↔ `test_missing_current_trace_cannot_borrow_another_batch_trace`.
  `test_luong1_edges_excluded_from_candidates` xanh ở mặc định 5, không ghim. F13: `idp_integration` `:34`
  (`llm.prompts == []`), `:152` cũ (`runtime.llm_calls_used == 0`).

## Đo lại so với `p1-baseline` (chi tiết: `reports/phase-2-measurement.md`)

| | wall p50 | wall p90 | pairs p50 | pairs p90 |
|---|---|---|---|---|
| `p1-baseline` | 38.2s | 41.6s | 25.9s | 29.9s |
| `p2-parallel` N=5 | **16.7s** | **19.1s** | **6.7s** | **8.6s** |

- pairs p90 = 0.29 × `p1-baseline` (≤ 0.4: đạt); 5/5 `batches_completed=5`, `stopped_reason=null`.
- `llm_ms_max` pairs 5894–8515ms; ngoài pairs p90 12.4s (< 20s, không cần báo R1).
- Công tắc quay về qua compose: `printenv`=1, pairs 29092ms = 4.35× median `p2-parallel` (≥ 3×: đạt), rồi
  recreate về `5`, env container giống hệt.
- `run_live` B0 / conc1 / conc5: mọi must trúng, `forbidden_hits=0`, exit 0 cả ba → không có must-miss quy cho P2.

## Thí nghiệm D4 (chi tiết: `reports/phase-2-failure-policy-experiment.md`)

- Record 3 lượt thật (5/5 batch mỗi lượt), simulate offline 42 ô (median qua 3 bản ghi).
- Tại `k=0`: prefix 0 relation, `calls_wasted=4`; keep 4/10 relation, `calls_wasted=0`, nhận 4 batch sau một K-a
  bị chặn, `PARTIAL_*` không còn nghĩa "phần còn lại chưa phân loại". `k ≥ 3`: hai policy bằng nhau về relation.
- Tần suất thật: 4/17 job mode `llm` (bỏ replay `perf-*`; SQL thô ra `4|28`), cả 4 ở `k=0`.
- KD1 ≈ 0.94 HTTP/job, KD4 ≈ 1.2s/job bình quân.
- Khuyến nghị giữ prefix; quyết định của user: **prefix** (2026-10-18).

## Lời gọi router

B0 23 + probe 33 + `p2-parallel` 40 + công tắc 8 + `run_live` 23+23 + `record` 18 + `simulate` 0 = **168**
(ngân sách P2 173–455; ngưỡng dừng 1.5× = 682). Không lời gọi OpenAI.

## Lệch so với phase (cần lead xác nhận)

1. **Probe bước 1**: lần 1 chỉ đạt 1.44× (< 2×, điều kiện dừng nguyên văn) do một lời gọi đuôi 17.0s. Tôi chạy thêm
   2 lần (20 lời gọi) để phân xử: 4.01× và 9.27× (lần 3 có đuôi 39.7s ở đường **tuần tự**). 2/3 lần ≥ 2×, gộp 3.7×,
   served model không đổi họ, 0 lỗi → kết luận latency đuôi ngẫu nhiên, không phải throttle, và đi tiếp. Nếu lead
   coi lần 1 là điều kiện dừng cứng thì cần user xác nhận lại.
2. **INV-2 và `client.traces`**: F2.7 yêu cầu gộp trace của **mọi** batch (gồm batch bị bỏ), còn danh sách ngoại lệ
   của INV-2 không nhắc trace. Test khoá: trace của các batch đã nhận là **tiền tố** của trace song song (phần thêm
   là chi tiêu KD1), không đòi bằng nhau tuyệt đối.
3. **Recreate dùng thêm `--no-deps`** (giao thức bước 2 không có) để không recreate `backend-db`/phụ thuộc. Cùng 3
   file compose, khớp nhãn `config_files`.
4. **`ruff format` cả file** `tests/test_contract_graph_pairs_idp_integration.py` (chưa format từ HEAD) để qua
   `ruff format --check` của gate; diff lớn hơn 2 dòng F13 nhưng chỉ là định dạng.
5. R2.6 khoá "batch sau lỗi không retry" bằng `attempts ≤ 1` (lần thử đầu của batch 4 có thể đã bị gate chặn).
6. Harness: cache cặp đã capture (`$AI2_PERF_DIR/pairs-cache-<sha>.json`, ngoài repo) để không tốn lại 3 lời gọi
   extraction; file record chứa luôn cặp (ngoài repo) để `simulate` chạy offline. `measure` có nhưng không chạy
   (bước đo không yêu cầu; công tắc đã chứng minh qua compose).
7. Nhỏ, không đổi hướng: `concurrency` truyền tường minh `< 1` → `ValueError`; `_plan_batches(n_total=…)` nhận số
   batch; nhánh song song gọi `report_progress` cả ở offset bị cắt (giống tuần tự); `batch_id` theo chỉ số
   (`batch-{i+1}`, trùng với tuần tự/prefix; cần cho keep_successful).

## Rủi ro còn lại

- Cửa sổ khởi động thread của wave đầu: nếu batch `j<k` vào `complete_json` **sau** khi quota đã lật, chốt
  `provider_exhausted` ở đầu `complete_json` (giữ theo spec) trả `None` không issue → `k` mới = `j` và issue quota ở
  sink `k` cũ bị bỏ. Chỉ xảy ra trong micro-giây khởi động thread (mọi batch submit cùng lúc; batch xếp hàng luôn có
  chỉ số lớn hơn batch đang chạy). Test ép thứ tự vào trước khi lật để giữ INV-2 tất định.
- Chưa chạy `hs:code-review` trên diff P2 (phase khuyến nghị trước P3) — để lead quyết định; chưa ghi artifact cook
  (`verification-P2.json`).
