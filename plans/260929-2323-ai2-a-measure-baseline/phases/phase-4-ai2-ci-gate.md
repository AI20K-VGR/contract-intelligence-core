---
phase: 4
title: "Ai2 Ci Gate"
status: pending
plan: 260929-2323-ai2-a-measure-baseline
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 4 — Ai2 Ci Gate

## Overview
Phase này thay placeholder `.github/workflows/ai-service.yml:23-24` bằng CI thật cho PR, không dùng secret, gồm các bước theo thứ tự:
1. `uv sync --frozen` (mỗi job tự chạy);
2. ruff;
3. pytest offline (đã triage, `.env` bị cô lập từ P3);
4. test evals;
5. `run_ai2_gate.py --mode pr --base-ref origin/$BASE`: baseline lấy từ nhánh đích; nếu PR chạm path đã khoá thì phải có label và được CODEOWNER duyệt (RT-01).

Phase cũng thêm workflow live `ai2-live-benchmark.yml`:
- chạy khi dispatch hoặc theo lịch;
- environment `ai2-live`, deployment branch `main`;
- dùng khoá của một project OpenAI riêng có trần cứng (RT-07);
- mỗi lượt live chạy tay đỏ khi tripwire hồi quy (RT-03).

Mọi lỗi test có sẵn (16 failed + 2 lỗi collection, PB-6) đều được phân loại rõ ràng. Phase dọn lint, xoá template CI hỏng, thêm CODEOWNERS cho các path đã khoá, cập nhật tài liệu và phát `review-decision.json`.

Phụ thuộc P2 và P3.

## Dependency map
- **Upstream:**
  - P2: `run_ai2_gate.py` (`--base-ref`), baseline đã có trên nhánh đích.
  - P3: marker `requires_pdf_fixture`, `ai-service/tests/conftest.py` cô lập env (gốc của T10), `run_live_benchmark.py` (`--fail-on-threshold --tripwire-only`).
  - P1: `build_golden --check`.
  - Quy ước repo: `.github/workflows/backend-ci.yml`, `.github/workflows/pr-guard.yml` (luồng feature → `develop` → `main`), `.github/CODEOWNERS`.
- **Downstream:**
  - B/C dùng job PR làm gate hồi quy.
  - C bật `enforce_thresholds_in_pr` và làm allowlist rò rỉ về rỗng.
  - Release B/C dùng `--mode full` và tập biến thể.
- **Người:** HC-5 (environment + deployment branch, project OpenAI có trần cứng, CODEOWNERS + "Require review from Code Owners", label, mentor duyệt `/.github/`), VD-8.

## Requirements
Chức năng:
- **F4.1 `.github/workflows/ai-service.yml` (PR, không secret).**
  - Trigger: `pull_request`, và `push` lên `develop`/`main`. Paths: `ai-service/**`, `evals/**`, `docs/contracts/**`, `.github/workflows/ai-service.yml`, `.github/CODEOWNERS`.
  - Quyền và chạy song song: `permissions: contents: read`; `concurrency: ai-service-${{ github.ref }}`, `cancel-in-progress: true`.
  - Môi trường: Python 3.12. Action pin bằng SHA 40 ký tự, lấy qua `git ls-remote` (không dùng `gh`, vì môi trường này không có).
  - **Mỗi job** có `actions/checkout` (`fetch-depth: 0`), `setup-python`, `pip install uv` và `uv sync --frozen` riêng.
  - Job `lint`: `uv run ruff check . ../evals`.
  - Job `test-offline`: `uv sync --frozen --extra dev --extra web --extra mistral --extra kafka`, rồi `uv run pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm"`. Đếm số skip của `requires_pdf_fixture` và ghi vào `$GITHUB_STEP_SUMMARY` (RT-15).
  - Job `evals-offline`:
    - Chạy `pytest ... evals/tests`, rồi `... --import-mode=importlib evals/eval_types`.
    - Chạy `run_ai2_gate.py --mode pr --base-ref "origin/$BASE_REF"`. Với sự kiện push, `BASE_REF` là `github.event.before`.
    - Biến `AI2_BASELINE_CHANGE_APPROVED` được đặt bằng `${{ contains(github.event.pull_request.labels.*.name, 'ai2-baseline-update') }}` và truyền qua `env:`.
    - Upload `evals/results/gate/**` với `if: always()`; ghi summary.
  - Không dùng `pull_request_target`, không có `secrets.`.
  - Ghi chú trung thực: với sự kiện `pull_request`, GitHub chạy YAML lấy từ nhánh của PR. Vì vậy chính workflow cũng phải nằm dưới CODEOWNER (`/.github/` đã có mentor).
