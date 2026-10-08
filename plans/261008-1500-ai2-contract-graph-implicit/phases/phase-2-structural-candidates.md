---
phase: 2
title: "Structural Candidates"
status: pending
plan: 261008-1500-ai2-contract-graph-implicit
created: 2026-10-08
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 2 — Structural Candidates (+ gold mở rộng + phiếu HG-1)

## Overview

Bộ sinh **ứng viên cặp** deterministic, không LLM: 4 nguồn `SAME_ARTICLE`, `EXPLICIT_REF` (bỏ dẫn chiếu văn bản ngoài — RT-09), `SAME_KEY` (chủ đề từ ngữ cảnh kế thừa), `REFERENCE_CUE`; loại cặp luồng 1; điểm cấu trúc + top-k. Đo recall trên **dev**, chốt `PAIRS_TOP_K` + lexicon (đóng băng). Sau khi đóng băng, sinh **tầng S4** = ứng viên B∪C trên held-out nằm ngoài pool P1, GPT gán nhãn S4, chọn mẫu HG-1 có trọng số π, khoá selection và xuất **một** phiếu duyệt (RT-02, RT-01, RT-12). Không bộ phân loại nào chạy trên held-out ở phase này. Chưa nối `run_idp`.

## Dependency map

- Phụ thuộc P1: `pairs/{corpus,pool,labeler,review,manifest,score,models}.py`, dữ liệu dev + held-out đã đóng băng, CLI `run.py`.
- Code tái dùng (đã đọc, không sửa):
  - `ai-service/app/pipeline/contract_graph/resolver.py:85-209` `StructureIndex` (`build` `:115`, `part_of` `:173`, `position` `:177`, `span` `:180`, `levels_of` `:185`, `canonical_of` `:189`, `body_parts`/`annex_parts` `:200-209`, `resolve` `:211`); `default_target_parts` (`:375`).
  - `ai-service/app/pipeline/contract_graph/address.py:91` `parse_addresses`, `:161` `canonical`.
  - `ai-service/app/pipeline/contract_graph/documents.py:24` `named_document` (regex đòi số có `/`, `:16-19` — không đủ cho "Luật Thương mại 2005", RT-09 OBSERVED).
  - `_SKIPPED_TYPES = {"FIELD", "TABLE"}` (`builder.py:69`).
  - `fold_for_match` (`ai1_snapshot_adapter.py`) cho từ khoá không dấu (không cho địa chỉ — luồng 1 D12).
- Được dùng bởi: P3 (`generate_pair_candidates`, `PairCandidate`, `clause_context`), P4 (stats), P5 (biến thể B, kiểm `candidates ⊆ pool ∪ S4`), HG-1.

## Requirements

### Chức năng

Module `ai-service/app/pipeline/contract_graph/pair_candidates.py`:

1. **Kiểu**: `PairSource(str, Enum)` (`SAME_ARTICLE`, `EXPLICIT_REF`, `SAME_KEY`, `REFERENCE_CUE`); `@dataclass(frozen=True) PairCandidate(node_a, node_b, sources: frozenset[PairSource], score: float, topic: str | None)` (a trước b theo `position`); `PairCandidateSet(candidates: tuple, stats: dict)` với `candidates_total`, `candidates_by_source`, `excluded_luong1`, `excluded_ancestor`, `excluded_short`, `excluded_external_ref`, `candidates_capped`, `candidates_kept`.
2. **Ngữ cảnh kế thừa** — `clause_context(index, nodes_by_id, node_id) -> str`: tiêu đề Điều/Phụ lục tổ tiên + câu dẫn của cha (phần trước `:` cuối), cắt `CONTEXT_CHARS_MAX = 300`; không gồm text của node.
3. **Chủ đề** — `topic_of(context, text)`: lexicon cố định (`PENALTY`, `PAYMENT`, `PRICE`, `DELIVERY`, `QUALITY`, `WARRANTY`, `TERM`, `TERMINATION`, `FORCE_MAJEURE`, `DISPUTE`, `CONFIDENTIALITY`), khớp sau `fold_for_match` trên tiêu đề trước rồi 80 ký tự đầu khoản; "Quyền và nghĩa vụ" không là chủ đề.
4. **Nguồn**:
   - `SAME_ARTICLE`: cùng `part_of` + cùng `dieu` (hoặc cùng Phụ lục), không tổ tiên–hậu duệ.
   - `EXPLICIT_REF`: `parse_addresses(text)` → `resolve` UNIQUE, ≠ chính nó, không tổ tiên–hậu duệ; bỏ địa chỉ SELF. **Bỏ địa chỉ dẫn chiếu văn bản ngoài** (RT-09): `named_document(câu chứa địa chỉ)` ≠ None, **hoặc** trong 60 ký tự sau địa chỉ (đã gập) có `luat|bo luat|nghi dinh|thong tu|quyet dinh|phap lenh|nghi quyet` ⇒ không cặp, đếm `excluded_external_ref`.
   - `SAME_KEY`: hai node khác Điều cùng `topic_of` ≠ None.
   - `REFERENCE_CUE`: cụm không số (`nêu trên`, `nói trên`, `kể trên`, `như trên`, `đã nêu`, `quy định ở trên`, `các trường hợp (nêu|quy định) (ở )?trên`, `theo (quy định|thỏa thuận) về <chủ đề>`, `tại phụ lục` không số) ⇒ ghép tối đa `CUE_LOOKBACK = 3` node đứng trước gần nhất cùng chủ đề.
