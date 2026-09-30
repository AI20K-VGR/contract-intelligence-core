---
phase: 2
title: "Scorer And Thresholds"
status: pending
plan: 260929-2323-ai2-a-measure-baseline
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 2 — Scorer And Thresholds

## Overview
Phase này thay hai eval dạng "bảng tra" (mirror) bằng bộ chấm tất định chạy pipeline thật (D-A12, VD-4):
- hỏi đáp: `FourLayerReasoner.run` (`ai-service/app/reasoning/stack.py:29`), task lấy từ `classify_ask` (`ai-service/app/reasoning/query.py:14`);
- xử lý: `run_idp` (`ai-service/app/pipeline/idp.py:40`).

Cách chấm:
- Chấm theo đơn vị. Mỗi chỉ số báo `x/n` kèm Wilson 95% và cluster-bootstrap theo hợp đồng (RT-13). Sàn là 60 đơn vị (D-A9). Ngưỡng theo D-A8.
- Gate chặn khi có hồi quy pass→fail so với baseline **của nhánh đích** (RT-01), và khi có **bất kỳ** đơn vị tripwire mới nào bị FAIL (RT-02).
- Citation chấm ở mức span bằng IoU trên tập dòng (VD-1, RT-08). Bbox chỉ dùng làm chẩn đoán.
- 15 task HD chỉ là bucket chẩn đoán `fixture_tuned_legacy`. Lint `test_no_eval_leakage` chặn luật rò mới (RT-04).

Phase này cũng:
- sửa mọi đường exit code (PB-1);
- thêm gate CLI một lệnh;
- đặt card v2 ở `evals/cards/proposed/`, để chạy `--draft --card-proposal` được **trước** HC-3 (RT-06).

Phụ thuộc P1. Commit chia 4 bước: **2a** thư viện dùng chung; **2b** `ai2_grounded_query`; **2c** `ai2_contract_package`; **2d** gate CLI, exit code, runbook.

## Dependency map
- **Upstream:** P1 (`evals/data/golden/**`, `evals/corpus/golden_manifest.json`, `.gitattributes`).
- **Production (chỉ đọc):**
  - `ai-service/app/pipeline/ai1_snapshot_adapter.py:334`
  - `ai-service/app/reasoning/stack.py:17-29`
  - `ai-service/app/reasoning/query.py:14`
  - `ai-service/app/pipeline/idp.py:40`
  - `ai-service/app/reasoning/vector_recall.py:169-186`
  - `ai-service/app/reasoning/relations.py` (`doc_side`)
  - `ai-service/app/reasoning/l0_rules.py` ~336-394: đối tượng của lint rò rỉ (PB-11)
  - `ai-service/fixtures/eval_suite.py:93`
  - `ai-service/fixtures/reasoning/hd_tong_hop_tasks.json`: bucket chẩn đoán
- **Hợp đồng tái dùng:** `evals/release_verification.py:60-111,297-362`.
- **Downstream:** P3 dùng `real_pipeline`, `unit_metrics`, `value_normalize`, `units`, `processing_units`. P4 gọi `run_ai2_gate.py --mode pr --base-ref origin/$BASE` và cần baseline đã commit trên nhánh đích.
- **Người:** HC-1 và HC-3 trước khi tạo baseline chính thức. Trước đó chỉ chạy `--draft --card-proposal`.

## Requirements
Chức năng:
- **F2.1 `evals/unit_metrics.py`** (stdlib):
  - `wilson_interval`; `zero_failure_upper_bound`.
  - `cluster_bootstrap_ci(records, cluster_key="contract_id", B=2000, seed=0)` (RT-13).
  - `MetricSpec`, `UnitRecord(metric, item_id, unit_id, passed, cluster, detail)`.
  - `evaluate_metric`: trả `PASS(point)` / `FAIL` / `UNDERPOWERED` / `NOT_RUN`, kèm `wilson_lower`, `cluster_lower`, `zero_failure_upper_bound`. `UNDERPOWERED` không bao giờ được tính là PASS.
  - `diff_regressions(baseline, current, specs)`:
    - chỉ số thường: item từ `true` → `false`;
    - **chỉ số tripwire** (`max_failures: 0` hoặc ngưỡng 1,0): mọi `(item_id, unit_id)` FAIL chưa có trong tập FAIL của baseline, kể cả item mới (RT-02);
    - lệch `golden_version` hoặc `scorer_version` → lỗi setup.
  - `build_report` có thêm `by_split`, `card_approved`, `tau_provisional`.
  - `render_markdown`; `exit_code`.
  - `load_baseline(path | git_ref)`, `write_baseline`. `write_baseline` từ chối khi có `CI`, `dirty`, `draft` hoặc card chưa duyệt.
