---
phase: 5
title: "Bakeoff Rerun"
status: pending
plan: 261008-1500-ai2-contract-graph-implicit
created: 2026-10-08
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 5 — Bake-off Rerun + cổng quyết định

## Overview

Nhập và **khoá** quyết định duyệt HG-1 trước trial 1 (RT-15), kiểm vũ trụ gold phủ mọi ứng viên (RT-02), rồi chạy `hs:bakeoff` trên held-out: C (đường tích hợp đầy đủ), B (`SAME_ARTICLE`+`EXPLICIT_REF`), E (mọi cặp pool + S4 — chỉ khi khả thi, RT-12) × ≥2 trial, cùng một classifier model hợp lệ (`served_model thuộc họ classifier được nhận diện — RT-04), cùng `PROMPT_VERSION`. Báo precision **bảo thủ** (quyết định cổng) + quan sát + ước lượng 1/π (RT-01), recall, McNemar trên cùng item, false `DUPLICATE`, khoảng theo cụm, hiệu chuẩn người gán nhãn (cận trên), chi phí/độ trễ. Cổng dùng đúng ngưỡng `review_policy` + false DUPLICATE = 0 ⇒ khuyến nghị (`ENABLE_CANDIDATE` / `KEEP_OFF_*` / `HUMAN_DECISION`). Không tự bật cờ; `KEEP_OFF_INSUFFICIENT_N` là kết quả được chấp nhận (Q6). Dedicated classifier endpoint/model chưa có ⇒ BLOCKED (Q3).

## Dependency map

- Phụ thuộc P4: đường tích hợp `build_pair_relations` (loại cặp luồng 1 + `PAIRS_TOP_K`), doc AI2-20 (§Số đo).
- Phụ thuộc P3: `pairs/predictor.py` (C/B/E, kiểm họ `served_model`), `PROMPT_VERSION`.
- Phụ thuộc P2: S4 + `review_selection` (sha khoá), `CANDIDATES_VERSION`, `PAIRS_TOP_K`.
- Phụ thuộc P1: `manifest.verify`, `review.import_sheet`/`labeler_confusion`, `score` (bảo thủ + 1/π), `models.family`.
- Cổng người **HG-1**: `.harness/state/contract-graph-pairs/review/heldout_review.csv` đã điền đủ.
- Tái dùng (chỉ gọi, không sửa): `review_policy.MIN_N`, `MIN_WILSON_LOWER`, `wilson_lower` (`ai-service/app/pipeline/contract_graph/review_policy.py:21-44`); `harness/plugins/hs/skills/bakeoff/scripts/bakeoff_rank.py` (`preflight` — mặc định `budget_tokens ≤ 2_000_000`, `budget_seconds ≤ 600` theo red-team OBSERVED; `record`; `rank --plan-dir`); `harness/scripts/wilson.py` (`--clusters`, `--mcnemar`, `--diff`, `--judge-screen`, `--min-n`); quy tắc `harness/rules/sampled-rate-reporting.md`; hợp đồng CLI/trường báo cáo probe run1 (`.harness/state/bakeoff/contract-edge-261007/probe.py:6-7, 152-207`) — không import.

## Requirements

### Chức năng

1. **Bước 0 — tiền điều kiện (thoát mã 2 nếu trượt bất kỳ)**:
   - `run.py verify` sạch (held-out pool, nhãn, S4 không đổi sha).
   - `run.py review-import --csv …` ⇒ `data_dir/review/heldout_review.decisions.jsonl`; mọi dòng được chọn có quyết định; `selection_sha256` của file chọn == `manifest.review_selection.sha256` (P2).
   - **Khoá quyết định** (RT-15): commit `manifest.json` với `heldout_review: {decisions_sha256, n_selected, n_approve, n_relabel, n_reject}` **trước** trial 1 (`git log` chứng minh thứ tự trong `verification-P5.json`).
   - **Vũ trụ gold** (RT-02): sinh lại ứng viên C và B trên held-out bằng code hiện tại ⇒ `candidates ⊆ pool ∪ S4`; `CANDIDATES_VERSION`, `PAIRS_TOP_K` == manifest `extension_s4`; lệch ⇒ mã 2 (code đã trôi sau khi khoá gold).
   - Classifier khả dụng qua đường production (classifier_client(NineRouterClient(), model)); classifier_family_ok(served_model) đúng, labeler thuộc họ openai và tên model cụ thể khác labeler; unknown hoặc trùng ⇒ mã 2.
   - `PROMPT_VERSION` == bản chốt ở `l2-p3-classifier-dev.json`.
   - **Khả thi** (RT-12): từ tỷ lệ dự đoán/nhãn của `l2-p3` × số ứng viên C held-out ⇒ `expected_n_L`; nếu mọi nhãn có `expected_n_L` < `MIN_N / 2` ⇒ ghi `feasibility: "KEEP_OFF_INSUFFICIENT_N expected"` và **bỏ biến thể E** (bake-off C vs B, vẫn ≥2 ứng viên); ngược lại giữ E với trần `E_MAX_PAIRS_PER_DOC = 300`.
   - `bakeoff_rank.py preflight` (ứng viên đã chọn, metric dry-run in một số, `--budget-tokens`/`--budget-seconds` rõ ràng từ token/hồ sơ của `l2-p3` × số văn bản × 1,5; nếu vượt trần mặc định của preflight ⇒ ghi lý do + giảm phạm vi E, không bỏ qua preflight).
2. **Runner** — `evals/contract_graph/pairs/bakeoff.py`:
   - `run(variant, trial, *, out_dir, model)`: mỗi văn bản held-out (sau `verify`) gọi `predictor.predict_doc(..., variant)`; ghi `out_dir/t<trial>/<variant>.json`: dự đoán (`pair_id`, nhãn, hướng), metric, chi phí, `decisions_sha256`, `served_model`.
   - Vũ trụ chấm = `pool ∪ S4` (đơn vị `pair_id` không thứ tự). Gold = duyệt `approved=true`.
   - Metric mỗi (biến thể, trial) qua `score.score_relations(..., selection=…)`: theo nhãn `precision_conservative` (dự đoán không có gold duyệt = sai — **dùng cho cổng**), `precision_observed`, `precision_weighted`/`recall_weighted` (Horvitz–Thompson 1/π, chỉ báo), `recall_observed`, `direction_accuracy`; `recall_any` (gold positive duyệt dự đoán đúng nhãn / tổng gold positive duyệt — metric bake-off, `direction=higher`); `false_duplicate`; theo tầng S1–S4 và theo văn bản; `llm_calls`, `prompt_tokens`, `completion_tokens`, `elapsed_s`, p50/p95/hồ sơ; `rejected`, `injection_signals`; `n_docs`.
   - `metric(variant, out_dir, field)` in **một số** (mặc định `recall_any` trial mới nhất).
3. **Chạy bake-off** (`hs:bakeoff`, noise `medium`):
   - Mỗi biến thể × trial 1..2 (xen kẽ C1, B1, [E1], C2, B2, [E2]): `run.py bakeoff run <V> --trial <i> --out <dir> --allow-heldout`; `bakeoff_rank.py record --run contract-pairs-<YYMMDD> --candidate <V> --trial <i> --value <recall_any> --elapsed-s … --tokens …`.
   - `bakeoff_rank.py rank --run contract-pairs-<YYMMDD> --direction higher --noise medium --rel-band 0.05 --plan-dir plans/261008-1500-ai2-contract-graph-implicit` ⇒ `bakeoff-verdict.json`.
   - McNemar trên cùng item (gold positive duyệt), worse-of trial: `wilson.py --mcnemar --b <b> --c <c> --json` cho C vs B (và C vs E nếu có); khoảng chứa 0,5 ⇒ hoà. Precision giữa biến thể: `--diff`. Không dùng "khoảng chồng nhau".
   - Mỗi tỷ lệ chính: `wilson.py --k --n --clusters <số văn bản> --json`.
   - Hiệu chuẩn người gán nhãn: `labeler_confusion` ⇒ `wilson.py --judge-screen …` mỗi nhãn; báo cáo ghi rõ đây là **cận trên** đồng thuận (người duyệt thấy nhãn GPT; không có người gán mù).
4. **Cổng** — `bakeoff.decide(report) -> dict` (thuần):
   - Kiểm `report.decisions_sha256` == `manifest.heldout_review.decisions_sha256` cho **mọi** file trial; lệch ⇒ từ chối (RT-15).
   - Mỗi nhãn L trên C, **trial tệ hơn**: `n_L` = mọi dự đoán L trong vũ trụ chấm, `k_L` = đúng theo gold duyệt (bảo thủ, RT-01). Đạt ⇔ `n_L ≥ MIN_N` ∧ `wilson_lower(k_L, n_L) ≥ MIN_WILSON_LOWER`.
   - Veto `false_duplicate > 0` ở bất kỳ trial C ⇒ `KEEP_OFF_FALSE_DUPLICATE`.
   - Verdict theo thứ tự: `KEEP_OFF_FALSE_DUPLICATE` → `KEEP_OFF_INSUFFICIENT_N` → `KEEP_OFF_BELOW_THRESHOLD` → `HUMAN_DECISION` (mọi nhãn đạt nhưng: cận dưới theo cụm < 0,85, hoặc McNemar cho thấy B tốt hơn C có ý nghĩa; **hoặc** nhãn không đạt bảo thủ nhưng đạt theo ước lượng 1/π — chỉ để người xem) → `ENABLE_CANDIDATE`.
   - Ghi `per_label` (k, n, rate, Wilson lower/upper, cụm lower, quan sát, 1/π, đạt?), `min_n_needed` (`wilson.py --min-n` với tỷ lệ quan sát), ước số văn bản cần thêm, `thresholds_source: "review_policy.py"`, `thresholds` đọc từ import, `feasibility`, `variants_run`.
   - Chỉ là **khuyến nghị**: không sửa env, không sửa `calibration.json` luồng 1, runtime không đọc.
5. **Báo cáo** — `evals/contract_graph/reports/l2-p5-bakeoff.{json,md}` (scoreboard cả biến thể thua, spread, `over_budget`, McNemar, cụm, hiệu chuẩn cận trên, chi phí, số vòng tune dev đã thấy: lexicon P2 + prompt P3, số lần held-out chạy = số trial, biến thể bị bỏ + lý do) và `l2-p5-decision.json`. Không văn bản/span. So run1 (C 10/11, B 8/11, E precision 11/32) chỉ định hướng, ghi rõ run1 có thể dùng GPT và khác dữ liệu.
6. **Doc** — điền §Số đo AI2-20 (k/n + khoảng + verdict; "đo trên mẫu HĐ công khai").

### Phi chức năng

- Held-out chạy đúng số trial khai báo (2; trial 3 chỉ khi `bakeoff_rank` trả `insufficient_trials`, ghi lý do). Không chỉnh prompt/lexicon/K giữa trial.
- Test mock LLM; live chỉ qua `--allow-heldout`.
- Mọi tỷ lệ `k/n` + khoảng + method `wilson`.

## Files — file inventory

| Hành động | Path | Cỡ ước tính | Ảnh hưởng test |
|---|---|---|---|
| Create | `evals/contract_graph/pairs/bakeoff.py` | ~250 dòng | `test_cg_pairs_bakeoff.py` |
| Create | `evals/contract_graph/tests/test_cg_pairs_bakeoff.py` | ~17 test | mới |
| Modify | `evals/contract_graph/pairs/run.py` | +`review-import`, `bakeoff run|metric|decide|preflight-checks` | `test_cg_pairs_bakeoff.py` |
| Modify | `evals/contract_graph/pairs/manifest.json` | khối `heldout_review` (không văn bản) | `test_committed_manifest_has_no_text` |
| Create | `evals/contract_graph/reports/l2-p5-bakeoff.{json,md}` | nhỏ | — |
| Create | `evals/contract_graph/reports/l2-p5-decision.json` | nhỏ | `test_committed_decision_matches_report` |
| Create | `plans/261008-1500-ai2-contract-graph-implicit/bakeoff-verdict.json` | sinh bởi `bakeoff_rank.py rank` | — |
| Modify | `docs/ai2/AI2-20-contract-graph-pairs.vi.md` | §Số đo | — |
| Ngoài repo | `.harness/state/contract-graph-pairs/{review/heldout_review.decisions.jsonl,bakeoff/t<i>/<V>.json}` | dữ liệu | — |

## Implementation Steps

1. Viết test RED → FAIL.
2. Implement `bakeoff.py` (`preconditions`, `run`, `metric`, `decide`) + subcommand.
3. Bước 0 đầy đủ; **commit khoá quyết định** (manifest `heldout_review`) trước bước 4.
4. Chạy biến thể × trial (xen kẽ); `record` từng trial.
5. `rank` → `bakeoff-verdict.json`; `wilson.py` (McNemar, `--diff`, `--clusters`, `--judge-screen`, `--min-n`); `decide` → `l2-p5-decision.json`.
6. Báo cáo `l2-p5-bakeoff.{json,md}`; §Số đo AI2-20.
7. Regression gate; `hs:code-review` toàn nhánh ⇒ `review-decision.json`; commit. Báo verdict + scoreboard đầy đủ; không đổi cờ.

## TDD

### Tests Before (RED)

`evals/contract_graph/tests/test_cg_pairs_bakeoff.py` (client giả, held-out giả 3 văn bản trong `tmp_path`)
- [ ] `test_precondition_verify_failure_exits_2`.
- [ ] `test_precondition_review_incomplete_exits_2`.
- [ ] `test_precondition_selection_hash_mismatch_exits_2`.
- [ ] `test_precondition_candidates_outside_gold_universe_exits_2` (RT-02) — ứng viên C mới không thuộc `pool ∪ S4` ⇒ mã 2.
- [ ] `test_precondition_served_model_family` (RT-04) — classifier `served_model` `gh/gpt-4o-mini` hoặc `unknown` ⇒ mã 2.
- [ ] `test_feasibility_drops_variant_e` (RT-12) — `expected_n_L` nhỏ ⇒ chỉ C, B; `feasibility` ghi.
- [ ] `test_gate_uses_conservative_precision` (RT-01) — 70 dự đoán CONFLICT, 54 có gold, 40 đúng ⇒ cổng dùng 40/70.
- [ ] `test_weighted_estimate_reported_not_gating`.
- [ ] `test_metric_prints_single_number`.
- [ ] `test_mcnemar_counts_b_and_c_on_same_items`.
- [ ] `test_decide_insufficient_n` — n=59 ⇒ `KEEP_OFF_INSUFFICIENT_N`.
- [ ] `test_decide_below_threshold` — 56/60 (≈0,841) ⇒ `KEEP_OFF_BELOW_THRESHOLD`; 57/60 (≈0,863) đạt.
- [ ] `test_decide_false_duplicate_veto`.
- [ ] `test_decide_uses_worse_trial`.
- [ ] `test_decide_refuses_decisions_sha_mismatch` (RT-15).
- [ ] `test_decide_thresholds_imported_from_review_policy`.
- [ ] `test_reports_have_no_clause_text`.

### Implement

Theo Implementation Steps 2–6.

### Tests After

- [ ] `test_committed_decision_matches_report` — tái tính `decide(l2-p5-bakeoff.json)` == `l2-p5-decision.json`.
- [ ] `test_committed_manifest_has_no_text` xanh với `heldout_review`.
- [ ] `bakeoff-verdict.json` có `run == contract-pairs-<YYMMDD>`, mỗi ứng viên ≥2 trial (hoặc lý do).
- [ ] `verification-P5.json` có commit khoá quyết định đứng **trước** thời điểm trial 1.

### Regression Gate

- Harness (repo root): `uv run --project ai-service --frozen --extra web --extra dev python -m pytest -q -p no:cacheprovider evals/contract_graph/tests`.
- ai-service (từ `ai-service/`): lệnh ở `plan.md` §Acceptance — đúng 13 lỗi môi trường.
- Lint: `uv run --project ai-service --frozen --extra dev ruff check --config ai-service/pyproject.toml evals/contract_graph/pairs evals/contract_graph/tests`.
- Review: `hs:code-review` ⇒ `review-decision.json`.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Precision lệch lạc quan do mẫu duyệt (RT-01) | `test_gate_uses_conservative_precision`, `test_weighted_estimate_reported_not_gating` |
| Critical | Ứng viên C ngoài vũ trụ gold (RT-02) | `test_precondition_candidates_outside_gold_universe_exits_2` |
| Critical | Quyết định duyệt sửa sau khi thấy scoreboard (RT-15) | `test_decide_refuses_decisions_sha_mismatch` + commit khoá trước trial 1 |
| Critical | Classifier unknown hoặc trùng model labeler (RT-04) | `test_precondition_served_model_family` |
| Critical | Ngưỡng bị chép/nới | `test_decide_thresholds_imported_from_review_policy`, `test_decide_below_threshold` |
| Critical | False DUPLICATE lọt cổng | `test_decide_false_duplicate_veto` |
| High | Chọn trial đẹp | `test_decide_uses_worse_trial` |
| High | Tốn tiền cho verdict đã biết (RT-12) | `test_feasibility_drops_variant_e` |
| High | Kết luận "khác nhau" từ khoảng chồng | McNemar/`--diff`; `test_mcnemar_counts_b_and_c_on_same_items` |
| Medium | Metric sai hợp đồng `bakeoff_rank` | `test_metric_prints_single_number` |

## Success

- [ ] HG-1 hoàn tất; `heldout_review` (sha quyết định) commit trước trial 1; `selection_sha256` khớp P2.
- [ ] Biến thể đã chọn × ≥2 trial chạy thật bằng classifier model được nhận diện (`served_model` thuộc họ classifier) — hoặc BLOCKED kèm Q3 (phase không PASS).
- [ ] `bakeoff-verdict.json`, `l2-p5-bakeoff.{json,md}`, `l2-p5-decision.json` commit; scoreboard đủ (thua, McNemar, cụm, bảo thủ/quan sát/1/π, hiệu chuẩn cận trên, chi phí).
- [ ] Verdict tính đúng ngưỡng `review_policy` (test tái tính khớp); không cờ nào bị đổi.
- [ ] §Số đo AI2-20 điền; hai suite xanh; `review-decision.json` có.

## Risks

| Rủi ro | L × I | Xử lý |
|---|---|---|
| n < 60 cho hầu hết nhãn | Cao × Trung bình | Q6 chấp nhận; `min_n_needed` + văn bản cần thêm; bỏ E khi chắc (RT-12) |
| Người dùng chưa duyệt xong | Trung bình × Cao | Chặn ở bước 0; P2 báo khối lượng sớm |
| Provider dao động giữa trial | Trung bình × Trung bình | Xen kẽ; worse-of; spread trong verdict |
| Classifier endpoint/model không khả dụng | Cao × Cao | BLOCKED (Q3) |
| Ngân sách preflight vượt mặc định | Trung bình × Thấp | Đặt budget rõ; thu hẹp E; không bỏ preflight |

## Rollback

`git revert <commit P5>`: gỡ runner, báo cáo, verdict, khối `heldout_review`, §Số đo doc. Runtime không đổi. Dữ liệu ngoài repo giữ nguyên.

## Amendment 2026-10-09 — final model

Người dùng cho phép model khác Claude. Snapshot cuối giữ một classifier duy nhất cho toàn bộ sáu trial: requested cx/gpt-6-sol, served gpt-6-sol, family openai; frozen labeler là gpt-4o-mini-2024-07-18, nên K-a đạt điều kiện khác model cụ thể. E vẫn bị budget block; HUMAN_DECISION không tự bật cờ.