5. **Loại trừ**: cặp ∈ `excluded_pairs` (cặp cạnh luồng 1); tổ tiên–hậu duệ; `FIELD`/`TABLE`; text < `MIN_CLAUSE_CHARS = 25`.
6. **Điểm + cắt**: `EXPLICIT_REF=4`, `REFERENCE_CUE=3`, `SAME_KEY=2`, `SAME_ARTICLE=1`; +1 `SAME_ARTICLE` liền kề; +1 thân↔phụ lục; sắp `(-score, position(a), position(b))`, giữ `top_k`. Tất định, không lặp `set` khi xuất.
7. **API**: `generate_pair_candidates(index, nodes, *, excluded_pairs=frozenset(), top_k=PAIRS_TOP_K, sources=ALL_SOURCES) -> PairCandidateSet`. Thuần, không I/O, không env.
8. **Hằng số**: `PAIRS_TOP_K` (ban đầu 40, chốt ở bước 6), `CONTEXT_CHARS_MAX = 300`, `MIN_CLAUSE_CHARS = 25`, `CUE_LOOKBACK = 3`, `CANDIDATES_VERSION = "pairs-cand-v1"` (tăng khi lexicon/K đổi).

Eval `evals/contract_graph/pairs/candidate_eval.py`:

9. `doc_record(doc)`: dựng `StructuralNode` từ `doc.json` + `StructureIndex.build(..., {doc_id: "body"})` + `excluded_pairs` từ `plan_edges` — dùng chung cho dev đo và S4 held-out (cùng code với runtime qua `generate_pair_candidates`).
10. **Đo dev** (`run.py candidates --split dev`; `--split heldout` ⇒ mã 2): `top_k=10**6` để có thứ hạng đầy đủ; báo cáo `l2-p2-candidates.{json,md}`: recall ứng viên trên gold GPT dev theo nguồn (riêng + biên), theo tầng S1/S2/S3, theo nhãn; recall@K với K ∈ {10, 20, 30, 40, 60, 80}; số ứng viên/hồ sơ; `excluded_external_ref`; số vòng chỉnh lexicon (≤2); `ground_truth: "gpt-labels (approved=false), dev"`.
11. **Tầng S4 held-out** (`run.py extend-heldout`, lệnh **duy nhất** của P2 được đọc held-out; gọi `verify` trước; từ chối nếu `CANDIDATES_VERSION`/`PAIRS_TOP_K` khác giá trị ghi ở báo cáo dev): với mỗi văn bản held-out sinh ứng viên biến thể C (mọi nguồn, `PAIRS_TOP_K`) và B (`{SAME_ARTICLE, EXPLICIT_REF}`, `PAIRS_TOP_K`); `S4 = (B ∪ C) − pool`; GPT gán nhãn S4 bằng `labeler` P1 (cùng model/prompt/cache, kiểm `served_model` openai); ghi `data_dir/heldout/<doc_id>/{s4.jsonl,labels.s4.gpt.jsonl}`; manifest thêm `extension_s4: {candidates_version, top_k, files: {doc_id: {name: sha256}}, n_pairs, labels_by_label}`.
12. **Chọn mẫu HG-1** (`run.py review-select`): `review.select_for_review` trên nhãn GPT held-out S1–S4 (D18: positive ≤75/nhãn, UNRELATED 80 phân tầng, π, trần 380); ghi `data_dir/review/selection.jsonl`; manifest thêm `review_selection: {sha256, n_rows, by_stratum, by_label, pi_table}` **trước** khi xuất phiếu (khoá chọn mẫu).
13. **Xuất phiếu** (`run.py review-export`) → `data_dir/review/heldout_review.csv`; in đường dẫn + số dòng; báo người dùng bắt đầu HG-1.