- **F4.2 `.github/workflows/ai2-live-benchmark.yml` (live).**
  - Trigger: **chỉ** `workflow_dispatch` (inputs `k`, `max_usd`, `limit`); **không** có `schedule` (VD-5, VD-8) và **không** có `pull_request`.
  - `permissions: contents: read`; `concurrency: ai2-live` (không cancel); `environment: ai2-live`; `timeout-minutes: 60`; action pin SHA.
  - Bước kiểm input: `max_usd` ≤ 20, `k` ≤ 5. Input đưa vào qua `env:`, không nội suy trực tiếp.
  - Lệnh chạy: `run_live_benchmark.py --provider openai --k "$K" --max-usd "$MAX_USD" --fail-on-threshold --tripwire-only --out evals/results/live/run`, với `OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}` và `AI2_LLM_BASE_URL: https://api.openai.com/v1`.
  - Upload artifact không chứa văn bản thô, giữ 90 ngày.
  - Ghi chú trung thực `[PRIOR]` → OBSERVED qua docs (PB-13): workflow chỉ chạy được khi đã nằm trên default branch. Người có quyền write chọn được ref khi dispatch, nên phải chặn bằng deployment branch `main` cộng trần cứng phía OpenAI (HC-5). Nghiệm thu theo VD-8.
- **F4.3** Xoá `evals/ci/production-evals.yml`.
- **F4.4 Triage.** Chạy lại ở bước 1 trên SHA đã commit. Mọi `reason=` trỏ về bảng trong `ai-service/README.md#triage`.

  | # | Test | Nguyên nhân (OBSERVED) | Quyết định |
  |---|---|---|---|
  | T1 | `tests/unit/test_mistral_ocr.py` (7) | thiếu `mistralai` (extra; `uv.lock` đã có, PB-13) | CI cài extra. Local: `pytest.importorskip("mistralai", reason=...)` |
  | T2 | `tests/unit/test_kafka_idp_worker.py` (lỗi collection) | thiếu `aiokafka` | như T1 |
  | T3 | `tests/unit/test_production_query.py` (lỗi collection) | `:16` import `_answer_language_instruction`, hàm này không còn tồn tại | **Sửa** theo API hiện tại. Hành vi đã bị bỏ thì xoá riêng test đó, ghi lý do |
  | T4–T5 | `tests/test_hd_gold.py::…`, `tests/test_ingest.py::…dieu_9` | thiếu `HD-TONG-HOP.sample.pdf` (`.gitignore:3`; pr-guard) | `@pytest.mark.requires_pdf_fixture` + `skipif(not exists, reason=...)`; đếm trong CI summary; issue bàn giao C có hạn chót (RT-15, accepted-risk) |
  | T6–T8 | `tests/test_structure_reconstruction.py` (3) | thiếu `AI2-TEST-MASTER.body.pdf` | như T4 |
  | T9 | `tests/test_p0_contract_baseline.py::test_p0_artifact_freezes_…` | `:22` đọc file trong `plans/…`, không có ở HEAD (còn ở `10ae216`) | **Sửa**: `git show 10ae216:<path>` → `ai-service/tests/fixtures/p0-contract-baseline.json` |
  | T10 | `tests/unit/test_core.py::test_schema_and_config` | `.env` có `OCR_DPI`, được nạp khi import `app.api.main` (PB-12; `src/contract_ocr/infrastructure/config.py:40`) | **Sửa**: conftest ở P3 cô lập env, cộng `monkeypatch.delenv("OCR_DPI", raising=False)` trong test. **Không xfail** (RT-12) |
  | T11 | `tests/unit/test_kafka_contract_compat.py::…` | `:151` `parents[3].parent.parent` đi ra ngoài repo | **Sửa**: `parents[3] / "docs" / "contracts"` |
  | T12 | `tests/integration/test_team_handoff_bundle.py::…` | `WinError 206` do `--basetemp` dài | không sửa code; Windows dùng `--basetemp $env:TEMP\ai2pt`; CI Linux phải xanh |