- **F2.2 `evals/value_normalize.py`**: như bản trước (5 loại giá trị; loại trừ số điều, khoản, phụ lục và năm đứng một mình; quy tắc dấu phân tách; không trích số viết bằng chữ).
- **F2.3 `evals/real_pipeline.py`**:
  - luôn truyền `vector_recall=VectorRecallService(enabled=False)`;
  - không bao giờ import `app.api.main`;
  - có `adapt_snapshot`, `load_catalog_case`, `run_query`, `run_processing` và các hằng entry.
- **F2.4 `ai2_grounded_query/units.py`**:
  - Integrity: node tồn tại, `page_revision_id` khớp, `text_span` ⊂ text trang.
  - Tập dòng được cite: `line_ids`; không có thì map `char_start/char_end` sang dòng; vẫn không có thì `geometry_unresolved`, tính là sai.
  - `citation_correct`: qua integrity **và** IoU tập dòng ≥ τ với một `acceptable_span` cùng trang. Đơn vị IoU là `span_iou_unit` trong card (VD-1). `unit_id = <qid>#cit#<page>:<line_ids>`.
  - `citation_recall` theo `required_spans`.
  - `value_fabricated` mức 1/2, `unit_id = <qid>#val#<normalized>`.
  - `value_accuracy` (VD-3), `state_match`.
  - Chẩn đoán: `value_in_evidence`; `bbox_consistency` (bbox phát ra so với hợp bbox các dòng, khi `geometry_available`) (RT-08).
  - τ và đơn vị IoU đọc từ card. Thiếu → lỗi setup. Có `--card-proposal` thì ghi `tau_provisional`.
- **F2.5 `ai2_grounded_query/invariants.py`**: vị từ cho 14 cờ cũ, giữ nguyên bảng ở bản trước. Cờ lạ → exit 2. Case được thực thi ngoài `stack.py` thì giữ trạng thái FAIL, hoặc đưa vào `retired_cases` qua HC-3.
- **F2.6 Grounded `scorer.py` / `runner.py`**:
  - `SCORER_VERSION = "2.0.0"`, card nạp lười.
  - Runner đọc golden (`--golden-dir` để trỏ sang tập biến thể; kiểm `approval` trừ khi `--draft`) và 20 invariant cũ.
  - 15 task HD chạy thành **bucket `fixture_tuned_legacy`**: chỉ chẩn đoán, không vào mẫu số, report ghi rõ "rò rỉ tập test, PB-11".
  - Report tách theo split. Che MST theo card.
  - Cờ: `--draft --card-proposal <path> --baseline --base-ref --update-baseline --enforce-thresholds --report-json --evals-root`. Không còn lane mirror.
- **F2.7 Contract `processing_units.py` / `scorer.py` / `runner.py`** (VD-4a):
  - `processing_state_match` trên các case GOLDEN.
  - `fact_value_fabricated` gồm mức 1, mức 2 và `normalization_invented`, `unit_id = <case_id>#fact#<fact_id>`. Phạm vi theo **VD-9**: mặc định (a) là fact của cả 95 case eval, vì kiểm này không cần nhãn.
  - `--candidates` chỉ là chẩn đoán state trên nhãn `UNVERIFIED`, không vào mẫu số của `processing_state_match`.
- **F2.8 Card v2 đề xuất** ở `evals/cards/proposed/ai2_grounded_query.v2.json` và `evals/cards/proposed/ai2_contract_package.v2.json` (RT-06):
  - Thêm `metrics{}`, `unit_floor: 60`, `span_iou_threshold`, `span_iou_unit`, `value_location`, `enforce_thresholds_in_pr`, `scorer_version`, `production_entry`, `masks`, `retired_cases`, `limitations`.
  - Giữ `p0_rules` và `case_matrix`.
  - Bỏ các trường mirror, `dimensions`, `threshold`.
  - Chỉ có `approve_card.py` được chuyển bản đề xuất sang `evals/cards/`.