### Phi chức năng

- Tất định; không import ngoài `app.contracts.models`, `app.pipeline.contract_graph.{address,resolver,documents}`, `fold_for_match`.
- Không bộ phân loại (Claude) nào chạy trên held-out; GPT chỉ gán nhãn (cùng vai trò P1).
- Không đụng `idp.py`.

## Files — file inventory

| Hành động | Path | Cỡ ước tính | Ảnh hưởng test |
|---|---|---|---|
| Create | `ai-service/app/pipeline/contract_graph/pair_candidates.py` | ~250 dòng | `test_contract_graph_pair_candidates.py` |
| Create | `ai-service/tests/test_contract_graph_pair_candidates.py` | ~18 test | mới |
| Create | `evals/contract_graph/pairs/candidate_eval.py` | ~170 dòng (đo dev, S4, chọn mẫu, xuất) | `test_cg_pairs_candidate_eval.py` |
| Create | `evals/contract_graph/tests/test_cg_pairs_candidate_eval.py` | ~9 test | mới |
| Modify | `evals/contract_graph/pairs/run.py` | +`candidates`, `extend-heldout`, `review-select`, `review-export` | `test_cg_pairs_candidate_eval.py` |
| Modify | `evals/contract_graph/pairs/manifest.json` | khối `extension_s4`, `review_selection` (không văn bản) | `test_committed_manifest_has_no_text` |
| Create | `evals/contract_graph/reports/l2-p2-candidates.{json,md}` | nhỏ | — |
| Ngoài repo | `.harness/state/contract-graph-pairs/{heldout/*/s4*.jsonl,review/*}` | dữ liệu | — |

## Implementation Steps

1. Viết test RED → FAIL.
2. Implement kiểu + `clause_context` + `topic_of`.
3. Implement 4 nguồn (kèm lọc văn bản ngoài) + loại trừ.
4. Implement điểm + cắt + stats; kiểm tất định.
5. Implement `candidate_eval.py` (đo dev) + subcommand; chạy dev.
6. Chốt `PAIRS_TOP_K`: K nhỏ nhất trong lưới có recall@K ≥ 0,95 × recall không cắt; không có K ≤ 80 ⇒ giữ 40, ghi lý do. Tối đa 2 vòng chỉnh lexicon/cụm trên dev; ghi `CANDIDATES_VERSION` cuối. **Đóng băng**: từ đây không đổi `pair_candidates.py` (P3–P5 chỉ gọi).
7. `extend-heldout` → `review-select` (in số dòng; > 380 ⇒ lỗi, báo người dùng) → commit `manifest.json` (khoá `review_selection`) → `review-export`.
8. Regression gate → commit phase. Báo người dùng đường dẫn phiếu + số dòng (HG-1).

## TDD

### Tests Before (RED)

`ai-service/tests/test_contract_graph_pair_candidates.py`
- [ ] `test_clause_context_inherits_article_heading_and_lead`.
- [ ] `test_topic_from_heading_before_text`.
- [ ] `test_rights_and_obligations_is_not_a_topic`.
- [ ] `test_same_article_pairs`.
- [ ] `test_explicit_ref_resolves_clause_level`.
- [ ] `test_explicit_ref_to_external_law_dropped` (RT-09, parametrize) — "khoản 2 Điều 7 Luật Thương mại 2005", "Điều 300 Luật Thương mại", "khoản 1 Điều 4 Nghị định số 37/2015/NĐ-CP", "Điều 351 Bộ luật Dân sự" trên hồ sơ có khoản 2 Điều 7 / Điều 4 ⇒ không cặp, `excluded_external_ref` tăng; "khoản 2 Điều 7 của Hợp đồng này" ⇒ có cặp.
- [ ] `test_same_key_across_articles`.
- [ ] `test_reference_cue_links_nearest_preceding_same_topic`.
- [ ] `test_reference_cue_with_numeric_address_is_explicit_not_cue`.
- [ ] `test_luong1_pairs_excluded`.
- [ ] `test_ancestor_descendant_excluded`.
- [ ] `test_field_table_and_short_nodes_skipped`.
- [ ] `test_scores_and_order`.
- [ ] `test_top_k_cap_counts_capped`.
- [ ] `test_sources_filter_for_variant_b`.
- [ ] `test_deterministic_and_no_mutation`.
- [ ] `test_node_order_a_before_b`.
- [ ] `test_candidates_version_constant_present`.

