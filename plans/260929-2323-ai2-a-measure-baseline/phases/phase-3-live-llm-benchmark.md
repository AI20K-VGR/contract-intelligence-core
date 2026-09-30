---
phase: 3
title: "Live Llm Benchmark"
status: pending
plan: 260929-2323-ai2-a-measure-baseline
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 3 — Live Llm Benchmark

## Overview
Phase này đưa vào repo một benchmark live chạy OpenAI `gpt-4o-mini` với snapshot có ngày đã pin (D-A6). Benchmark chỉ nhận dữ liệu giả lập, có trần USD và trần số lời gọi, được kiểm **trước** mỗi lời gọi. Nó chạy đúng pipeline thật như P2 (`evals/real_pipeline.py`) và chấm bằng chính bộ chấm P2, nhờ vậy số live và số offline so được với nhau.

Logic cần giữ từ các script của phiên lập kế hoạch (`bench.py`: xử lý hồ sơ có và không có LLM; query lặp k lần; độ trễ, token, lời gọi) được **viết lại trong repo**. Các script cũ nằm ở thư mục tạm, không còn tồn tại (research §5), nên không tham chiếu tới chúng.

Phase cũng:
- đăng ký các marker `live`, `llm`, `integration`, `requires_pdf_fixture`;
- **cô lập `.env` khỏi suite offline**: vô hiệu `load_dotenv` và xoá các biến nhạy cảm, trừ khi opt-in (RT-12);
- thêm `response_model` vào trace của client;
- làm mỗi lượt live chạy tay đỏ khi tripwire hồi quy so với baseline live (RT-03);
- tạo báo cáo baseline `docs/ai2/AI2-16-measurement-baseline.vi.md`.

Phụ thuộc P2.

## Dependency map
- **Upstream:** P2 (`evals/real_pipeline.py`, `evals/unit_metrics.py`, `evals/value_normalize.py`, `evals/eval_types/ai2_grounded_query/units.py`, `evals/eval_types/ai2_contract_package/processing_units.py`, `evals/baselines/*.offline.json`); P1 (`evals/data/golden/manifest.json`, cờ `synthetic`).
- **Code production:**
  - `ai-service/app/llm/client.py:13-85`: `NineRouterClient`. `all_traces` là **list cấp class, sống suốt process** (`:14`), nên không được dùng để tính tiền. Fallback bỏ `response_format` làm 1 lần gọi logic thành 2 lời gọi API (`:57-70`). `max_retries=0` (`:28`).
  - Nơi gọi LLM: `ai-service/app/reasoning/l2_plan.py:158,255`, `ai-service/app/pipeline/fact.py:92-94`, `ai-service/app/pipeline/table.py:145-152`, `ai-service/app/pipeline/runtime.py:97`. Tất cả đều đi qua `complete_json`, nên subclass chặn được.
  - Embedding (`ai-service/app/llm/embeddings.py:167`) **không** đi qua `complete_json`, nên vector mode nằm ngoài phạm vi.
- **Downstream:** P4 (`.github/workflows/ai2-live-benchmark.yml` gọi `evals/scripts/run_live_benchmark.py`); B/C chạy lại benchmark để so với baseline.
- **Người:** HC-4 (cho phép chi tiêu, khoá đặt qua env), VD-5 (trần và k).

## Requirements
Chức năng:
- **F3.1 `evals/live/budget.py`: `BudgetedClient(NineRouterClient)`.**
  - Constructor nhận `model` (đã pin, dùng cho cả `strong`), `base_url`, `max_usd`, `max_calls`, `pricing`.
  - **Trước khi gọi:** ước lượng = token vào ≈ ceil(ký tự/3) + token ra dự phòng 1.000. Nếu `spent + ước lượng > max_usd` hoặc `calls + 1 > max_calls` → đặt cờ **dính** `exhausted` rồi raise `BudgetExceeded`.
  - **Sau khi gọi:** đọc `self.traces[-1]` của **instance**, cộng token/tiền theo usage thật; fallback tính 2 lần gọi.
  - Retry khi gặp 429/5xx: tối đa 3 lần, backoff mũ có jitter; ghi `retry_wait_ms` riêng; mỗi lần retry tính vào trần.