- **F2.9 `config_integrity.py` (cả 2 domain)**: băm byte sau khi đổi CRLF→LF.
- **F2.10 `evals/scripts/approve_card.py`** (người chạy):
  - `--proposal <path> --approved-by <tên>`, có xác nhận tương tác;
  - ghi `approved_by`/`approved_ts`, **chuyển** file sang `evals/cards/<domain>.json` và xoá bản đề xuất;
  - sidecar = sha256 trên LF;
  - in tóm tắt thay đổi ngưỡng;
  - có `CI` → 2.
  - Ghi chú trung thực: guard `CI` không phải kiểm soát bảo mật. Bằng chứng duyệt là commit của Văn Dũng cộng review của CODEOWNER (P4).
- **F2.11 `run_release_verification.py`**: như bản trước (bỏ import không tồn tại, đọc card từ `evals/cards/`, bỏ domain contract khỏi mutation, thêm `--out`). Exit: PASS → 0, UNVERIFIED → 3, còn lại → 1, lỗi setup → 2.
- **F2.12 `evals/scripts/run_ai2_gate.py`**:
  - `--mode pr|full`, `--domain`, `--base-ref <ref>`.
  - Có `--base-ref` thì baseline, card và golden manifest đều đọc bằng `git show <ref>:<path>` (RT-01).
  - Tính diff `<ref>...HEAD`. Nếu diff chạm `evals/baselines/**`, `evals/cards/*.json`, `evals/cards/*.sha256` hoặc `evals/data/golden/manifest.json` → in diff và exit 1, trừ khi `AI2_BASELINE_CHANGE_APPROVED=true`. Workflow chỉ đặt biến này khi PR có label `ai2-baseline-update`; phần review CODEOWNER nằm ở HC-5.
  - Chạy đủ 3 bước (`build_golden --check`, grounded, processing), không dừng sớm âm thầm.
  - Ghi `evals/results/gate/<utc>/summary.{json,md}`. Exit bằng mức nặng nhất trong các bước.
  - Không có `--base-ref` (dùng khi chạy local) thì đọc từ cây làm việc và in cảnh báo.
  - `--draft --card-proposal-dir evals/cards/proposed` chuyển bản card đề xuất xuống CLI của từng domain. Ở chế độ này gate không bao giờ ghi baseline, và `summary.json` ghi `draft: true`.
- **F2.13 Runbook**: một lệnh cho mỗi mục đích; bảng exit code; mẫu PowerShell `if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }`; quy trình HC-3 và quy trình làm mới baseline (PR riêng, có label, có CODEOWNER); mô tả `--draft --card-proposal`.
- **F2.14** `.gitignore`: thêm `evals/results/`.
- **F2.15 `evals/tests/test_no_eval_leakage.py`** (RT-04):
  - Quét `ai-service/app/**/*.py` tìm: (a) chuỗi câu hỏi golden và câu hỏi task HD (đã chuẩn hoá, ≥ 12 ký tự); (b) node id của fixture catalog/HD (`field_usd`, `field_penalty_build`, `field_penalty_equip`, `cl_9`, …).
  - `ALLOWLIST` đóng băng liệt kê đúng các literal hiện có, kèm `file:line`. Lint đỏ khi allowlist tăng hoặc có literal mới. Allowlist chỉ được **giảm**, và đó là việc bàn giao cho C (VD-6).

Phi chức năng:
- Offline kín: không gọi mạng, không phụ thuộc biến môi trường.
- Tất định.
- Gate PR ≤ 5 phút `[ASSUMED]`.

## Related Code Files
**Create**
- 2a:
  - `evals/unit_metrics.py`, `evals/value_normalize.py`, `evals/real_pipeline.py`, `evals/scripts/approve_card.py`
  - `evals/tests/test_unit_metrics.py`, `evals/tests/test_value_normalize.py`, `evals/tests/test_real_pipeline.py`, `evals/tests/test_approve_card.py`, `evals/tests/test_no_eval_leakage.py`
