---
phase: 1
title: "Pair Label Dataset"
status: pending
plan: 261008-1500-ai2-contract-graph-implicit
created: 2026-10-08
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 1 — Pair Label Dataset

## Overview

Dựng bộ nhãn **cặp khoản** cho luồng 2 từ ≥15 mẫu HĐ SALES / SUPPLY_SERVICE công khai: tải + chuẩn hoá + tách Điều/khoản/điểm → **gom cụm gần trùng** rồi chia split theo cụm (D15, RT-13) → pool cặp S1–S3 (D17) → GPT gán nhãn đóng có span, ghi model thực phục vụ (D16, RT-04) → manifest sha256 khoá held-out. Cung cấp module chọn mẫu duyệt có trọng số π và scorer bảo thủ + có trọng số (D18, RT-01) để P2/P5 dùng. Dữ liệu nằm **ngoài repo** ở `AI2_CG_PAIRS_DATA_DIR` = `.harness/state/contract-graph-pairs/` (D14, Q8); repo chỉ có code, manifest không văn bản và báo cáo tổng hợp. Không đụng runtime `ai-service/app/`.

Phiếu duyệt HG-1 **không** xuất ở phase này: P2 xuất sau khi thêm tầng S4 (RT-02) để một phiếu phủ đủ.

## Dependency map

- Không phụ thuộc phase nào của plan. Base `83f2d75`.
- Tái dùng (đã đọc, không sửa):
  - `evals/contract_graph/dataset.py:39-67` `cache_key`, `fetch_cached` (`CacheMiss` khi offline), `:188` `file_digest`, `:196-203` `_write`/`_json_line` (LF, UTF-8); mẫu freeze/verify `:103-181`.
  - `evals/contract_graph/normalize.py:37` `html_to_text`.
  - `evals/contract_graph/segment.py:27-74` `segment(text, doc_id)`; regex `ARTICLE` (`:14`) đòi dấu `.` sau số ⇒ chuẩn hoá tiêu đề trước.
  - `evals/contract_graph/score.py:29` `wilson`, `:39` `rate`.
  - `ai-service/app/pipeline/contract_graph/builder.py:124` `plan_edges` + `resolver.StructureIndex.build` (`resolver.py:115`) để loại cặp có cạnh luồng 1 (mẫu dựng node: `evals/contract_graph/pipeline_predictor.py:53-99`).
  - `fold_for_match` (`ai-service/app/pipeline/ai1_snapshot_adapter.py`) để chuẩn hoá khi gom cụm.
  - `evals/contract_graph/tests/conftest.py:20-25` chặn mạng (autouse).
  - Văn bản spike `evals/spikes/clause_key/clauses_heldout.jsonl`, `clauses_heldout2.jsonl` + URL `heldout_sources.json`, `heldout2_sources.json` (kiểm nhiễm bẩn — chỉ đọc).
  - Ý tưởng/hợp đồng CLI của probe `.harness/state/bakeoff/contract-edge-261007/probe.py` (`LABELS`, grounding `:106-111`, trường báo cáo `:198-205`) — không import.
- Được dùng bởi: P2 (node, pool, nhãn dev, `labeler`, `review.select_for_review`, `manifest`), P3 (dev), P5 (held-out, `review.import_sheet`, `score`).

## Requirements

### Chức năng

