---
phase: 1
title: "Vbhn Eval Harness"
status: pending
plan: 261007-1735-ai2-contract-graph-op-first
created: 2026-10-07
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 1 — Vbhn Eval Harness

## Overview

Dựng bộ đo tự động, track trong repo, tại `evals/contract_graph/`: lấy (có cache) ≥10 cặp (văn bản sửa đổi, VBHN) của nhiều cơ quan, có ca `REPEAL`; chuẩn hoá HTML/DOCX thành text; trích gold từ chú thích VBHN; đông cứng bộ dữ liệu kèm manifest sha256; scorer in precision/recall/độ đúng đích theo loại cạnh + Wilson CI. Predictor baseline là parser spike được port lại, dùng để tự kiểm harness (phải tái lập số spike trên cặp NĐ 50/2021). Phase này **không** sửa code runtime của `ai-service/`.

Vì sao trước: mọi phase sau (resolver, parser) cần một thước đo chung; spike mới có n=1 cặp và chưa bao giờ đo độ đúng **đích** (`[ASSUMED]` trong `plans/reports/spike-261007-1719-operation-parser-vbhn-report.md` §Giới hạn 1).

## Dependency map

- Phụ thuộc: không phase nào. Cần commit `70998af` (`ai-service/app/pipeline/relation_markers.py`) để predictor baseline đo `marker_hit` như spike.
- Được dùng bởi: P2 (`resolver_eval.py` đọc `data/`, `segment.py`), P3 (`pipeline_predictor.py` cắm vào `run_eval.py`, chấm bằng `score.py`).
- Nguồn port: `.harness/state/vbhn-probe/scripts/vbhn_notes.py` (trích chú thích, OPS), `op_parser_eval.py` (parser baseline, chọn "Điều 1." dài nhất), `footnotes.py` (DOCX footnote + anchor). Dữ liệu spike: `.harness/state/vbhn-probe/raw/nd50.html`, `vbhn02bxd.html` (thư mục `.harness/` bị loại khỏi git qua `.git/info/exclude` — OBSERVED `git check-ignore`), nên phải chuẩn hoá rồi commit bản text.

## Requirements

### Chức năng