- 2b:
  - `evals/eval_types/ai2_grounded_query/units.py`, `evals/eval_types/ai2_grounded_query/invariants.py`
  - `evals/eval_types/ai2_grounded_query/tests/test_units.py`, `evals/eval_types/ai2_grounded_query/tests/test_invariants.py`
  - `evals/cards/proposed/ai2_grounded_query.v2.json`
  - `evals/baselines/ai2_grounded_query.offline.json` (sau HC-1/HC-3)
- 2c:
  - `evals/eval_types/ai2_contract_package/processing_units.py`, `evals/eval_types/ai2_contract_package/tests/test_processing_units.py`
  - `evals/cards/proposed/ai2_contract_package.v2.json`
  - `evals/cards/ai2_contract_package.sha256` (do `approve_card.py` sinh)
  - `evals/baselines/ai2_contract_package.offline.json`
- 2d: `evals/scripts/run_ai2_gate.py`, `evals/tests/test_gate_exit_codes.py`

**Modify**
- 2a:
  - `evals/eval_types/ai2_grounded_query/config_integrity.py`
  - `evals/eval_types/ai2_contract_package/config_integrity.py`
  - `.gitignore`
- 2b:
  - `evals/eval_types/ai2_grounded_query/`: `scorer.py`, `runner.py`, `judge_runner.py` (`:150`), `judge_prompt.py` (`:99`)
  - `evals/eval_types/ai2_grounded_query/tests/`: `test_scorer.py`, `test_config_conformance.py`, `test_mirror_parity.py`
  - `evals/cards/ai2_grounded_query.json`, `evals/cards/ai2_grounded_query.sha256` (chỉ sửa qua `approve_card.py`, HC-3)
  - `evals/scripts/run_grounded_query_evals.py`
- 2c:
  - `evals/eval_types/ai2_contract_package/`: `scorer.py`, `runner.py`
  - `evals/eval_types/ai2_contract_package/tests/`: `test_scorer.py`, `test_config_conformance.py`, `test_mirror_parity.py`
  - `evals/cards/ai2_contract_package.json` (qua `approve_card.py`)
  - `evals/scripts/run_production_evals.py`, `evals/scripts/run_release_verification.py`
  - `evals/mutation_mapping.json`, `evals/tests/test_p4_release_verification.py` (`:24`)
- 2d: `evals/docs/production-eval-setup.md`

**Delete**
- 2b: `evals/eval_types/ai2_grounded_query/pipeline_mirror.py`
- 2c:
  - `evals/eval_types/ai2_contract_package/pipeline_mirror.py`
  - `evals/eval_types/ai2_contract_package/tests/production_fixtures/ground_truth.json`
  - `evals/data/samples/ai2_contract_package/` (10 JSON + README)
  - `evals/eval_config.json`, `evals/eval_config.sha256`

**Giữ nguyên, có chủ đích:**
- ground truth và samples của grounded query (20 invariant);
- `evals/release_verification.py`, `evals/mutation_fixtures.py`, `evals/workflow_gate.py`.

## File inventory

| Nhóm | File | Hành động | Cỡ | Tác động test |
|---|---|---|---|---|
| 2a | `unit_metrics.py` | C | ~320 dòng (thêm cluster CI, hồi quy tripwire) | mọi verdict |
| 2a | `value_normalize.py`, `real_pipeline.py`, `approve_card.py` | C | ~200 / ~150 / ~130 dòng | các chỉ số, offline kín, HC-3 |
| 2a | `test_no_eval_leakage.py` | C | ~120 dòng | chặn rò rỉ (RT-04) |
| 2a | 2 × `config_integrity.py` | M | +3 dòng | CRLF |
| 2b | `units.py`, `invariants.py` | C | ~320 + ~250 dòng | chỉ số query, P0 |
| 2b | `scorer.py`, `runner.py` | M (viết lại) | −450 / +340 dòng | conformance, CLI |
| 2b | `judge_runner.py`, `judge_prompt.py` | M | 1–2 dòng | 0 hit mirror |
| 2b/2c | 2 card đề xuất + 2 card thật + sha | C/M | card v2 | HC-3 |
| 2c | `processing_units.py`, contract `scorer.py`, contract `runner.py` | C/M | ~170 dòng + viết lại | chỉ số xử lý |
| 2c | 16 file xoá | D | — | `git grep` |
| 2c | `run_release_verification.py`, `mutation_mapping.json`, `test_p4_release_verification.py` | M | nhỏ | exit 3 |
| 2d | `run_ai2_gate.py`, `test_gate_exit_codes.py`, runbook | C/M | ~230 + ~260 dòng | exit code, base ref |