- **F4.5 Lint.**
  - **Trước** autofix: thêm `__all__` hoặc `# noqa: F401` cho re-export có chủ đích ở `ai-service/app/tools/jobs.py:12-20`.
  - Commit riêng: `ruff check --fix --select I001,F401,E714` trên các file không thuộc P1–P3.
  - Sửa tay, có review ngữ nghĩa và test: `app/reasoning/gold.py:48` (F841), `tests/test_p6_event_ui_convergence.py:345-347` (F601).
- **F4.6 Tài liệu.**
  - `ai-service/README.md` thêm mục "CI và kiểm thử": lệnh Windows/Linux; marker; opt-in live; bảng triage T1–T12; cách làm mới baseline (PR riêng + label + CODEOWNER); cảnh báo `[PRIOR]` rằng required check có paths filter có thể làm treo PR không chạm path.
  - `docs/code-standards.md:39-43`: marker đã đăng ký; eval chạy trên pipeline thật; gate một lệnh kèm bảng exit code; `.env` bị cô lập trong test; `--basetemp` ngắn.
- **F4.7 `evals/tests/test_ci_workflows.py`** (RT-10):
  - Đọc trigger bằng `triggers = wf.get("on", wf.get(True))`, vì PyYAML parse `on` thành `True`. Assert `triggers` khác rỗng.
  - Workflow PR: không có `secrets.`, không có `pull_request_target`, `contents: read`. Mỗi job có `uv sync` và `fetch-depth: 0`. Có `--base-ref`, `--strict-markers`, `run_ai2_gate.py --mode pr`. Label chỉ đi qua `env:`.
  - Workflow live: trigger = {`workflow_dispatch`} (không `schedule`), `environment: ai2-live` (deployment branch `main`), có bước kiểm trần, có `--fail-on-threshold --tripwire-only`, input qua `env:`.
  - Mọi `uses:` có dạng `@[0-9a-f]{40}`.
  - **Fixture YAML âm viết inline**: workflow có `pull_request_target`; workflow live có `pull_request`; workflow có `uses: …@v4`. Test phải bắt được cả 3.
- **F4.8 `.github/CODEOWNERS`** (cần mentor duyệt): thêm `/evals/baselines/`, `/evals/cards/`, `/evals/data/golden/`, `/evals/tests/test_no_eval_leakage.py` với owner là Văn Dũng (handle lấy ở HC-5) và `@hieubui2409`. HC-5 bật "Require review from Code Owners" (RT-01).

Phi chức năng:
- Job PR ≤ 15 phút `[ASSUMED]`.
- Validate ở local trước khi lên remote, gồm một lượt chạy với `CI=true` (RT-09).
- Không có secret trong log.

## Related Code Files
**Create**
- `.github/workflows/ai2-live-benchmark.yml`
- `ai-service/tests/fixtures/p0-contract-baseline.json`
- `evals/tests/test_ci_workflows.py`

**Modify**
- `.github/workflows/ai-service.yml`, `.github/CODEOWNERS`
- `ai-service/README.md`, `docs/code-standards.md`
- Triage:
  - `ai-service/tests/unit/test_mistral_ocr.py`, `ai-service/tests/unit/test_kafka_idp_worker.py`, `ai-service/tests/unit/test_production_query.py`
  - `ai-service/tests/test_hd_gold.py`, `ai-service/tests/test_ingest.py`, `ai-service/tests/test_structure_reconstruction.py`, `ai-service/tests/test_p0_contract_baseline.py`
  - `ai-service/tests/unit/test_core.py`, `ai-service/tests/unit/test_kafka_contract_compat.py`
- Lint:
  - Sửa tay: `ai-service/app/reasoning/gold.py`, `ai-service/tests/test_p6_event_ui_convergence.py`
  - Re-export: `ai-service/app/tools/jobs.py`
- Ruff autofix I001/F401/E714: danh sách chính xác là output của ruff lúc cook, trừ file của P1–P3 (khoảng 60 file, PB-9).

**Delete**
- `evals/ci/production-evals.yml`

## File inventory