1. **Nguồn** — `evals/contract_graph/pairs/sources.json`: `{url, profile: SALES|SUPPLY_SERVICE, title, has_annex_section: bool|null, note}`; ≥15 mục **dùng được** (≥5 Điều sau tách), mỗi profile ≥6; ưu tiên mẫu có phần "PHỤ LỤC" trong cùng văn bản; không nguồn 403/paywall. `split` không ghi tay.
2. **Corpus** — `pairs/corpus.py`:
   - `fetch` qua `dataset.fetch_cached` (cache dưới thư mục dữ liệu).
   - `normalize_headings(text)`: dòng mở `ĐIỀU|Điều|DIEU` + số + `[:.\-–]` ⇒ `Điều N.`; dòng `PHỤ LỤC` ⇒ `Phụ lục …`; giữa dòng không đổi.
   - `build_doc(source, text)`: `doc_id = "pd-" + sha256(url)[:10]`; `nodes = segment(normalize_headings(text), doc_id)`; bỏ node text < 20 ký tự không con; mỗi node thêm `heading` (tiêu đề Điều/Phụ lục tổ tiên ≤120 ký tự). < 5 Điều ⇒ loại, đếm `rejected_segmentation`.
   - `near_duplicate_clusters(docs)` (RT-13): văn bản → `fold_for_match` + gộp khoảng trắng → tập shingle 5-từ; hai văn bản cùng cụm khi Jaccard ≥ 0,8 **hoặc** sha256 chuỗi tiêu đề Điều (đã gập) bằng nhau; union-find, tất định.
   - `contaminated(doc)`: URL ∈ `heldout_sources.json`/`heldout2_sources.json`/dạng `repo:` **hoặc** containment shingle của bất kỳ khoản spike (`clauses_heldout*.jsonl`, trường `text`) trong văn bản ≥ 0,5 ⇒ `True`.
3. **Pool** — `pairs/pool.py` (D17), `POOL_SEED = 20261008`:
   - Cặp không thứ tự cùng văn bản, `pair_id = sha256(doc_id|a|b)[:16]`, a trước b theo `order`; bỏ tổ tiên–hậu duệ.
   - S1 mọi cặp cùng Điều; S2 mọi cặp thân↔Phụ lục (trần 200/văn bản, chọn theo seed); S3 `min(40, tất cả)` cặp khác Điều ngoài S1/S2 theo seed. Chọn ngẫu nhiên bằng `random.Random(seed ^ int(sha256(doc_id)[:8], 16))` trên danh sách đã **sắp** (không lặp `set`).
   - Loại cặp có cạnh luồng 1 (`plan_edges` trên `StructureIndex` của văn bản, vai trò `body`/`annex`), đếm `excluded_luong1`.
   - Bản ghi `{pair_id, doc_id, a, b, stratum}` — không văn bản.
   - `estimate_review_rows(pools, labels)` (RT-12): in số dòng HG-1 dự kiến theo quy tắc D18 (GPT-positive theo nhãn, trần 75/nhãn; 80 UNRELATED) — chạy ở `summary` **trước** `freeze`, ghi vào báo cáo (S4 chưa có, P2 cập nhật).
4. **Người gán nhãn GPT** — `pairs/labeler.py` (D16):
   - `LABELS = ("GENERAL_SPECIFIC", "CONFLICT", "DUPLICATE", "REFERENCE", "UNRELATED")`; định nghĩa + quy tắc phân xử lấy từ `pairs/LABELING.vi.md` (một nguồn cho người và prompt): GENERAL_SPECIFIC cần `general: A|B`; REFERENCE (dẫn chiếu **không** số Điều) cần `referrer: A|B`; không chắc ⇒ UNRELATED; không kết luận pháp lý.
   - `LABELER_PROMPT_VERSION = "pairs-labeler-v1"`; mỗi cặp một lời gọi; client OpenAI-compatible từ `AI2_CG_LABELER_BASE_URL`/`_API_KEY`/`_MODEL` (hoặc `--env-file`); thiếu ⇒ thoát mã 2, không fallback ngầm.
   - Input: `heading` + `text` của A, B dạng chuỗi JSON.
   - Kiểm: nhãn ∉ tập ⇒ `label_invalid`; span (bắt buộc với nhãn ≠ UNRELATED) phải là chuỗi con của `text` sau NFC + gộp khoảng trắng ⇒ không thì `grounded=false` (giữ, gắn cờ).
   - `family(model_id)` (RT-04, dùng chung P3/P5, đặt ở `pairs/models.py`): đoạn sau `/` cuối, chữ thường; `gpt*`/`chatgpt*`/`o\d*` ⇒ `openai`; `claude*` ⇒ `anthropic`; khác ⇒ `unknown`.
   - Ghi `served_model = resp.model` (model provider thực trả) vào bản ghi; `family(served_model) != "openai"` ⇒ dừng mã 2 (K-a, fail-closed).
   - Cache: `cache/labeler/<sha256(model|prompt_version|system|user)>.json`; chạy lại ⇒ không gọi mạng.
   - Bản ghi: `{pair_id, label, general|referrer|null, span_a, span_b, grounded, requested_model, served_model, prompt_version, request_digest}`.