## Implementation Steps
1. **2a RED.** Viết các test 2a, gồm test hồi quy tripwire, cluster CI và lint rò rỉ. Xác nhận fail.
2. **2a GREEN.** Làm các module 2a. Sửa `config_integrity.py` và `.gitignore`. Đóng băng `ALLOWLIST` của `test_no_eval_leakage` bằng cách quét HEAD hiện tại, đối chiếu PB-11, ghi `file:line`. Commit.
3. **2b RED.** Viết `test_units.py` (gồm test đối nghịch) và `test_invariants.py`, viết lại các test grounded. Test dùng card/golden mini ở thư mục tạm.
4. **2b GREEN.**
   - Làm `units.py`, `invariants.py`; viết lại `scorer.py`/`runner.py`; xoá mirror; sửa 2 file judge.
   - Viết `evals/cards/proposed/ai2_grounded_query.v2.json`, **không** đụng `evals/cards/ai2_grounded_query.json` hay sidecar.
   - Chạy `$PY evals/scripts/run_grounded_query_evals.py --draft --card-proposal evals/cards/proposed/ai2_grounded_query.v2.json --report-json evals/results/p2/grounded.json`. Lệnh phải exit 0 dù card chưa duyệt. Ghi số draft và histogram IoU vào `verification-P2.json`.
5. **2c RED.** Viết `test_processing_units.py` và viết lại các test contract.
6. **2c GREEN.** Làm `processing_units.py`, viết lại contract scorer/runner, xoá các file theo danh sách, viết card contract đề xuất, sửa `run_production_evals.py`, `run_release_verification.py`, `mutation_mapping.json`, `test_p4_release_verification.py:24`. Chạy draft với `--card-proposal`.
7. **2d RED → GREEN.** Viết `test_gate_exit_codes.py`. Các test chạy subprocess trên một **repo git tạm**: commit base có baseline, commit PR sửa code và/hoặc baseline. Sau đó làm `run_ai2_gate.py` và viết lại runbook.
8. **Bàn giao HC-3.** Văn Dũng chạy `approve_card.py --proposal …` cho từng domain trong commit của chính mình. Agent không chạy lệnh này.
9. **Baseline** (sau HC-1 + HC-3, trên cây sạch). Chạy `--update-baseline` cho 2 domain. Commit trong **PR riêng** có label `ai2-baseline-update` và được CODEOWNER duyệt.
10. Lint các file `.py` của P2 theo `plan-graph.yaml`. Chạy regression gate. Commit theo 2a–2d.

## TDD

### Tests Before (RED)
Test happy-path gọi `monkeypatch.delenv("CI", raising=False)`; test từ chối gọi `setenv("CI", "true")` (RT-09).