1. **Chuẩn hoá** (`normalize.py`)
   - `html_to_text(raw) -> str`: bỏ `script/style`; **giải mã HTML bị escape trong chuỗi JSON** (OBSERVED: trong `vbhn02bxd.html` khối chú thích nằm trong payload Next.js dạng `</span>…`); thẻ khối (`p, div, br, li, tr, h1–h6`) → xuống dòng; `html.unescape`; gộp khoảng trắng; nối đoạn bị ngắt cứng (dòng không kết thúc bằng `.;:` và dòng sau bắt đầu chữ thường).
   - `docx_to_text(data: bytes) -> str`: đọc `word/document.xml` + `word/footnotes.xml` bằng `zipfile` + `xml.etree`; chèn marker `[n]` tại vị trí `footnoteReference` và nối khối chú thích cuối văn bản ⇒ HTML và DOCX ra **cùng một dạng** cho bước trích gold.
   - `operative_body(text, article="1", next_article="2") -> str`: trong các lần xuất hiện `Điều <article>.`, lấy lần có thân dài nhất tới `Điều <next_article>.` (bỏ mục lục — lỗi spike #2). **Điểm cắt chỉ tính khi `Điều <next_article>.` nằm ngoài ngoặc kép** (theo dõi độ sâu `“…”` và `"…"` khi quét): Điều 1 của văn bản sửa đổi hay trích nguyên văn “Điều 2. …” của văn bản gốc (RT-14; red-team OBSERVED trên `nd50.html`: “Điều 23.”, “Điều 36.”, “Điều 42.” nằm trong ngoặc kép ở Điều 1). Không port nguyên `text.find("Điều 2.", …)` của `op_parser_eval.py:43`.
2. **Gold** (`gold.py`)
   - `extract_notes(text) -> list[Note]`: chú thích `[n] … được (sửa đổi|bổ sung|bãi bỏ|thay …) … theo quy định tại …`.
   - `note_op(note)`: lấy thao tác **chỉ từ phần trước** `theo quy định tại`, thứ tự OPS như spike (`sửa đổi, bổ sung`→SUBSTITUTION trước `bổ sung`→INSERTION; `bãi bỏ`/`bỏ cụm từ`→REPEAL; `thay thế`/`thay cụm từ`→SUBSTITUTION); không khớp → `OTHER` (đếm, không chấm).
   - `note_source(note)`: địa chỉ nguồn sau `theo quy định tại` + số hiệu văn bản sửa đổi; lọc theo số hiệu của cặp.
   - `anchor_target(vbhn_body, note_no, level)`: lần xuất hiện đầu của `[n]` trong **thân** (trước khối chú thích), đi tuần tự theo dõi ngữ cảnh `Điều N[a-zđ]?.` / `N[a-zđ]?.` / `[a-zđ]\d*)` (nhãn có hậu tố `Điều 30a.`, `5a.`, `d1)`, `i1)` là **đơn vị riêng**, không gộp vào `Điều 30`/`5.`/`d)` — RT-02) → địa chỉ đầy đủ ở đúng cấp chú thích nêu ("Điểm này"/"Khoản này"/"Điều này"; "Cụm từ" → đơn vị nhỏ nhất chứa marker).
   - Bản ghi gold: `{pair_id, note_no, op, level, src_address, amending_doc, target_address, note_text[:200], approved: false, extractor_version}` (D13 — auto-gold, chưa duyệt).
3. **Địa chỉ chuẩn hoá** (định dạng chung với P2, ghi rõ ở đây để P2 khớp): chữ thường NFC; từ cấp gấp dấu ASCII (`diem`, `khoan`, `dieu`, `phu luc`); **chữ điểm giữ nguyên `đ`** (D12); số bỏ số 0 đầu; thứ tự nhỏ→lớn, cách nhau một dấu cách. Ví dụ: `diem đ khoan 2 dieu 1`, `khoan 5 dieu 4`, `phu luc 1`.
   - **Hậu tố (RT-02, D17)**: giá trị từng cấp theo grammar `điểm [a-zđ]\d*` (vd `d1`, `d2`, `i1`, `a1`), `khoản \d+[a-zđ]?` (vd `5a`), `Điều \d+[a-zđ]?` (vd `30a`); hậu tố viết thường, dính liền phần số/chữ, chỉ bỏ số 0 đầu của phần số (`05a`→`5a`). Ví dụ: `diem d1 khoan 2 dieu 3`, `khoan 5a dieu 18`, `dieu 30a`. `diem d1 …` ≠ `diem d …`, `khoan 5a …` ≠ `khoan 5 …`. Bằng chứng nhu cầu: red-team OBSERVED trên `nd50.html` có "Bổ sung điểm i1/d1, d2/d1/d1/a1 …", "Bổ sung khoản 5a vào sau khoản 5"; `vbhn02bxd.html` có "Bổ sung Điều 30a"; 7/9 INSERTION của gold spike trỏ đơn vị có hậu tố.
4. **Segment** (`segment.py`): `segment(text, doc_id) -> list[dict]` — node dạng kwargs của `StructuralNode` (`node_id`, `type="CLAUSE"`, `raw_label` "Điều 3"/"1."/"a)"/"Phụ lục 1", `parent_id`, `order`, `text`, `source_file_id=doc_id`, `page_range=[1]`), marker `[n]` đã gỡ khỏi text. Stdlib thuần (không import `app`) để P2 dựng cây đích từ VBHN.
   - Nhãn đầu dòng nhận cả dạng hậu tố (RT-02): `Điều \d+[a-zđ]?\.`, `\d+[a-zđ]?\.`, `[a-zđ]\d*\)` — "d1) [8] Hợp đồng theo chi phí cộng phí ; d2) [9] …" ra 2 node `d1)`, `d2)` là anh em của `d)`, không bị gộp vào `d)`.
   - `collapse_to_articles(nodes) -> list[dict]` (RT-05): dựng cây "chỉ có Điều" giống hình dạng cây AI1 thật (red-team đếm `raw_label` trong `ai-service/fixtures` + `docs/contracts/examples`: 73 "Điều N", 14 "Điều N.N", 0 nhãn "N."/"a)"): mỗi node `Điều N` giữ `node_id`, text = text của nó + text các node con nối theo thứ tự, mỗi con mở đầu dòng bằng `raw_label` gốc ("1. …", "d1) …") để resolver P2 đi đường `ANCESTOR` + kiểm nhãn trong text; node phụ lục giữ nguyên.
5. **Dataset** (`dataset.py`): `fetch_cached(url, cache_dir, offline)` (urllib, timeout, cache theo sha256(url) ở `data/contract_graph_cache/` — thư mục `/data/` đã bị ignore ở `.gitignore:16`; `offline=True` mà chưa cache → lỗi rõ ràng); `freeze(pairs, out_dir)` ghi `data/<pair_id>/{amending.txt, vbhn.txt, gold.jsonl}` + `data/manifest.json` (`pair_id`, `issuer`, `amending_doc`, `vbhn_doc`, URL, `fetched_at`, `raw_sha256`, sha256 từng file, đếm gold theo op); `verify_manifest(data_dir) -> list[str]`.
6. **Scorer** (`score.py`): `wilson(k, n, z=1.96)`; `score(gold, preds)` theo từng op: `n_gold`, `n_pred`, `src_found`, `op_lexical_agreement` (pred op == gold op; recall), `op_precision` (pred đúng op / pred op đó), `target_correct`/`target_accuracy` (đích chuẩn hoá == gold target, mẫu số = gold đã ghép được pred), `unmatched_predictions` (pred không ghép được gold — liệt kê để audit). Mỗi tỷ lệ ghi rõ `denominator`, `passed`, Wilson 95% (theo `docs/code-standards.md` §Testing). `render_markdown(report)`. Báo cáo ghi nhãn `ground_truth: "vbhn-note auto-gold (approved=false)"`.
   - **Tên chỉ số op (RT-09)**: gold lấy op từ động từ của chú thích qua bảng OPS (`vbhn_notes.py:12-13`) và predictor map động từ cùng quy ước, nên chỉ số này đo **đồng thuận từ vựng** (tìm ra câu thao tác + động từ khớp), không đo phân loại đúng nghĩa. Vì vậy tên là `op_lexical_agreement`, không phải "op accuracy"; báo cáo markdown ghi một dòng giải thích ngay dưới bảng.
   - **Ghép gold↔pred một-một (RT-13)**: trong mỗi cặp, bước 1 ghép theo khoá `(src_address, target_address)` khớp chính xác; bước 2 với phần còn lại, ghép theo `src_address` theo thứ tự xuất hiện (gold theo `note_no`, pred theo thứ tự predictor trả về). Mỗi gold/pred dùng tối đa một lần; pred thừa cùng src ⇒ `unmatched_predictions`; gold thừa ⇒ miss (vào mẫu số recall, không vào mẫu số `target_accuracy`). Không dùng dict khoá bằng src như `op_parser_eval.py:51-63` (chỉ giữ được 1 pred/src; `vbhn02bxd.html.gold.json` có 26 bản ghi nhưng 25 src).
   - **Tách theo cặp (RT-10)**: báo cáo JSON có `by_pair[<pair_id>]` cùng bộ chỉ số, để phase sau lấy mốc của riêng `nd50-2021` từ số OBSERVED thay vì mốc spike.
7. **Predictor baseline** (`baseline_predictor.py`): port `op_parser_eval.parse` (OP_HEAD, `op_of`, `target_of`, thân "Điều 1." dài nhất) ra `{src_address, op, target_text, head}`; tính `marker_hit` bằng `has_amend_marker`.
8. **CLI** (`run_eval.py`): `python -m evals.contract_graph.run_eval score --data evals/contract_graph/data --predictor baseline --out evals/contract_graph/reports/p1-baseline` (kiểm manifest trước, lệch → exit ≠ 0, không chấm); `python -m evals.contract_graph.run_eval fetch --sources evals/contract_graph/sources.json` (mạng, tuỳ chọn). `--predictor` nhận `baseline` hoặc đường dẫn `module:function` có chữ ký `predict(pair_dir: Path) -> list[dict]` (P3 dùng `evals.contract_graph.pipeline_predictor:predict`) — để phase sau không phải sửa `run_eval.py`.
9. **`sources.json`**: ≥10 cặp, ≥4 cơ quan ban hành (vd Quốc hội, Chính phủ, Bộ Xây dựng, Bộ Tài chính, NHNN); gồm cặp spike NĐ 50/2021 ↔ VBHN 02/VBHN-BXD; ≥1 cặp có REPEAL (gợi ý VBHN Luật Thương mại theo spike report `[ASSUMED khả dụng]`); mỗi cặp ghi `operative_article` nếu không phải Điều 1.

### Phi chức năng

- Harness lõi chỉ dùng stdlib (repo chạy `uv run --frozen`, không thêm dependency vào `ai-service/uv.lock`).
- Test chạy offline: chặn mạng trong test (`urllib.request.urlopen` bị monkeypatch ném lỗi) và chỉ dùng fixture.
- Output deterministic (`sort_keys`, thứ tự pair cố định) để diff báo cáo có nghĩa. Không lặp qua `set` khi sinh output (bài học RT-01: thứ tự `set` chuỗi đổi theo `PYTHONHASHSEED`); có test so bytes báo cáo giữa 2 hash seed.
- Dung lượng dữ liệu commit ≤ 5 MB (ghi số thật vào manifest). Chỉ commit text đã chuẩn hoá, không commit HTML/DOCX gốc (`.gitignore:5` chặn `*.docx`). VBQPPL không thuộc đối tượng bảo hộ quyền tác giả `[PRIOR: Luật SHTT Điều 15]`.

## Files — file inventory

| Hành động | Path | Cỡ ước tính | Ảnh hưởng test |
|---|---|---|---|
| Create | `evals/contract_graph/__init__.py` | <10 dòng | — |
| Create | `evals/contract_graph/README.md` | ~70 dòng | — (cách fetch/freeze/score, định dạng địa chỉ chuẩn kể cả hậu tố, nghĩa của `op_lexical_agreement`, hướng dẫn duyệt gold: người duyệt gán op theo `new_text` thật, **không** chép động từ của chú thích — RT-09) |
| Create | `evals/contract_graph/sources.json` | ~12 mục | test dataset contract |
| Create | `evals/contract_graph/normalize.py` | ~120 dòng | `test_cg_normalize.py` |
| Create | `evals/contract_graph/gold.py` | ~150 dòng | `test_cg_gold.py` |
| Create | `evals/contract_graph/segment.py` | ~90 dòng | `test_cg_segment.py` |
| Create | `evals/contract_graph/dataset.py` | ~110 dòng | `test_cg_dataset.py` |
| Create | `evals/contract_graph/score.py` | ~130 dòng | `test_cg_score.py` |
| Create | `evals/contract_graph/baseline_predictor.py` | ~80 dòng | `test_cg_baseline_eval.py` |
| Create | `evals/contract_graph/run_eval.py` | ~90 dòng | `test_cg_dataset.py`, `test_cg_baseline_eval.py` |
| Create | `evals/contract_graph/data/manifest.json` + `data/<pair_id>/{amending.txt,vbhn.txt,gold.jsonl}` | ≤5 MB | `test_cg_dataset.py::test_committed_dataset_*` |
| Create | `evals/contract_graph/reports/p1-baseline.{json,md}` | nhỏ | — (sản phẩm đo) |
| Create | `evals/contract_graph/tests/conftest.py` | ~15 dòng | chèn `<repo>/ai-service` vào `sys.path`; chặn mạng |
| Create | `evals/contract_graph/tests/fixtures/{mini_amending.html, mini_vbhn.html, mini_vbhn_escaped.html, mini_suffix_amending.html, mini_suffix_vbhn.html}` | mỗi file <4 KB | mọi test P1; cặp `mini_suffix_*` (RT-02) cũng dùng ở P2/P3 |
| Create | `evals/contract_graph/tests/test_cg_{normalize,gold,segment,dataset,score,baseline_eval}.py` | 6 file | — |

Số module code = 8 (`__init__`, `normalize`, `gold`, `segment`, `dataset`, `score`, `baseline_predictor`, `run_eval`), mỗi module một trách nhiệm; phần còn lại là test/dữ liệu. Tên test có tiền tố `test_cg_` để không trùng basename với `evals/tests/` khi pytest dùng import mode mặc định.

## Implementation Steps

1. **Xác nhận lại lệnh chạy**: lúc lập plan đã OBSERVED `uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m pytest` chạy được từ repo root (`evals/tests/test_clause_key_spike.py` 102 passed). Máy cook khác thì chạy lại `… python -m pytest --version`; hỏng → dùng `ai-service/.venv/Scripts/python.exe -m pytest` (quy ước `evals/docs/production-eval-setup.md:28`). Ghi lệnh thực dùng vào `verification-P1.json`.
2. Tạo `evals/contract_graph/` + `tests/conftest.py` (thêm `ai-service` vào `sys.path`; fixture autouse chặn `urllib.request.urlopen`).
3. Viết fixture mini: `mini_amending.html` có dòng mục lục "Điều 1. Sửa đổi…" ngắn + thân Điều 1 thật với 5 mục: (a) "1. Sửa đổi, bổ sung khoản 2 Điều 3 như sau:", (b) "2. Sửa đổi, bổ sung một số điểm của khoản 1 và khoản 2 Điều 4 như sau:" với con "a) Sửa đổi điểm c như sau:", "b) Bổ sung điểm đ vào sau điểm d như sau:", (c) "3. Bổ sung khoản 5 vào sau khoản 4 Điều 6 như sau:", (d) "4. Bãi bỏ khoản 3 Điều 7.". `mini_vbhn.html` có thân Điều 3/4/6/7 với marker `[1]…[5]` và khối chú thích, trong đó một chú thích có tên nghị định chứa "sửa đổi, bổ sung" sau "theo quy định tại", một chú thích trỏ văn bản khác (phải bị lọc). `mini_vbhn_escaped.html` gói một phần thân trong chuỗi JSON escape. Cặp `mini_suffix_*` (RT-02, tách riêng để không đổi số chính xác của `test_baseline_end_to_end_on_mini_fixture`): `mini_suffix_amending.html` Điều 1 có "1. Bổ sung điểm d1, d2 vào sau điểm d khoản 2 Điều 3 như sau:", "2. Bổ sung khoản 5a vào sau khoản 5 Điều 18 như sau:", "3. Bổ sung Điều 30a vào sau Điều 30 như sau:"; `mini_suffix_vbhn.html` có thân Điều 3 › `2.` › `d)`, `d1) [1] …`, `d2) [2] …`; Điều 18 › `5.`, `5a. [3] …`; `Điều 30.`, `Điều 30a. [4] …` cùng khối chú thích "Điểm này/Khoản này/Điều này được bổ sung theo quy định tại …".
4. Viết toàn bộ test RED (mục TDD) → chạy → thấy FAIL (ImportError/AssertionError).
5. Implement theo thứ tự `normalize` → `gold` → `segment` → `score` → `dataset` → `baseline_predictor` → `run_eval` cho tới khi xanh.
6. **Dữ liệu spike chỉ có ở worktree `contract-intelligence-develop`** (RT-15: `.harness/` bị loại qua `.git/info/exclude:12` của common dir, nên worktree mới cho `feature/ai2-contract-graph` không có `raw/`). Trước khi đổi worktree: chép `.harness/state/vbhn-probe/raw/{nd50.html, vbhn02bxd.html}` vào cache `data/contract_graph_cache/` theo đúng khoá sha256(url) của `fetch_cached`, hoặc cook ngay trong worktree này. Chuẩn hoá cặp spike vào `data/nd50-2021/`; chạy baseline → kiểm tái lập: `src_found = 26/26`, `op_lexical_agreement = 26/26` (OBSERVED spike). Lệch → sửa harness, không sửa kỳ vọng.
7. `run_eval fetch` ≥9 cặp còn lại vào cache, `freeze` vào `evals/contract_graph/data/`, sinh manifest. Thiếu cặp (mạng/trang) → phase **BLOCKED**, ghi số cặp thật; không hạ ngưỡng 10. Khi BLOCKED chỉ vì thiếu cặp (code + nd50 + fixture đã xanh), cook dừng và hỏi người dùng có cho P2 chạy tiếp trên `nd50-2021` + fixture không (RT-15); câu trả lời ghi vào `## Validation Log` của plan. Tiêu chí ≥10 cặp vẫn mở, plan không được đánh dấu xong cho tới khi đạt; báo cáo P2/P3 khi đó ghi rõ số cặp thật.
8. Chạy `run_eval score --predictor baseline` trên toàn bộ dữ liệu → commit `reports/p1-baseline.{json,md}` (lần đầu có số **độ đúng đích** OBSERVED).
9. Regression gate (cả hai suite) → commit phase.

## TDD

### Tests Before (RED — viết trước, chạy thấy FAIL)

- [ ] `test_cg_normalize.py::test_block_tags_become_paragraph_breaks` — khoá: `<p>`/`<br>`/`<tr>` ra xuống dòng, entity được unescape.
- [ ] `test_cg_normalize.py::test_json_escaped_html_payload_is_decoded` — khoá ca OBSERVED `<…` của `vbhn02bxd.html`.
- [ ] `test_cg_normalize.py::test_hard_wrapped_paragraph_is_joined` — dòng bị ngắt giữa câu được nối, dòng kết thúc bằng `:` thì không.
- [ ] `test_cg_normalize.py::test_operative_body_skips_toc_and_takes_longest_article_1` — khoá lỗi spike #2 (mục lục).
- [ ] `test_cg_normalize.py::test_operative_body_ignores_quoted_article_heading` — chuỗi inline "Điều 1. … 1. Sửa đổi Điều 2 như sau: “Điều 2. Nội dung mới …” 2. Bãi bỏ khoản 3 Điều 7. Điều 2. Hiệu lực …" ⇒ thân Điều 1 chứa cả mục 2 "Bãi bỏ khoản 3 Điều 7" (RT-14).
- [ ] `test_cg_normalize.py::test_docx_footnote_reference_becomes_inline_marker` — DOCX dựng bằng `zipfile` trong test (D15), marker `[n]` đúng chỗ.
- [ ] `test_cg_gold.py::test_op_is_read_before_theo_quy_dinh_tai` — "Điểm này được bổ sung theo quy định tại … Nghị định số 50/2021/NĐ-CP sửa đổi, bổ sung …" ⇒ `INSERTION` (khoá lỗi spike #1).
- [ ] `test_cg_gold.py::test_repeal_and_phrase_ops_map` — "được bãi bỏ"→REPEAL, "bỏ cụm từ"→REPEAL, "thay cụm từ"→SUBSTITUTION.
- [ ] `test_cg_gold.py::test_source_address_canonical_keeps_d_stroke` — "điểm đ khoản 2 Điều 1" ⇒ `diem đ khoan 2 dieu 1` ≠ `diem d khoan 2 dieu 1`.
- [ ] `test_cg_gold.py::test_anchor_target_from_marker_position` — "Điều 4 … 2. … c) [3] …" + "Điểm này" ⇒ `diem c khoan 2 dieu 4`.
- [ ] `test_cg_gold.py::test_suffix_canonical_forms` (RT-02) — "điểm d1 khoản 2 Điều 3" ⇒ `diem d1 khoan 2 dieu 3`; "khoản 05a Điều 18" ⇒ `khoan 5a dieu 18`; "Điều 30a" ⇒ `dieu 30a`; `diem d1 khoan 2 dieu 3` ≠ `diem d khoan 2 dieu 3`.
- [ ] `test_cg_gold.py::test_anchor_target_on_suffix_labels` (RT-02) — trên `mini_suffix_vbhn.html`: `[1]`→`diem d1 khoan 2 dieu 3`, `[2]`→`diem d2 khoan 2 dieu 3`, `[3]`→`khoan 5a dieu 18`, `[4]`→`dieu 30a`; không bản ghi nào ra `diem d …`/`khoan 5 …`/`dieu 30` (đúng ca "sai giống nhau" của red-team).
- [ ] `test_cg_gold.py::test_notes_citing_other_documents_are_filtered`.
- [ ] `test_cg_gold.py::test_unmatched_op_is_other_and_counted_not_scored`.
- [ ] `test_cg_gold.py::test_gold_records_are_not_approved` — mọi bản ghi `approved is False`.
- [ ] `test_cg_segment.py::test_article_clause_point_tree_has_parent_links`.
- [ ] `test_cg_segment.py::test_note_markers_are_removed_from_node_text`.
- [ ] `test_cg_segment.py::test_annex_heading_becomes_root_node`.
- [ ] `test_cg_segment.py::test_suffix_labels_become_own_nodes` (RT-02) — `d1)`, `d2)` là anh em của `d)` (cùng `parent_id` = node `2.`); `5a.` anh em của `5.`; `Điều 30a.` là gốc riêng; text của `d)` không chứa nội dung `d1)`.
- [ ] `test_cg_segment.py::test_collapse_to_articles_keeps_child_labels_at_line_start` (RT-05) — sau `collapse_to_articles`, chỉ còn node `Điều N` (+ phụ lục); text của `Điều 3` có các dòng bắt đầu bằng `2.`, `d)`, `d1)` đúng thứ tự; `node_id` của Điều không đổi.
- [ ] `test_cg_score.py::test_wilson_known_values` — `wilson(26, 26)` cận dưới ≈ 0,87 (khớp spike); `wilson(0, 0) == (0.0, 1.0)`.
- [ ] `test_cg_score.py::test_per_op_metrics_have_explicit_denominators`.
- [ ] `test_cg_score.py::test_prediction_without_gold_is_unmatched_and_lowers_precision`.
- [ ] `test_cg_score.py::test_target_accuracy_denominator_is_gold_with_prediction`.
- [ ] `test_cg_score.py::test_one_to_one_matching_with_shared_source` (RT-13) — (a) 2 gold cùng src khác target + 2 pred đúng target ⇒ 2 ghép, `target_correct = 2`; (b) 2 gold cùng src + 1 pred ⇒ 1 ghép + 1 miss; (c) 1 gold + 2 pred cùng src ⇒ 1 ghép + 1 `unmatched_prediction`; (d) 2 gold + 2 pred cùng src, target pred hoán vị ⇒ bước 1 ghép theo `(src, target)` nên vẫn 2/2.
- [ ] `test_cg_score.py::test_op_metric_is_named_lexical_agreement` (RT-09) — report có `op_lexical_agreement`, không có key `op_correct`/`op_accuracy`; markdown có dòng giải thích.
- [ ] `test_cg_score.py::test_report_has_by_pair_breakdown` (RT-10) — `by_pair[pid]` có đủ chỉ số; tổng `target_correct` qua các cặp == tổng toàn bộ.
- [ ] `test_cg_dataset.py::test_freeze_writes_sha256_for_every_file`.
- [ ] `test_cg_dataset.py::test_verify_manifest_detects_tampered_file`.
- [ ] `test_cg_dataset.py::test_offline_fetch_never_touches_network` — `urlopen` bị chặn; có cache → trả bytes; không cache → lỗi rõ.
- [ ] `test_cg_dataset.py::test_run_eval_refuses_when_manifest_mismatches` — exit ≠ 0, không ghi báo cáo.
- [ ] `test_cg_dataset.py::test_run_eval_loads_predictor_from_dotted_path` — `--predictor tests.fake:predict` được nạp, không cần sửa `run_eval.py`.
- [ ] `test_cg_baseline_eval.py::test_report_bytes_independent_of_hash_seed` — chạy `run_eval score --predictor baseline` trên fixture mini trong 2 subprocess với `PYTHONHASHSEED=1` và `=2` ⇒ bytes `*.json` và `*.md` bằng nhau (bài học RT-01).
- [ ] `test_cg_baseline_eval.py::test_baseline_end_to_end_on_mini_fixture` — số chính xác trên fixture: 5 gold (mục 1, 2a, 2b, 3, 4); `op_lexical_agreement` 5/5; mục cha 2 là `unmatched_prediction` (không có chú thích riêng); đích đúng 2/5 (mục 1, 4). Mục 3 sai vì regex spike bắt "khoản 4 Điều 6" thay vì địa chỉ mới `khoan 5 dieu 6`; 2a/2b thiếu cấp khoản — đúng hành vi spike, là baseline để P2/P3 vượt.

### Implement

Theo Implementation Steps 5–8.

### Tests After (hành vi mới trên dữ liệu thật)

- [ ] `test_cg_dataset.py::test_committed_dataset_manifest_verifies` — `verify_manifest("evals/contract_graph/data") == []`.
- [ ] `test_cg_dataset.py::test_committed_dataset_meets_coverage_contract` — ≥10 cặp, ≥4 `issuer` khác nhau, `n_gold[REPEAL] ≥ 1`.
- [ ] `test_cg_baseline_eval.py::test_baseline_reproduces_spike_on_nd50` — trên `nd50-2021`: `src_found == op_lexical_agreement == 26`.
- [ ] `test_cg_gold.py::test_nd50_gold_suffix_targets` (RT-02) — gold `nd50-2021`: số INSERTION có `target_address` mang hậu tố (`d1`, `d2`, `i1`, `a1`, `5a`) == 7 (đếm từ 6 câu red-team OBSERVED: i1; d1, d2; d1; d1; a1; 5a); hai chú thích của "d1) [8] … ; d2) [9] …" ra `diem d1 khoan 2 dieu 3` và `diem d2 khoan 2 dieu 3`. Lệch ⇒ in danh sách bản ghi để người duyệt xem, **không** tự sửa số kỳ vọng.

### Regression Gate

- Harness: từ repo root `uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m pytest -q -p no:cacheprovider evals/contract_graph/tests` (hoặc fallback ở bước 1) — PASS 100%.
- ai-service: từ `ai-service/` `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q -p no:cacheprovider --basetemp=<writable>` — chỉ đúng 13 lỗi môi trường đã nêu trong `plan.md` §Acceptance (P1 không sửa `ai-service/`, nên số passed phải giữ 1061).

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Op lấy nhầm từ tên văn bản sau "theo quy định tại" | `test_op_is_read_before_theo_quy_dinh_tai` |
| Critical | Mục lục bị coi là thân Điều 1 | `test_operative_body_skips_toc_and_takes_longest_article_1` |
| Critical | Manifest lệch mà vẫn chấm (số đo trên dữ liệu đã bị sửa) | `test_run_eval_refuses_when_manifest_mismatches`, `test_verify_manifest_detects_tampered_file` |
| Critical | Harness không tái lập số spike ⇒ thước đo sai | `test_baseline_reproduces_spike_on_nd50` |
| Critical | Đơn vị hậu tố (`d1)`, `5a.`, `Điều 30a`) bị gộp vào đơn vị gốc ⇒ gold và pred sai giống nhau, chấm "đúng" (RT-02) | `test_suffix_labels_become_own_nodes`, `test_anchor_target_on_suffix_labels`, `test_suffix_canonical_forms`, `test_nd50_gold_suffix_targets` |
| High | "điểm đ" gộp với "điểm d" | `test_source_address_canonical_keeps_d_stroke` |
| High | Nhiều gold cùng src bị ghép sai/bỏ sót (d1/d2, "Bãi bỏ khoản 3 và khoản 4") (RT-13) | `test_one_to_one_matching_with_shared_source` |
| High | Văn bản sửa đổi trích “Điều 2. …” trong ngoặc kép ⇒ thân Điều 1 bị cắt cụt (RT-14) | `test_operative_body_ignores_quoted_article_heading` |
| Medium | Báo cáo đổi bytes theo hash seed | `test_report_bytes_independent_of_hash_seed` |
| Medium | Chỉ số op bị đọc như độ đúng ngữ nghĩa (RT-09) | `test_op_metric_is_named_lexical_agreement` |
| Medium | Không có cây hình dạng AI1 để đo đường `ANCESTOR` (RT-05) | `test_collapse_to_articles_keeps_child_labels_at_line_start` |
| High | Đích gold lấy sai cấp/sai ngữ cảnh Điều | `test_anchor_target_from_marker_position` |
| High | Payload HTML escape trong JSON bị bỏ sót ⇒ mất chú thích | `test_json_escaped_html_payload_is_decoded` |
| High | Pred không có gold bị bỏ qua ⇒ precision ảo | `test_prediction_without_gold_is_unmatched_and_lowers_precision` |
| High | Test gọi mạng | `test_offline_fetch_never_touches_network` + conftest chặn `urlopen` |
| Medium | Chú thích trỏ văn bản sửa đổi khác (VBHN gộp nhiều lần sửa) | `test_notes_citing_other_documents_are_filtered` |
| Medium | DOCX footnote | `test_docx_footnote_reference_becomes_inline_marker` |
| Medium | Op lạ ("đình chỉ", "hết hiệu lực") | `test_unmatched_op_is_other_and_counted_not_scored` |
| Medium | Gold bị coi là đã duyệt | `test_gold_records_are_not_approved` |

## Success

- [ ] `evals/contract_graph/data/manifest.json` có ≥10 cặp, ≥4 cơ quan, `verify_manifest` trả `[]`; có ≥1 gold `REPEAL` (ghi số thật).
- [ ] Baseline tái lập spike trên `nd50-2021`: `src_found 26/26`, `op_lexical_agreement 26/26`.
- [ ] `evals/contract_graph/reports/p1-baseline.{json,md}` commit, mỗi op có `n`, `k`, tỷ lệ, Wilson 95% cho `op_lexical_agreement`, op precision, target accuracy (độ đúng đích lần đầu là OBSERVED), có `by_pair` (mốc `nd50-2021` cho P2/P3 — RT-10).
- [ ] Gold `nd50-2021` dùng địa chỉ hậu tố: 7 INSERTION trỏ `d1/d2/i1/a1/5a` (hoặc danh sách lệch đã được người duyệt xem — RT-02).
- [ ] Suite harness xanh offline; suite ai-service đúng 13 lỗi môi trường, 1061 passed.
- [ ] Dữ liệu commit ≤ 5 MB (số thật ghi trong manifest).

## Risks

| Rủi ro | L × I | Xử lý |
|---|---|---|
| Không lấy đủ 10 cặp / 4 cơ quan / REPEAL (mạng, trang đổi DOM) | Trung bình × Trung bình | Cache; nhiều nguồn (Q4 plan.md); thiếu thì BLOCKED có số đếm, không hạ ngưỡng |
| Trang dùng cấu trúc khác (escape JSON, footnote DOCX, `<sup>` link) | Cao × Trung bình | 3 đường chuẩn hoá có test; mỗi nguồn mới thêm 1 fixture nhỏ khi gặp dạng lạ |
| Gold sai do VBHN gộp nhiều lần sửa cùng một điều | Trung bình × Cao | Lọc theo số hiệu văn bản của cặp; `unmatched_predictions` để audit; `approved=false` |
| Marker `[n]` đặt ở dòng chỉ có nhãn ("c) [5]") hoặc trên tiêu đề Điều | Trung bình × Trung bình | `anchor_target` đi theo nhãn gần nhất **trước** marker; test cả hai vị trí |
| Định dạng địa chỉ chuẩn của P1 và P2 lệch nhau (hai bản cài đặt) | Trung bình × Cao | Định dạng ghi ở Requirements §3 (kể cả hậu tố); P2 có test parity (`test_cg_resolver_eval.py::test_gold_and_app_canonical_forms_agree`) chạy cả bảng chuỗi hậu tố |
| Gold và pred cùng bỏ hậu tố ⇒ sai tương quan, `target_accuracy` INSERTION bị thổi phồng (RT-02) | Cao (nếu không sửa) × Cao | Grammar hậu tố ở §2/§3/§4; fixture `mini_suffix_*`; test trên nd50 `[8]`/`[9]` |
| Cắt thân Điều 1 ở “Điều 2.” trong ngoặc kép ⇒ recall thấp đổ lỗi cho parser (RT-14) | Trung bình × Trung bình | Theo dõi độ sâu ngoặc kép; test riêng |
| Dữ liệu spike không có ở worktree cook (RT-15) | Trung bình × Thấp | Bước 6 chép `raw/` vào cache trước; thiếu cặp ⇒ người dùng quyết định cho P2 chạy tiếp hay không |
| Dung lượng dữ liệu lớn | Thấp × Thấp | Chỉ commit text; ngưỡng 5 MB |

## Rollback

`git revert <commit P1>`: chỉ xoá `evals/contract_graph/`; runtime không đổi. Cache ở `data/contract_graph_cache/` nằm ngoài git, xoá tay nếu cần.