5. **Đóng băng** — `pairs/manifest.py`:
   - `ensure_outside_repo(data_dir)`: `git check-ignore -q <data_dir>/probe` phải exit 0 (thư mục bị bỏ qua) **và** `data_dir` không nằm dưới `evals/`, `ai-service/`, `docs/` ⇒ không thì thoát mã 2.
   - `assign_splits(clusters, contaminated)`: cụm có văn bản nhiễm bẩn ⇒ `dev` (đếm `forced_dev_contaminated`); cụm còn lại sắp theo `min sha256(url)` trong cụm, `ceil(2/3·N_cụm)` đầu ⇒ `heldout`, còn lại `dev`.
   - `freeze(data_dir, repo_manifest_path)`: ghi `data_dir/<split>/<doc_id>/{doc.json,pool.jsonl,labels.gpt.jsonl}` (LF, UTF-8, `sort_keys`), rồi manifest **trong repo** `evals/contract_graph/pairs/manifest.json`: `{schema: "contract-graph-pairs-dataset/1", ground_truth, pool_seed, pool_params, labeler: {requested_model, served_model, family, prompt_version}, clusters: [{cluster_id, doc_ids, split}], docs: [{doc_id, url, profile, split, cluster_id, files: {name: sha256}, n_nodes, n_pairs_by_stratum, labels_by_label}], extension_s4: null, review_selection: null, heldout_review: null, frozen_at}` — không văn bản.
   - `verify(data_dir, repo_manifest)` → lỗi (thiếu file, sha lệch, doc thừa/thiếu); lệnh đọc held-out gọi `verify` trước, lỗi ⇒ mã 2.
6. **Chọn mẫu + phiếu** — `pairs/review.py` (D18, RT-01; P2 gọi `select_for_review` + `export_sheet`, P5 gọi `import_sheet`):
   - `select_for_review(labels_by_stratum, seed)`: mỗi nhãn GPT-positive: lấy hết nếu ≤ `POSITIVE_CAP = 75`, vượt thì mẫu seed 75; GPT-UNRELATED: tổng `UNRELATED_SAMPLE = 80`, phân bổ theo tỷ lệ số cặp mỗi tầng (S1/S2/S3/S4), tối thiểu 10/tầng nếu đủ; mỗi bản ghi chọn mang `stratum`, `gpt_label`, `pi` (xác suất chọn của ô). Trần tổng `REVIEW_ROW_CAP = 380` (vượt ⇒ lỗi kèm số, không tự cắt).
   - `export_sheet(...)` → CSV UTF-8 BOM: `pair_id, doc_id, heading_a, text_a, heading_b, text_b, gpt_label, gpt_direction, gpt_span_a, gpt_span_b, grounded, decision, label_fixed, direction_fixed, note`.
   - `import_sheet(csv) -> list[decision]`: `decision ∈ {approve, relabel, reject}`; `relabel` bắt buộc `label_fixed` (+ hướng nếu cần); lỗi có số dòng; kết quả `{pair_id, gold_label, gold_direction, approved, source: "user-review"}`.
   - `labeler_confusion(selection, decisions)` → ma trận GPT↔người theo nhãn + tầng (báo cáo ghi là **cận trên** đồng thuận vì người duyệt thấy nhãn GPT).