- **F3.2 `evals/live/pricing.json`:** `{model: {input_per_1m, output_per_1m}, effective_date, source, verified}`. Giá hiện là `[PRIOR]`; bước 1 đối chiếu nguồn chính thức và ghi `verified: true` kèm ngày.
- **F3.3 `evals/live/benchmark.py`:**
  - **Data guard:** chỉ nhận golden có `synthetic: true` (và `approval`, trừ khi `--draft`) cùng case catalog/`eval_suite` (allowlist hằng: fixture dựng bằng code, dữ liệu giả, research §4). Mọi đầu vào khác → exit 2 **trước** khi gọi mạng.
  - **Preflight:** thiếu khoá (`AI2_LLM_API_KEY`/`OPENAI_API_KEY`) → exit 3; với `--provider openai`, base URL phải là `https://api.openai.com/v1`; 1 lời gọi ping, `response_model` khác model đã pin → exit 3.
  - **Warm-up:** 2 câu, không tính vào mẫu độ trễ.
  - **Query:** 84 câu × k.
  - **Xử lý:** 8 snapshot golden + 95 case eval × `k_processing` (mặc định 1).
  - **Tổng hợp:**
    - Chỉ số P2 theo câu hỏi/case, **không** nhân n với k (research §3.4). `state_match` báo cả `mean` lẫn `pass^k`. Chỉ số chặn dùng quy tắc any-fail-in-k.
    - Độ trễ e2e: p50/p95/p99/max trên các lượt warm.
    - CI bootstrap 95% cho p95, **resample theo `question_id`** (B=2000, có seed), vì k lượt của cùng một câu không độc lập (RT-14).
    - `latency_p95_s` gate < 20 s, lấy tập lượt theo **VD-7**. Mặc định (a): chỉ các lượt `used_llm=true`, n ≥ 60, thiếu thì `UNDERPOWERED`. p95 gộp mọi lượt chỉ để chẩn đoán.
    - Token, chi phí trên mỗi câu và mỗi lượt; `used_llm` rate; danh sách câu đổi trạng thái giữa các lượt.
  - **Metadata:** `git_sha`, `dirty`, `golden_version`, `scorer_version`, `model_pinned`, tập `response_model`, `prompt_digest` (sha256 mã nguồn `l2_plan.py`, `fact.py`, `table.py`, `runtime.py`), k, `concurrency=1`, `pricing.effective_date`, trần, thời điểm UTC.
  - **Output** `--out` (mặc định `evals/results/live/<utc>/`, đã gitignore ở P2): `runs.jsonl` chỉ có id, trạng thái, số đếm, hash, độ trễ, token, chi phí; **không** có answer, `text_span` hay câu hỏi. Kèm `summary.json`, `summary.md`. `--review-output` ghi output đầy đủ vào `<out>/review/` (chỉ local).
  - **Diff tripwire (RT-03):** so tập đơn vị FAIL của các chỉ số tripwire (`citation_correct`, `value_fabricated`, `fact_value_fabricated`) với tập tương ứng trong `evals/baselines/ai2_live.baseline.json`, dùng quy tắc any-fail-in-k. Đơn vị FAIL mới là hồi quy.
  - **Exit:**
    - `0`: chạy xong, verdict nằm trong JSON.
    - `1`: chỉ khi có `--fail-on-threshold` và (ngưỡng tripwire trượt **hoặc** hồi quy tripwire). Với `--tripwire-only`, chỉ xét chỉ số tripwire.
    - `2`: lỗi setup hoặc data guard.
    - `3`: preflight.
    - `4`: hết ngân sách (vẫn ghi summary `status: PARTIAL`).
- **F3.4 `evals/scripts/run_live_benchmark.py`** (CLI):
  - Cờ: `--k 5 --k-processing 1 --max-usd 5 --max-calls 1000 --model gpt-4o-mini-2024-07-18 --provider openai --out --dry-run --preflight-only --limit N --draft --fail-on-threshold --tripwire-only --review-output --write-baseline --load-dotenv`.
  - `--dry-run`: in ước lượng, không gọi mạng.
  - `--write-baseline`: ghi summary và **tập id đơn vị FAIL của tripwire** (chỉ id, không text) vào `evals/baselines/ai2_live.baseline.json`. Từ chối khi có `CI`, cây bẩn hoặc `--draft`.