| File | Hành động | Cỡ | Tác động test |
|---|---|---|---|
| `.github/workflows/ai-service.yml` | M (viết lại) | ~110 dòng | `test_ci_workflows.py`, run thật |
| `.github/workflows/ai2-live-benchmark.yml` | C | ~75 dòng | `test_ci_workflows.py`, dispatch |
| `.github/CODEOWNERS` | M | +4 dòng | RT-01 (cần mentor) |
| `evals/tests/test_ci_workflows.py` | C | ~170 dòng (gồm fixture âm) | bất biến bảo mật |
| 9 file test triage + `p0-contract-baseline.json` | M/C | nhỏ | 18 mục PB-6 |
| `gold.py`, `test_p6_event_ui_convergence.py`, `jobs.py` | M | vài dòng | test liên quan |
| Ruff autofix | M | ~60 file, chỉ import | toàn suite |
| `ai-service/README.md`, `docs/code-standards.md` | M | ~1 trang | — |
| `evals/ci/production-evals.yml` | D | — | — |

## Implementation Steps
1. **Đo lại triage** trên SHA đã commit (sau P3): chạy `cd ai-service; .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -rfE -m "not live and not llm" --basetemp $env:TEMP\ai2pt` và lưu output ra file. So với bảng F4.4; ghi nhận T10 đã hết đỏ nhờ P3 hay chưa.
2. Chạy `cd ai-service; uv sync --frozen --extra dev --extra web --extra mistral --extra kafka`. Nếu lỗi thì **dừng và hỏi**, không tự sửa `uv.lock`.
3. **RED.** Viết `evals/tests/test_ci_workflows.py` kèm fixture âm; test phải fail vì workflow chưa có. Các test T3/T9/T10/T11 đang đỏ sẵn, đó là RED của chúng.
4. **Triage** theo F4.4. Chạy lại từng test ngay sau khi sửa.
5. **Lint** theo F4.5: làm `jobs.py` trước, rồi autofix (commit riêng), rồi sửa tay (commit riêng). Kết quả `ruff check . ../evals` phải là `All checks passed`.
6. **Workflow.** Lấy SHA bằng `git ls-remote https://github.com/actions/checkout refs/tags/v4` (và tương tự cho `setup-python`, `upload-artifact`; các tag này là lightweight nên SHA chính là commit, PB-13). Viết 2 file YAML, sửa CODEOWNERS, xoá template cũ.
7. **Chạy local** mọi lệnh `run:` của job PR (bản tương đương trên Windows). Chạy thêm `$env:CI="true"; $PY -m pytest -q -p no:cacheprovider evals/tests` (RT-09). Chạy gate trên một nhánh tạm có base ref cục bộ.
8. Viết tài liệu.
9. Chạy regression gate. Sau đó chạy `hs:code-review` trên toàn bộ diff của A, trọng tâm là workflow, secret, exit code và base ref, để có `review-decision.json`.
10. **HC-5 và nghiệm thu (theo VD-8):**
    - Admin tạo environment `ai2-live` với deployment branch `main` (required reviewer tuỳ chọn, VD-8).
    - Tạo một project OpenAI riêng có hard limit (VD-5); khoá của project này làm secret.
    - Bật Code Owners review; tạo label `ai2-baseline-update`; mentor duyệt `/.github/`.
    - Ghi URL run PR xanh. Khi workflow đã lên `main`: 1 dispatch thành công (`k=1 limit=3 max_usd=0.2`), và 1 dispatch từ nhánh khác **bị từ chối**. Nếu không bị từ chối thì báo ngay (RT-07).

## TDD

### Tests Before (RED)
- [ ] 18 mục PB-6 đang đỏ (OBSERVED).
- [ ] `test_workflow_triggers_parsed` (`on` → `True`) và các fixture âm (có `pull_request_target`, workflow live có `pull_request`, dùng tag `@v4`) đều phải bị bắt.
- [ ] `test_pr_workflow_has_no_secrets_and_read_only`.
- [ ] `test_pr_workflow_runs_gate_with_base_ref`: mỗi job có `uv sync` + `fetch-depth: 0`; có `--base-ref`; label chỉ đi qua `env:`.
- [ ] `test_live_workflow_is_isolated`: trigger = {dispatch} (có `schedule` là FAIL); có environment giới hạn `main`; có kiểm trần; có `--fail-on-threshold --tripwire-only`.
- [ ] `test_actions_pinned_by_sha`.
- [ ] `test_legacy_ci_template_removed`.

### Implement
Theo bước 4–8.

### Tests After
- [ ] T3, T9, T10, T11 xanh cả khi chạy riêng lẫn khi chạy cả suite.
- [ ] `test_p6_event_ui_convergence.py` xanh.