7. **Scorer** — `pairs/score.py` (P2/P3/P5):
   - `score_relations(gold, preds, *, approved_only, selection=None)`: ghép `pair_id` không thứ tự. Mỗi nhãn ≠ UNRELATED:
     - `precision_conservative = rate(đúng, tất cả dự đoán nhãn đó trong vũ trụ chấm)` — dự đoán trên cặp không có gold duyệt tính **sai** (RT-01);
     - `precision_observed = rate(đúng, dự đoán có gold duyệt)`;
     - `precision_weighted` / `recall_weighted` = ước lượng Horvitz–Thompson với trọng số `1/pi` của bản ghi duyệt (chỉ khi có `selection`), ghi `estimator: "horvitz-thompson"` (không có khoảng Wilson — chỉ báo);
     - `recall_observed = rate(đúng, gold duyệt positive)`; `direction_accuracy`; `false_duplicate`;
     - theo tầng và theo văn bản (cụm) để tính khoảng theo cụm.
   - Tách `denominator`/`covered`/`passed`; `ground_truth` ghi rõ nguồn.
   - `render_markdown` chỉ in số, `pair_id`, `doc_id`.
8. **CLI** — `pairs/run.py`: `fetch`, `build`, `cluster`, `pool`, `label`, `summary`, `freeze`, `verify`. `--data-dir` mặc định `$AI2_CG_PAIRS_DATA_DIR` rồi `.harness/state/contract-graph-pairs`. `summary` ghi `evals/contract_graph/reports/l2-p1-dataset.{json,md}` (gồm ước số dòng HG-1).
9. **Hướng dẫn** — `pairs/LABELING.vi.md` (định nghĩa, phân xử, ví dụ tổng hợp ngắn tự viết, cách điền phiếu) và `pairs/README.md` (env, lệnh, quy tắc ngoài repo, HG-1 sau P2).

### Phi chức năng

- Test không gọi mạng/LLM.
- Tất định: cùng seed + cache ⇒ cùng cụm, split, pool, nhãn, sha256 — kể cả khác `PYTHONHASHSEED` (test subprocess).
- Repo không chứa văn bản HĐ, span hay phiếu (D14); không log văn bản/response.
- `.gitattributes` thêm `evals/contract_graph/pairs/*.json text eol=lf`.

## Files — file inventory

| Hành động | Path | Cỡ ước tính | Ảnh hưởng test |
|---|---|---|---|
| Create | `evals/contract_graph/pairs/__init__.py` | 1 dòng | — |
| Create | `evals/contract_graph/pairs/README.md` | ~60 dòng | — |
| Create | `evals/contract_graph/pairs/LABELING.vi.md` | ~120 dòng | `test_cg_pairs_labeler.py` |
| Create | `evals/contract_graph/pairs/sources.json` | ≥15 mục | `test_cg_pairs_manifest.py` |
| Create | `evals/contract_graph/pairs/models.py` | ~30 dòng (`family`) | `test_cg_pairs_labeler.py` |
| Create | `evals/contract_graph/pairs/corpus.py` | ~170 dòng | `test_cg_pairs_corpus.py` |
| Create | `evals/contract_graph/pairs/pool.py` | ~140 dòng | `test_cg_pairs_pool.py` |
| Create | `evals/contract_graph/pairs/labeler.py` | ~160 dòng | `test_cg_pairs_labeler.py` |
| Create | `evals/contract_graph/pairs/review.py` | ~150 dòng | `test_cg_pairs_review.py` |
| Create | `evals/contract_graph/pairs/manifest.py` | ~150 dòng | `test_cg_pairs_manifest.py` |
| Create | `evals/contract_graph/pairs/score.py` | ~190 dòng | `test_cg_pairs_score.py` |
| Create | `evals/contract_graph/pairs/run.py` | ~130 dòng | `test_cg_pairs_manifest.py::test_cli_verify_exit_codes` |
| Create | `evals/contract_graph/pairs/manifest.json` | sinh bởi `freeze` | `test_committed_manifest_has_no_text` |
| Create | `evals/contract_graph/reports/l2-p1-dataset.{json,md}` | nhỏ | — |
| Create | `evals/contract_graph/tests/test_cg_pairs_{corpus,pool,labeler,review,manifest,score}.py` | 6 file | mới |
| Modify | `.gitattributes` | +1 dòng | — |
| Ngoài repo | `.harness/state/contract-graph-pairs/{cache,dev,heldout}/**` | dữ liệu | — |