- **F3.5 `evals/live/dotenv_opt_in.py`:** hàm `load_env_if_opted_in(environ, path)`. Chỉ chạy khi `AI2_LIVE_TESTS=1` (hoặc `--load-dotenv`); không ghi đè biến đã có; trả **tên** biến đã nạp, không bao giờ trả giá trị.
- **F3.6 `evals/conftest.py`:** đăng ký marker `live`, `llm`, `integration`, `requires_pdf_fixture`. Áp cùng cơ chế cô lập như F3.8. Test `live` bị skip với lý do rõ khi chưa opt-in.
- **F3.7 `ai-service/pyproject.toml`:** `markers` gồm `live`, `llm`, `integration`, `requires_pdf_fixture` (PB-6: 23 cảnh báo; marker cuối dùng cho T4–T8 ở P4, RT-15).
- **F3.8 `ai-service/tests/conftest.py` — cô lập `.env` (RT-12, PB-12):**
  - Ở mức module (trước khi bất kỳ test nào import `app.api.main`), nếu `AI2_LIVE_TESTS != "1"` thì thay `dotenv.load_dotenv` bằng một hàm no-op. `app/api/main.py:10` gọi `from dotenv import load_dotenv` lúc import, nên sẽ nhận bản no-op.
  - Thêm fixture autouse gọi `monkeypatch.delenv` cho `OCR_DPI`, mọi `AI2_*`, `OPENAI_API_KEY` và `*_API_KEY`, **trừ** biến đã có sẵn trong shell cha lúc conftest nạp (lưu snapshot tên biến).
  - Khi `AI2_LIVE_TESTS=1` thì dùng `load_env_if_opted_in` (bản sao ngắn của `evals/live/dotenv_opt_in.py`, ghi rõ nguồn).
  - Chuyển `load_dotenv` sang lúc startup là thay đổi code production, nên **bàn giao cho B**.
- **F3.9 `ai-service/app/llm/client.py`:** thêm `trace["response_model"] = getattr(resp, "model", None)` ở nhánh thành công. Thay đổi additive, không đổi hành vi.
- **F3.10 `docs/ai2/AI2-16-measurement-baseline.vi.md`:**
  - mục đích, cấu hình;
  - bảng offline (từ `evals/baselines/*.offline.json`) và bảng live (từ `ai2_live.baseline.json`): mỗi chỉ số có `x/n`, Wilson 95%, trạng thái và khoảng cách tới D-A8;
  - độ trễ kèm CI; chi phí; độ ổn định;
  - tham chiếu 21/24 của phiên lập kế hoạch, kèm ghi rõ: **bị thổi phồng do rò rỉ tập test** (`l0_rules.py` ~336-394 hardcode node id của HD-TONG-HOP, PB-11), và không tái lập được vì `bench.py` không còn. Bucket `fixture_tuned_legacy` báo riêng;
  - hạn chế:
    - D-A10 một người duyệt; kèm độ đồng thuận hai nguồn (`candidate_review.py agreement`);
    - dữ liệu giả lập; số viết bằng chữ;
    - output citation thiếu bbox (PB-4);
    - các case được thực thi ngoài `stack.py`;
    - `value_fabricated` offline kém nhạy, vì answer chủ yếu trích nguyên văn (RT-03);
    - n hiệu dụng nhỏ hơn n đơn vị: 8 hợp đồng, cluster CI (RT-13);
  - map sang DOC-06 M02/M03/M04/M10; lệnh chạy lại.

Phi chức năng:
- Không log hay ghi khoá hoặc raw text hợp đồng (`docs/code-standards.md:50`).
- Mọi số trong báo cáo lấy từ JSON đã commit, không gõ tay.
- `concurrency=1`.
- Lượt baseline k=5 hết ≤ 30 phút `[ASSUMED]`.

## Related Code Files
**Create**
- `evals/live/__init__.py`, `evals/live/budget.py`, `evals/live/pricing.json`, `evals/live/benchmark.py`, `evals/live/dotenv_opt_in.py`
- `evals/scripts/run_live_benchmark.py`
- `evals/conftest.py`
- `evals/tests/test_live_budget.py`, `evals/tests/test_live_benchmark.py`, `evals/tests/test_live_openai_smoke.py`
- `ai-service/tests/test_llm_client_trace.py`, `ai-service/tests/test_offline_env_isolation.py`
- `evals/baselines/ai2_live.baseline.json` (sau lượt live HC-4)
- `docs/ai2/AI2-16-measurement-baseline.vi.md`

**Modify**
- `ai-service/pyproject.toml` (marker)
- `ai-service/tests/conftest.py` (opt-in `.env`)
- `ai-service/app/llm/client.py` (`response_model` trong trace)

**Delete**: không có.

## File inventory