### Regression Gate
- `cd ai-service; .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm" --basetemp $env:TEMP\ai2pt` → **0 failed, 0 error**. Trên Linux: `cd ai-service && uv run pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm"`.
- `$PY -m pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm" evals/tests` và `... --import-mode=importlib evals/eval_types` → 0 failed. Chạy lại với `CI=true` cũng phải 0 failed.
- `$PY evals/scripts/run_ai2_gate.py --mode pr --base-ref HEAD` → exit 0.
- `cd ai-service; .venv/Scripts/ruff.exe check . ../evals` → 0 lỗi.
- `$PY -m evals.golden.build_golden --check` → exit 0.

## Test scenario matrix

| Mức | Kịch bản | Test / kiểm |
|---|---|---|
| Critical | Secret lộ hoặc PR từ fork chạm được secret | `test_pr_workflow_has_no_secrets_and_read_only`, `test_live_workflow_is_isolated` |
| Critical | Test bất biến xanh một cách rỗng (RT-10) | `test_workflow_triggers_parsed` + fixture âm |
| Critical | Baseline tự tham chiếu trên CI (RT-01) | `test_pr_workflow_runs_gate_with_base_ref`; CODEOWNERS |
| Critical | Tắt test âm thầm | bảng triage; marker được đếm; code-review |
| Critical | Dispatch từ ref tuỳ ý dùng secret (RT-07) | deployment branch `main` + trần OpenAI; kiểm ở bước 10 |
| High | Test đỏ riêng trên GitHub vì `CI=true` (RT-09) | bước 7 chạy với `CI=true` |
| High | Script injection; action bị thay qua tag | input qua `env:`; `test_actions_pinned_by_sha` |
| High | Autofix xoá re-export hoặc đổi ngữ nghĩa | `jobs.py` xử lý trước; F601/F841 sửa tay có test |
| Medium | T10 tái phát; thiếu extra; job chậm | P3 cô lập env; bước 2; cache uv |

## Success Criteria
- [ ] (test) Suite offline `ai-service`: trước 16 failed + 2 lỗi collection → sau **0 failed, 0 error**. Số passed/skipped ghi trong `verification-P4.json`. Skip mới chỉ gồm 5 test mang marker `requires_pdf_fixture` (cộng T1/T2 khi chạy local thiếu extra).
- [ ] (invariant) 18/18 mục PB-6 có quyết định trong bảng triage. T10 không dùng xfail.
- [ ] (test) `evals/tests/test_ci_workflows.py` xanh, bắt được cả 3 fixture âm.
- [ ] (test) `ruff check . ../evals` → 0 lỗi (trước là 82 + 30).
- [ ] (invariant) `evals/ci/production-evals.yml` đã bị xoá; `ai-service.yml` không còn placeholder.
- [ ] (test) Mọi lệnh `run:` của job PR chạy local đều exit 0, cả khi đặt `CI=true`.
- [ ] (manual — `manual_test_anchor.py`) Một run PR của `ai-service` xanh trên GitHub (URL). Mentor đã duyệt `/.github/` và CODEOWNERS.
- [ ] (manual — `manual_test_anchor.py`) HC-5 + VD-8: environment có deployment branch `main`; trần cứng OpenAI đã đặt; một dispatch từ `main` thành công và một dispatch từ nhánh khác bị từ chối (URL/ảnh chụp). Nếu chọn VD-8(a), mục này có thể hoàn tất sau khi A đóng.
- [ ] (test) `review-decision.json` có verdict `PASS`.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| R4-1: triage che lỗi thật | Trung × Cao | Mặc định là sửa; skip có marker và được đếm; T10 sửa ở gốc; code-review |
| R4-2: CI Linux khác Windows | Trung × Trung | Chạy local trước; run PR đầu tiên; LF đã chuẩn hoá |
| R4-3: cần mentor/admin (CODEOWNERS, environment, label) | Cao × Trung | Phần code xong độc lập; HC-5 được theo dõi; VD-8 cho phép nghiệm thu live sau |
| R4-4: PR sửa workflow để tự đặt `APPROVED=true` | Thấp × Cao | `/.github/` thuộc CODEOWNER (mentor); `test_ci_workflows.py` khoá cách đặt biến |
| R4-5: autofix đụng WIP | Thấp × Trung | Tiền đề commit WIP; commit riêng |
| R4-6: chi phí lượt live | Thấp × Thấp | Chỉ chạy tay (VD-5, VD-8); trần ở input, CLI và OpenAI (20 USD/tháng); concurrency 1; required reviewer tuỳ chọn |