Hơn 8 file: mỗi module một trách nhiệm (nguồn/tách/cụm, pool, gán nhãn, họ model, chọn mẫu/phiếu, manifest, chấm, CLI), test 1:1.

## Implementation Steps

1. Probe (Probe-first): một lời gọi `labeler` thật trên 1 cặp tổng hợp; ghi `requested_model`, `served_model`, `family`, token, độ trễ vào `verification-P1.json`. Thiếu key hoặc `family(served_model) != openai` ⇒ P1 **BLOCKED** (không đổi model — K-a).
2. Viết test RED (6 file) → FAIL.
3. Implement `models.py`, `corpus.py`, `pool.py`, `labeler.py`, `review.py`, `manifest.py`, `score.py`, `run.py`; viết `LABELING.vi.md`, `README.md`.
4. Tìm nguồn: ≥15 dùng được (SALES ≥6, SUPPLY_SERVICE ≥6); thiếu ⇒ BLOCKED kèm số.
5. Chạy thật: `fetch` → `build` → `cluster` → `pool` (chạy 2 lần trong subprocess với `PYTHONHASHSEED=0` và `=1`, sha pool phải bằng) → `label` → `summary` (đọc ước số dòng HG-1; nếu > 380 ⇒ dừng, báo người dùng trước khi freeze) → `freeze` → `verify` (exit 0).
6. Kiểm repo sạch văn bản: `git status` chỉ thấy file inventory; `ensure_outside_repo` OK.
7. Regression gate → commit phase.

## TDD

### Tests Before (RED)

`evals/contract_graph/tests/test_cg_pairs_corpus.py`
- [ ] `test_normalize_headings_variants` — "ĐIỀU 1: ĐỐI TƯỢNG", "Điều 2 – Giá", "Điều 3. Thanh toán", "PHỤ LỤC 01", "Phụ lục" ⇒ dòng chuẩn; "theo Điều 5: …" giữa dòng không đổi.
- [ ] `test_build_doc_inherits_heading`.
- [ ] `test_doc_with_fewer_than_five_articles_rejected`.
- [ ] `test_doc_id_is_stable_hash_of_url`.
- [ ] `test_near_duplicates_share_cluster` (RT-13) — hai văn bản tổng hợp chỉ khác tên bên/địa chỉ ⇒ cùng cụm; văn bản khác chủ đề ⇒ khác cụm.
- [ ] `test_content_contamination_detected` — văn bản chứa nguyên một khoản spike (chuỗi giả lập trong test) ⇒ `contaminated=True` dù URL khác.

`evals/contract_graph/tests/test_cg_pairs_pool.py`
- [ ] `test_same_article_stratum_is_exhaustive`.
- [ ] `test_body_annex_stratum_and_cap`.
- [ ] `test_cross_article_sample_is_seeded_and_disjoint`.
- [ ] `test_ancestor_pairs_excluded`.
- [ ] `test_luong1_edge_pairs_excluded`.
- [ ] `test_pool_records_carry_no_text`.
- [ ] `test_pool_stable_across_hash_seeds` — subprocess `PYTHONHASHSEED=0` và `=7` cho cùng sha pool.
- [ ] `test_estimate_review_rows_applies_caps`.