| File | Hành động | Cỡ | Tác động test |
|---|---|---|---|
| `evals/live/budget.py` | C | ~180 dòng | trần, retry, fallback |
| `evals/live/benchmark.py` | C | ~350 dòng | guard, preflight, tổng hợp, output |
| `evals/live/dotenv_opt_in.py` | C | ~30 dòng | opt-in |
| `evals/live/pricing.json` | C | ~15 dòng | tính tiền |
| `evals/scripts/run_live_benchmark.py` | C | ~120 dòng | exit code |
| `evals/conftest.py` | C | ~30 dòng | marker, skip live |
| 4 file test | C | ~600 dòng | RED trước |
| `ai-service/app/llm/client.py` | M | +1 dòng | `test_llm_client_trace.py` |
| `ai-service/pyproject.toml` | M | +5 dòng | `--strict-markers` |
| `ai-service/tests/conftest.py` | M | +25 dòng (no-op `load_dotenv`, xoá env) | `test_offline_env_isolation.py`, T10 ở P4 |
| `ai-service/tests/test_offline_env_isolation.py` | C | ~40 dòng | cô lập `.env` (RT-12) |
| `evals/baselines/ai2_live.baseline.json` | C | ~10 KB | — |
| `docs/ai2/AI2-16-measurement-baseline.vi.md` | C | ~4 trang | — |

## Implementation Steps
1. **Probe trước (HC-4, tốn tiền rất ít).** Có khoá trong env, chạy một script bỏ đi đặt ở scratchpad (không commit): gọi `chat.completions.create(model="gpt-4o-mini-2024-07-18", ...)` 1 lần, in `resp.model` và `usage`. Đối chiếu giá ở trang giá chính thức. Nếu snapshot bị ngưng thì chọn snapshot có ngày hiện hành (kiểm bằng `GET /v1/models`) và ghi vào Validation Log. Kết quả chuyển `[PRIOR]` thành OBSERVED.
2. **RED.** Viết `test_live_budget.py`, `test_live_benchmark.py` (client giả, không mạng, golden mini trong thư mục tạm), `test_llm_client_trace.py`, và test cho `dotenv_opt_in` (nằm trong `test_live_benchmark.py`). Xác nhận fail.
3. Làm `dotenv_opt_in.py`, `budget.py`, `pricing.json` (giá đã đối chiếu ở bước 1), `benchmark.py`, CLI. Thêm `evals/conftest.py`, marker trong `ai-service/pyproject.toml`, opt-in trong `ai-service/tests/conftest.py`, và 1 dòng ở `client.py`.
4. **GREEN** unit/integration, không mạng.
5. `$PY evals/scripts/run_live_benchmark.py --dry-run --k 5` → ước lượng ≤ `MAX_USD` (VD-5).
6. **Smoke live (HC-4):** `$PY evals/scripts/run_live_benchmark.py --limit 3 --k 1 --max-usd 0.10 --load-dotenv` → exit 0, `response_model` khớp.
7. **Baseline live (HC-4):** chạy `$PY evals/scripts/run_live_benchmark.py --k 5 --max-usd 5 --load-dotenv --write-baseline` trên cây sạch, sau HC-1 và HC-3. Commit `evals/baselines/ai2_live.baseline.json` trong PR có label `ai2-baseline-update` (RT-01).
8. Viết `docs/ai2/AI2-16-measurement-baseline.vi.md` từ `evals/baselines/*.json`; ghi `git_sha` của lượt đo.
9. Lint file của phase, chạy regression gate, commit `feat(ai): benchmark live gpt-4o-mini có trần chi phí + báo cáo baseline`.

## TDD

### Tests Before (RED)
Test happy-path gọi `monkeypatch.delenv("CI", raising=False)`; test từ chối gọi `setenv("CI", "true")` (RT-09).