`evals/contract_graph/tests/test_cg_pairs_candidate_eval.py`
- [ ] `test_recall_by_source_and_marginal`.
- [ ] `test_recall_at_k_curve_monotonic`.
- [ ] `test_recall_by_stratum_uses_p1_strata`.
- [ ] `test_heldout_split_refused_for_candidates`.
- [ ] `test_extend_heldout_is_b_union_c_minus_pool` (RT-02) — 2 văn bản giả: S4 đúng bằng (B ∪ C) − pool, không trùng pool.
- [ ] `test_extend_heldout_refuses_version_mismatch` — `PAIRS_TOP_K` khác báo cáo dev ⇒ mã 2.
- [ ] `test_extend_heldout_runs_verify_first` — held-out bị sửa ⇒ mã 2, labeler không gọi.
- [ ] `test_review_selection_locked_in_manifest_before_export` — `review-export` không có `review_selection` sha khớp ⇒ mã 2.
- [ ] `test_reports_have_no_clause_text`.

### Implement

Theo Implementation Steps 2–7.

### Tests After

- [ ] `test_top_k_constant_matches_report` — `PAIRS_TOP_K`, `CANDIDATES_VERSION` == giá trị trong `l2-p2-candidates.json`.
- [ ] `test_committed_manifest_has_no_text` xanh với khối `extension_s4`, `review_selection`.
- [ ] `l2-p2-candidates.json` thật có recall theo nguồn/tầng/nhãn (k/n + Wilson + cụm), recall@K, K chọn, số vòng chỉnh, kích thước S4 held-out + số dòng phiếu.

### Regression Gate

- ai-service (từ `ai-service/`): lệnh ở `plan.md` §Acceptance — đúng 13 lỗi môi trường.
- Harness (repo root): `uv run --project ai-service --frozen --extra web --extra dev python -m pytest -q -p no:cacheprovider evals/contract_graph/tests`.
- Focused: `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q tests/test_contract_graph_pair_candidates.py tests/test_contract_graph_resolver.py tests/test_contract_graph_address.py`.
- Lint: `uv run --frozen --extra dev ruff check app/pipeline/contract_graph/pair_candidates.py tests/test_contract_graph_pair_candidates.py` + ruff evals (lệnh ở plan.md).

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Ứng viên khác Điều không có gold ⇒ cổng mù phần giá trị của luồng 2 (RT-02) | `test_extend_heldout_is_b_union_c_minus_pool` |
| Critical | Chọn lại mẫu duyệt sau khi thấy kết quả | `test_review_selection_locked_in_manifest_before_export` |
| Critical | Cặp luồng 1 gửi LLM lại | `test_luong1_pairs_excluded` |
| Critical | Output lắc ⇒ top-k khác nhau | `test_deterministic_and_no_mutation`, `test_scores_and_order` |
| High | Dẫn chiếu luật ngoài chiếm suất top-k (RT-09) | `test_explicit_ref_to_external_law_dropped` |
| High | Code ứng viên đổi sau khi sinh S4 ⇒ ứng viên P5 ngoài vũ trụ gold | `test_extend_heldout_refuses_version_mismatch` + P5 bước 0 |
| High | Khoản lược chủ ngữ mất chủ đề | `test_clause_context_inherits_article_heading_and_lead`, `test_topic_from_heading_before_text` |
| High | Tune trên held-out | `test_heldout_split_refused_for_candidates`, `test_extend_heldout_runs_verify_first` |
| Medium | Cặp container | `test_ancestor_descendant_excluded` |

## Success

- [ ] Mọi test P2 xanh; hai suite xanh; ruff sạch.
- [ ] `l2-p2-candidates.{json,md}` commit; `PAIRS_TOP_K` + `CANDIDATES_VERSION` chốt và đóng băng.
- [ ] S4 sinh + gán nhãn; `review_selection` khoá trong manifest; phiếu xuất ≤ 380 dòng; người dùng được báo (HG-1).

## Risks

| Rủi ro | L × I | Xử lý |
|---|---|---|
| Recall S3 thấp | Cao × Trung bình | Báo đúng số; giới hạn đã biết của hướng C |
| Lexicon quá khít dev | Trung bình × Trung bình | ≤2 vòng; đóng băng trước S4 |
| S4 lớn đẩy phiếu > 380 | Trung bình × Trung bình | Trần π trong `select_for_review`; lỗi rõ thay vì tự cắt |
| Cây AI1 thật khác cây `segment` | Trung bình × Trung bình | Dùng chung `StructureIndex`; P4 test trên record AI1-shape |

## Rollback

`git revert <commit P2>`: gỡ module, eval, báo cáo, khối manifest. Runtime không đổi. Dữ liệu S4/phiếu ngoài repo giữ nguyên.