`evals/contract_graph/tests/test_cg_pairs_labeler.py` (client giả)
- [ ] `test_closed_label_set_and_invalid_label_flagged`.
- [ ] `test_span_grounding_flags_not_drops`.
- [ ] `test_span_from_heading_is_not_grounded`.
- [ ] `test_direction_required_for_general_specific_and_reference`.
- [ ] `test_cache_hit_makes_no_call`.
- [ ] `test_missing_labeler_env_exits_2`.
- [ ] `test_clause_text_sent_as_json_string`.
- [ ] `test_prompt_definitions_come_from_labeling_md`.
- [ ] `test_family_router_prefix_and_unknown` (RT-04) — `gh/gpt-4o-mini`, `openai/gpt-4.1`, `o3-mini` ⇒ openai; `anthropic/claude-sonnet-x`, `claude-…` ⇒ anthropic; `mistral-large`, `""` ⇒ unknown.
- [ ] `test_served_model_recorded_and_non_openai_exits_2` — client giả trả `resp.model="claude-x"` ⇒ mã 2.

`evals/contract_graph/tests/test_cg_pairs_review.py`
- [ ] `test_selection_caps_and_pi` (RT-01/RT-12) — nhãn có 120 positive ⇒ 75, `pi=75/120`; nhãn 30 ⇒ 30, `pi=1`; UNRELATED 80 phân tầng, `pi` từng ô đúng.
- [ ] `test_selection_over_row_cap_errors` — vượt 380 ⇒ lỗi kèm số.
- [ ] `test_selection_deterministic`.
- [ ] `test_import_requires_label_for_relabel`.
- [ ] `test_import_reject_is_not_approved`.
- [ ] `test_import_unknown_decision_is_error`.
- [ ] `test_labeler_confusion_counts_by_stratum`.
- [ ] `test_export_roundtrip_utf8_bom`.

`evals/contract_graph/tests/test_cg_pairs_manifest.py`
- [ ] `test_split_by_cluster_two_thirds_heldout` — cụm 2 văn bản không bị tách qua split.
- [ ] `test_contaminated_cluster_forced_to_dev` — URL spike, `repo:`, hoặc nhiễm bẩn nội dung ⇒ cả cụm dev.
- [ ] `test_verify_detects_tamper`.
- [ ] `test_committed_manifest_has_no_text` — không khoá `text`, `span_a`, `span_b`, `heading`; mọi chuỗi ≤ 300 ký tự.
- [ ] `test_cli_verify_exit_codes`.
- [ ] `test_sources_schema`.
- [ ] `test_ensure_outside_repo` — thư mục không bị ignore hoặc nằm dưới `evals/` ⇒ mã 2.

`evals/contract_graph/tests/test_cg_pairs_score.py`
- [ ] `test_conservative_precision_counts_unreviewed_as_wrong` (RT-01) — 70 dự đoán, 54 có gold duyệt, 40 đúng ⇒ bảo thủ 40/70, quan sát 40/54.
- [ ] `test_weighted_estimate_uses_inverse_pi`.
- [ ] `test_false_duplicate_counted`.
- [ ] `test_approved_only_filters_unapproved_gold`.
- [ ] `test_direction_accuracy_separate_from_label_match`.
- [ ] `test_recall_by_stratum_and_by_doc`.
- [ ] `test_markdown_has_no_clause_text`.

### Implement

Theo Implementation Steps 3–5.

### Tests After

- [ ] `test_committed_manifest_has_no_text` chạy trên `manifest.json` thật.
- [ ] `run.py verify` exit 0 trên dữ liệu thật (ghi `verification-P1.json`).
- [ ] `l2-p1-dataset.json` có: số văn bản theo profile/split/cụm, `rejected_segmentation`, `forced_dev_contaminated`, số cụm gần trùng, cặp theo tầng, `excluded_luong1`, nhãn GPT theo nhãn × split, `label_invalid`, `grounded=false`, `served_model` + họ, ước số dòng HG-1 (chưa gồm S4).

### Regression Gate