- [ ] `test_tripwire_regression_vs_live_baseline` (RT-03): baseline live không có đơn vị FAIL ở `value_fabricated`; lượt mới có 1 giá trị bịa ở 1/k lượt → với `--fail-on-threshold --tripwire-only` thì exit 1; không có cờ thì exit 0 nhưng summary ghi hồi quy.
- [ ] `test_latency_gate_population` (RT-14): 90% lượt không dùng LLM (1 ms), 10% dùng LLM (30 s) → theo VD-7(a), p95 gate lấy trên nhóm `used_llm` nên FAIL (hoặc `UNDERPOWERED` nếu n < 60), dù p95 gộp đạt. Bootstrap resample theo `question_id`.
- [ ] `ai-service/tests/test_offline_env_isolation.py::test_env_isolated_after_importing_api_main` (RT-12): khi chưa opt-in, sau `import app.api.main` thì `OCR_DPI`, `AI2_LLM_API_KEY`, `OPENAI_API_KEY`, `AI2_VECTOR_RECALL_ENABLED` không có trong `os.environ`, trừ khi đã có sẵn trong shell cha; `load_dotenv` là no-op.
- [ ] `test_budget_blocks_before_call`: trần 0 → `BudgetExceeded`; client giả ghi nhận **0** lời gọi.
- [ ] `test_budget_counts_fallback_as_two_calls`: client giả lỗi ở lần có `response_format`, lần 2 thành công → `calls == 2`.
- [ ] `test_budget_uses_actual_usage`: usage giả → `spent` tính đúng theo `pricing.json`.
- [ ] `test_budget_exhaustion_is_sticky_when_swallowed`: gọi trong một hàm `except Exception: pass` (giống pipeline nuốt lỗi) → benchmark vẫn phát hiện `exhausted`, dừng với exit 4 và summary `PARTIAL`.
- [ ] `test_retry_bounded_with_backoff`: 429 liên tiếp → đúng 3 lần retry, có `retry_wait_ms`, sleep bị monkeypatch.
- [ ] `test_budget_ignores_class_level_all_traces`: `NineRouterClient.all_traces` có sẵn 100 trace cũ → `spent` vẫn bằng 0 lúc khởi đầu (kiểm vòng đời).
- [ ] `test_preflight_model_mismatch_exit_3` và `test_missing_key_exit_3_without_network`.
- [ ] `test_data_guard_rejects_non_synthetic`: manifest `synthetic: false` hoặc path ngoài allowlist → exit 2, 0 lời gọi.
- [ ] `test_runs_jsonl_has_no_raw_text`: không có dòng text nào của snapshot hay câu hỏi xuất hiện trong `runs.jsonl`/`summary.json`; không có trường chuỗi dài hơn 64 ký tự ngoài hash.
- [ ] `test_k_aggregation`: n của chỉ số = số câu (không nhân k); `pass^k`; any-fail-in-k cho chỉ số chặn; n của độ trễ = số lượt warm.
- [ ] `test_p95_bootstrap_ci_deterministic`: cùng seed → cùng CI.
- [ ] `test_dry_run_no_network`.
- [ ] `test_dotenv_opt_in`: không có cờ → không nạp gì; có cờ → chỉ nạp biến chưa có; trả tên, không trả giá trị.
- [ ] `ai-service/tests/test_llm_client_trace.py::test_trace_records_response_model`: response giả có `model` → trace có `response_model`; các key cũ của trace không đổi.
- [ ] `test_live_openai_smoke` (`@pytest.mark.live @pytest.mark.llm`): 1 lời gọi thật với `max_usd=0.01`, `response_model == pinned`. Skip khi chưa opt-in.

### Implement
Theo bước 3.

### Tests After
- [ ] Dry-run in ước lượng ≤ trần.
- [ ] Smoke live (bước 6) exit 0.

### Regression Gate
- `$PY -m pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm" evals/tests` → 0 failed.
- `$PY -m pytest -q -p no:cacheprovider --strict-markers --import-mode=importlib evals/eval_types` → 0 failed.
- `cd ai-service; .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm" tests/test_llm.py tests/test_llm_client_trace.py tests/test_offline_env_isolation.py tests/test_llm_guardrails.py tests/test_reasoning.py` → xanh.
- `cd ai-service; .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/unit/test_core.py` → kỳ vọng T10 hết đỏ nhờ cô lập env, chạy riêng lẫn chạy cả suite. Kết quả ghi vào verification; P4 xác nhận.
- `cd ai-service; .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m "not live and not llm" --basetemp $env:TEMP\ai2pt` → danh sách fail ⊆ 16 mục của PB-6 (P3 không thêm lỗi mới). Triage ở P4.
- `$PY evals/scripts/run_ai2_gate.py --mode pr` → exit 0.
- Live (HC-4): `$env:AI2_LIVE_TESTS="1"; $PY -m pytest -q -m "live and llm" evals/tests/test_live_openai_smoke.py` → 1 passed.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Vượt trần vì lỗi bị nuốt trong pipeline | `test_budget_exhaustion_is_sticky_when_swallowed` |
| Critical | Tính tiền sai vì `all_traces` sống suốt process hoặc fallback 2 lời gọi | `test_budget_ignores_class_level_all_traces`, `test_budget_counts_fallback_as_two_calls` |
| Critical | Dữ liệu không phải giả lập bị gửi ra ngoài (D-A6) | `test_data_guard_rejects_non_synthetic` |
| Critical | Lộ raw text hoặc khoá trong artifact | `test_runs_jsonl_has_no_raw_text`, `test_dotenv_opt_in` |
| High | Đo nhầm model (alias trôi) | `test_preflight_model_mismatch_exit_3` + bước 1 |
| High | CI phóng đại vì coi k lượt là mẫu độc lập | `test_k_aggregation` |
| High | 429 làm lệch p95 mà không ai biết | `test_retry_bounded_with_backoff` (ghi `retry_wait_ms` riêng) |
| Critical | `.env` lọt vào suite offline qua `app/api/main.py:63` (RT-12) | `test_env_isolated_after_importing_api_main`, `test_dotenv_opt_in`; CI không có `.env` và không có secret |
| Critical | Lượt live không bao giờ đỏ khi LLM bịa (RT-03) | `test_tripwire_regression_vs_live_baseline` |
| High | p95 bị câu không dùng LLM pha loãng (RT-14) | `test_latency_gate_population` |
| Medium | p95 nhiễu với n nhỏ | CI bootstrap theo câu hỏi + sàn 60 lượt |
| Medium | Giá hoặc snapshot đổi theo thời gian | `pricing.json` có ngày + bước 1 |