- [ ] `test_wilson_known_values`: 60/60 → [0,940; 1,000]; 57/60 → [0,863; 0,983]; 21/24 → [0,690; 0,957]. Bộ số 21/24 chỉ dùng làm vector test, **không** phải mốc.
- [ ] `test_cluster_bootstrap_wider_than_wilson_when_clustered`: 8 cụm, lỗi dồn vào 1 cụm → cận dưới cluster < cận dưới Wilson; cùng seed → cùng kết quả.
- [ ] `test_floor_is_never_pass`, `test_blocking_zero_failure`.
- [ ] `test_threshold_boundary_reports_lower_bounds`: 57/60 → `PASS(point)` với `wilson_lower` ≈ 0,863.
- [ ] `test_regression_detection`: item thường đổi true → false → hồi quy; lệch version → lỗi setup.
- [ ] `test_tripwire_new_item_fail_is_regression` (RT-02): baseline không có item Q; bản mới Q phát ra một giá trị bịa → hồi quy. Item đã FAIL mà có thêm đơn vị FAIL mới → cũng hồi quy.
- [ ] `test_exit_code_matrix`; `test_write_baseline_refuses_in_ci_dirty_draft_unapproved`.
- [ ] `test_value_formats`.
- [ ] `test_offline_is_hermetic`: có env `AI2_VECTOR_RECALL_ENABLED=true` và khoá giả → spy **đếm** lời gọi `complete_json`/embedding phải bằng 0 (không dùng sentinel raise, vì `runtime.py:101` nuốt `Exception`); output giống hệt khi không có env.
- [ ] `test_offline_is_deterministic`, `test_production_entry_and_no_mirror`, `test_config_integrity_crlf`.
- [ ] `test_approve_card_moves_proposal`: thiếu `--approved-by` → 2; có `CI` → 2; thành công thì proposal bị xoá, card thật có `approved_by`, sidecar = sha LF.
- [ ] `test_no_eval_leakage`: HEAD hiện tại xanh với allowlist. Thêm một literal `"cl_9"` giả vào một file tạm nằm trong phạm vi quét → đỏ.
- [ ] `test_units_geometry`: cùng tập dòng → IoU 1,0; khác trang → 0; map từ ký tự sang dòng; không resolve được → sai.
- [ ] `test_units_adversarial`:
  - **cite đúng điều khoản nhưng sai dòng**, trong điều khoản ≥ 5 dòng → FAIL (RT-08);
  - cite heading điều khoản → FAIL;
  - bỏ citation → recall giảm, `citation_correct` n = 0, không PASS;
  - đổi một chữ số → bị bắt là bịa;
  - câu không trả lời được mà có citation → sai.
- [ ] `test_units_tau_from_card` và `test_card_proposal_marks_tau_provisional`.
- [ ] `test_invariant_predicates`, `test_legacy_runs_real_stack`.
- [ ] `test_hd_tasks_are_diagnostic_only`: bucket `fixture_tuned_legacy` có trong report nhưng không nằm trong mẫu số của bất kỳ chỉ số có gate nào.
- [ ] `test_report_by_split`.
- [ ] `test_card_v2_shape` (chạy trên bản đề xuất): ngưỡng theo D-A8; `unit_floor` 60; τ ∈ (0, 1]; `span_iou_unit` là `line_set` hoặc `bbox`; 8 `p0_rules`.
- [ ] `test_processing_units`: fact bịa được bắt; phạm vi fact theo VD-9; candidate không vào mẫu số `processing_state_match`.
- [ ] `test_gate_exit_codes`, trên repo git tạm:
  - drift → 2;
  - hồi quy → 1;
  - tripwire có item mới FAIL → 1;
  - **PR vừa hồi quy vừa `--update-baseline` → 1**, vì baseline đọc từ base ref (RT-01);
  - PR chạm path đã khoá khi chưa được duyệt → 1; có `AI2_BASELINE_CHANGE_APPROVED=true` mà không hồi quy → 0;
  - sạch → 0;
  - `UNVERIFIED` → 3;
  - cờ lạ → 2;
  - golden chưa duyệt mà không có `--draft` → 2.

### Implement
Theo các bước 2, 4, 6, 7.

### Tests After
- [ ] Report draft đủ 5 chỉ số query và 2 chỉ số xử lý. Mỗi chỉ số có `x/n` + Wilson + cluster CI + trạng thái, tách theo split, kèm bucket HD.
- [ ] `evals/tests/test_p4_release_verification.py` 6/6.