- Harness (repo root): `uv run --project ai-service --frozen --extra web --extra dev python -m pytest -q -p no:cacheprovider evals/contract_graph/tests` — 77 cũ + mới xanh.
- Lint: `uv run --project ai-service --frozen --extra dev ruff check --config ai-service/pyproject.toml evals/contract_graph/pairs evals/contract_graph/tests`.
- Suite ai-service (phase không sửa `ai-service/`): chạy một lần trước commit, đúng 13 lỗi môi trường.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Văn bản HĐ/span lọt vào repo | `test_committed_manifest_has_no_text`, `test_pool_records_carry_no_text`, `test_markdown_has_no_clause_text`, `test_ensure_outside_repo` |
| Critical | Held-out bị sửa sau đóng băng | `test_verify_detects_tamper`, `test_cli_verify_exit_codes` |
| Critical | Bản gần trùng / nội dung spike lọt vào held-out (RT-13) | `test_near_duplicates_share_cluster`, `test_split_by_cluster_two_thirds_heldout`, `test_content_contamination_detected`, `test_contaminated_cluster_forced_to_dev` |
| Critical | Precision lệch lạc quan do mẫu duyệt (RT-01) | `test_conservative_precision_counts_unreviewed_as_wrong`, `test_selection_caps_and_pi` |
| Critical | Người gán nhãn không phải GPT mà không ai biết (RT-04) | `test_family_router_prefix_and_unknown`, `test_served_model_recorded_and_non_openai_exits_2` |
| High | Pool lắc theo hash seed | `test_pool_stable_across_hash_seeds` |
| High | Span bịa của GPT được tin | `test_span_grounding_flags_not_drops`, `test_span_from_heading_is_not_grounded` |
| High | Khối lượng duyệt vượt dự kiến (RT-12) | `test_estimate_review_rows_applies_caps`, `test_selection_over_row_cap_errors` |
| High | Cặp có cạnh luồng 1 bị gán lại | `test_luong1_edge_pairs_excluded` |
| Medium | Gọi lại LLM khi có cache | `test_cache_hit_makes_no_call` |
| Medium | Thiếu env ⇒ client khác ngầm | `test_missing_labeler_env_exits_2` |

## Success

- [ ] ≥15 văn bản dùng được (SALES ≥6, SUPPLY_SERVICE ≥6); held-out ≥10 văn bản, dev ≥5; không cụm nhiễm bẩn nào trong held-out.
- [ ] `manifest.json` commit, `verify` exit 0; sha256 manifest trong `verification-P1.json`.
- [ ] Mọi cặp pool có nhãn GPT (hoặc lỗi được đếm); `served_model` thuộc họ `openai`.
- [ ] Ước số dòng HG-1 (trước S4) ≤ 380 hoặc đã báo người dùng.
- [ ] `l2-p1-dataset.{json,md}` commit; test harness xanh; ruff sạch.

## Risks

| Rủi ro | L × I | Xử lý |
|---|---|---|
| Không đủ 15 mẫu tách được | Trung bình × Cao | Cache raw; `normalize_headings`; BLOCKED kèm số |
| Gom cụm làm held-out < 10 văn bản | Trung bình × Trung bình | Báo số cụm; tìm thêm nguồn khác chủ đề trước freeze; không bỏ gom cụm |
| Mẫu soạn sẵn ít CONFLICT/DUPLICATE | Cao × Trung bình | Báo đúng số; không chèn dữ liệu tổng hợp vào held-out (Q6) |
| GPT gán CONFLICT tràn lan | Cao × Cao | Hướng dẫn "không chắc ⇒ UNRELATED"; HG-1; cổng bảo thủ |
| `.harness/` chỉ bị bỏ qua cục bộ (`.git/info/exclude:12`) | Trung bình × Cao | `ensure_outside_repo` trước mọi ghi |

## Rollback

`git revert <commit P1>`: gỡ `evals/contract_graph/pairs/`, test, báo cáo, dòng `.gitattributes`. Runtime không đổi. Dữ liệu ngoài repo giữ nguyên.