## Success Criteria
- [ ] (test) Mọi test mới xanh. `pytest --strict-markers --collect-only -q` ở `ai-service` và `evals` → 0 lỗi marker (trước: 23 cảnh báo, PB-6).
- [ ] (test) `$PY evals/scripts/run_live_benchmark.py --dry-run --k 5` exit 0, ước lượng ≤ `MAX_USD`.
- [ ] (manual — `manual_test_anchor.py`) Lượt baseline live (HC-4):
  - exit 0; `response_model == model_pinned`;
  - lượt query warm ≥ 60 (mục tiêu 84×5 − 2 warm-up); lượt `used_llm=true` ≥ 60, thiếu thì `UNDERPOWERED` được ghi trung thực (VD-7);
  - `latency_p95_s` có CI theo câu hỏi; `cost_usd ≤ MAX_USD`;
  - baseline chứa tập id đơn vị FAIL của tripwire;
  - `status` khác `PARTIAL`.
- [ ] (invariant) `evals/baselines/ai2_live.baseline.json` đã commit, có `git_sha`, `dirty: false`, `golden_version`, `scorer_version`, `pricing.effective_date`.
- [ ] (manual — `manual_test_anchor.py`) `docs/ai2/AI2-16-measurement-baseline.vi.md` có bảng khoảng cách D-A8 cho **mọi** chỉ số (offline và live), mục hạn chế, và lệnh chạy lại.
- [ ] (test) Trace của client có `response_model`; mọi test `ai-service/tests/test_llm*.py` offline vẫn xanh.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| R3-1: `BudgetExceeded` bị L2 nuốt, đo tiếp mà không có LLM | Trung × Cao | Cờ `exhausted` dính + kiểm sau mỗi lượt → exit 4, `PARTIAL`; kết quả sau khi cạn bị loại |
| R3-2: giá hoặc snapshot `[PRIOR]` sai | Trung × Trung | Bước 1 probe + nguồn giá có ngày; preflight exit 3 |
| R3-3: không có khoá hoặc chưa được cho chi tiêu | Trung × Trung | Mọi thứ khác xong ở client giả; mục manual chờ HC-4, ghi trong verification |
| R3-4: nhiễu mạng làm p95 dao động | Cao × Thấp | Báo CI bootstrap; gate p95 chỉ ở live; ghi độ trễ LLM riêng |
| R3-5: sửa `client.py` đụng phạm vi B (LLM enablement) | Thấp × Thấp | Chỉ thêm 1 trường; B sở hữu các thay đổi LLM khác; A chạy trước B |
| R3-6: `.env` bị nạp vào lượt chạy offline (PB-12: `app/api/main.py:63` nạp ngay khi import, 11 module test import nó) | **Trung** × Cao | Conftest vô hiệu `load_dotenv` + xoá env nhạy cảm, trừ khi `AI2_LIVE_TESTS=1`; `test_env_isolated_after_importing_api_main`; bàn giao B việc chuyển `load_dotenv` sang startup |
| R3-7: `used_llm` < 60 lượt khiến gate p95 `UNDERPOWERED` | Trung × Trung | P1 có ≥ 15 câu kiểu so sánh; VD-5 có thể tăng k; ghi trung thực |