### Regression Gate
- `$PY -m pytest -q -p no:cacheprovider evals/tests` và `... --import-mode=importlib evals/eval_types` → 0 failed.
- Trước HC: `$PY evals/scripts/run_ai2_gate.py --mode pr --draft --card-proposal-dir evals/cards/proposed` → exit 0, report ghi `draft: true`, `card_approved: false`.
- Sau HC và baseline: `$PY evals/scripts/run_ai2_gate.py --mode pr --base-ref HEAD` → exit 0.
- `cd ai-service; .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m "not live" tests/test_reasoning.py tests/test_eval_contract.py tests/test_catalog.py` → xanh.
- Lint: `cd ai-service; .venv/Scripts/ruff.exe check <các file .py của P2 trong plan-graph.yaml, tiền tố ../>` → 0 lỗi. File không thuộc P2 do P4 autofix.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Baseline tự tham chiếu nuốt hồi quy (RT-01) | `test_gate_exit_codes` (PR tự cập nhật baseline → 1) |
| Critical | Tripwire bỏ lọt item mới (RT-02) | `test_tripwire_new_item_fail_is_regression` |
| Critical | PASS giả do khớp lỏng (RT-08) | `test_units_adversarial` (sai dòng / heading → FAIL) |
| Critical | Rò rỉ tập test (RT-04) | `test_no_eval_leakage`, `test_hd_tasks_are_diagnostic_only` |
| Critical | Deadlock dẫn tới tự duyệt (RT-06) | `test_card_proposal_marks_tau_provisional`, gate draft exit 0 trước HC |
| Critical | Offline gọi mạng | `test_offline_is_hermetic` (dùng spy) |
| Critical | Exit 0 khi có lỗi | `test_gate_exit_codes`, `test_exit_code_matrix` |
| High | CI hẹp giả do đơn vị bị cụm (RT-13) | `test_cluster_bootstrap_wider_than_wilson_when_clustered` |
| High | Test đỏ riêng trên GitHub vì `CI=true` (RT-09) | quy ước monkeypatch; P4 chạy lại với `CI=true` |
| High | Chuẩn hoá giá trị sai; cờ cũ bị bỏ âm thầm | `test_value_formats`, `test_invariant_predicates` |
| Medium | Không tất định; lộ MST; mutation vỡ | các test tương ứng |

## Success Criteria
- [ ] (invariant) `git ls-files "*pipeline_mirror*"` rỗng. `git grep -n pipeline_mirror -- evals ai-service` và `git grep -n "eval_config.json" -- evals` đều 0 hit.
- [ ] (test) `evals/tests` + `evals/eval_types` → 0 failed, 0 lỗi collection.
- [ ] (test) Report grounded (draft hoặc chính thức): `state_match` n ≥ 84 (chỉ golden), `citation_recall` n ≥ 60, `value_accuracy` n ≥ 60. `citation_correct` và `value_fabricated` báo n thật (`UNDERPOWERED` nếu dưới sàn). Bucket HD có nhãn "rò rỉ, không gate".
- [ ] (test) Report processing: `fact_value_fabricated` n ≥ 60 (VD-9a: khoảng 11.280); `processing_state_match` n bằng số case GOLDEN.
- [ ] (test) `test_gate_exit_codes.py` xanh với cả 9 kịch bản.
- [ ] (invariant) `test_no_eval_leakage.py` xanh. Allowlist liệt kê literal của `l0_rules.py` kèm `file:line` (bàn giao C).
- [ ] (manual — `manual_test_anchor.py`) HC-3: hai card nằm ở `evals/cards/` với `approved_by: "Văn Dũng"`, sidecar khớp, `evals/cards/proposed/` rỗng. SHA commit của Văn Dũng ghi trong verification.
- [ ] (manual — `manual_test_anchor.py`) Hai file baseline `*.offline.json` đã vào nhánh đích qua PR có label và được CODEOWNER duyệt, `dirty: false`.
- [ ] (test) `run_ai2_gate.py --mode pr --base-ref HEAD` → exit 0.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| R2-1: offline phụ thuộc env | Trung × Cao | `VectorRecallService(enabled=False)`; test spy |
| R2-2: phase lớn (~55 file) | Cao × Trung | 4 commit, mỗi commit có gate riêng |
| R2-3: vị từ invariant lỏng/chặt | Trung × Trung | Cặp PASS/FAIL cho mỗi vị từ; HC-3 duyệt tham số |
| R2-4: n phía phát ra < 60 | Trung × Trung | Báo `UNDERPOWERED`; P1 có dư câu hỏi |
| R2-5: HC chậm | Trung × Trung | `--draft --card-proposal` không bị chặn |
| R2-6: allowlist rò rỉ bị nới để lint xanh | Thấp × Cao | Test khoá kích thước allowlist (chỉ giảm); file này cũng nằm dưới CODEOWNER nếu mentor đồng ý mở rộng HC-5 |
| R2-7: `git show origin/<base>` thiếu ref trên CI | Trung × Trung | P4 checkout với `fetch-depth: 0`; thiếu ref → exit 2, không dùng cây PR thay thế |
