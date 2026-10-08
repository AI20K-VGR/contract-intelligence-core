---
phase: 2
title: "Address Resolver"
status: pending
plan: 261007-1735-ai2-contract-graph-op-first
created: 2026-10-07
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 2 — Address Resolver

## Overview

Module deterministic, thuần (không I/O, không flag), biến địa chỉ tiếng Việt thành node có thật trong cây cấu trúc của `DossierRecord`: `"điểm c khoản 1 Điều 3"`, `"khoản 5 vào sau khoản 4 Điều 4"`, `"điểm a"` tương đối dưới mục cha nêu nhiều khoản, `"Phụ lục 01"`, `"khoản này"`. Kết quả luôn là một trong `UNIQUE` / `AMBIGUOUS(candidates)` / `NOT_FOUND`; **không bao giờ tạo node**. Đây là chỗ khó thật của luồng 1: spike chỉ ra đích đủ cấp 16/26, 10 ca hụt đều do mục cha nêu nhiều khoản (OBSERVED, `plans/reports/spike-261007-1719-operation-parser-vbhn-report.md` §Kết quả). "Đủ cấp" không có nghĩa là "đúng": độ đúng đích của spike là `[ASSUMED]` (§Giới hạn 1), nên mốc so sánh của phase này là `target_correct` OBSERVED trong `p1-baseline.json`, không phải 16 (RT-10).

Phase này chưa nối vào `run_idp`; P3 gọi nó.

## Dependency map

- Phụ thuộc: P1 — dùng `evals/contract_graph/data/` + `segment.py` + `baseline_predictor.py` để đo resolver trên cây VBHN; định dạng địa chỉ chuẩn lấy từ P1 Requirements §3.
- Code tái dùng: `StructuralNode` (`ai-service/app/contracts/models.py:385-409`: `raw_label`, `parent_id`, `order`, `structure_level`, `source_file_id`); `DossierRecord.evidence_nodes()` (`ai-service/app/tools/store.py:56-59`); vai trò file `record.source_files[].role` (dùng như `ai-service/app/reasoning/relations.py:348` `source_roles`). Nhãn cấu trúc hiện có dạng `"Điều 5"`, `"Điều 5.3"`, `"Điều 1.1"`, `"(a)"`, `"Phụ lục 1"` (OBSERVED, đếm `raw_label` trong `ai-service/fixtures/`); `heading_level` nhận `khoản|điểm` chỉ khi nhãn ghi chữ (`ai-service/app/pipeline/structure.py:151-165`).
- Không import helper private của `relations.py` (`_resolve_reference`, `_annex_numbers`): resolver mới so nhãn cấu trúc, không quét text blob như `relations.py:567-592`, nên không trùng logic.
- Được dùng bởi: P3 (`builder.py`, `implicit.py`), P4 gián tiếp (địa chỉ chuẩn trong `ContractEdge.target_address`).

## Requirements

### Chức năng — `address.py`

1. `Address` (dataclass frozen): `dieu`, `khoan`, `diem` (chuỗi; **giữ `đ`** — D12; có thể mang hậu tố: `dieu="30a"`, `khoan="5a"`, `diem="d1"` — D17/RT-02), `phu_luc`, `khoan_options: tuple[str, ...]` (mục cha "khoản 1 và khoản 2 Điều 3"), `self_level: "dieu"|"khoan"|"diem"|None` ("khoản này"), `insert_after: Address|None` ("… vào sau khoản 4 …").
2. `parse_addresses(text) -> list[Address]` — một câu có thể nêu nhiều đích ("Bãi bỏ khoản 3 và khoản 4 Điều 7" ⇒ 2 địa chỉ, cùng `dieu`). Hỗ trợ:
   - đủ cấp: `điểm c khoản 1 Điều 3`, `khoản 2 Điều 5`, `Điều 7`, `khoản 2 của Điều 5`;
   - kiểu số hợp đồng: `Điều 5.3`, `khoản 5.3`, `5.3` đứng sau động từ ⇒ `dieu=5, khoan=3`;
   - chèn: `khoản 5 vào sau khoản 4 Điều 4` ⇒ `Address(dieu=4, khoan=5, insert_after=Address(dieu=4, khoan=4))`; `điểm đ vào sau điểm d khoản 2 Điều 3`; `bổ sung điểm đ vào khoản 2 Điều 3` (container, không có anchor);
   - **hậu tố (RT-02)**: `điểm d1`, `điểm i1`, `khoản 5a`, `Điều 30a`; danh sách trần sau một cấp: `điểm d1, d2 vào sau điểm d khoản 2` ⇒ 2 địa chỉ `diem d1 …`, `diem d2 …` cùng anchor `diem d khoan 2 …`. Regex mỗi cấp neo cuối bằng `(?![\wđ])` để "điểm d1" **không bao giờ** bị đọc thành "điểm d" và "khoản 5a" không thành "khoản 5";
   - phụ lục: `Phụ lục 01`, `Phụ lục số 2`, `Phụ lục II` (La Mã I–XX) ⇒ `phu_luc="1"|"2"|"2"`;
   - tự tham chiếu: `khoản này`, `điểm này`, `Điều này`;
   - tương đối: `điểm a` (chỉ một cấp, không có `dieu`).
   Có sẵn hoa/thường, NFC/NFD (chuẩn hoá NFC trước khi parse).
3. `parse_parent_context(text) -> Address|None` — cho câu mục cha: "Sửa đổi, bổ sung một số điểm của khoản 1 và khoản 2 Điều 3" ⇒ `Address(dieu=3, khoan_options=("1","2"))`; "Sửa đổi, bổ sung Điều 4 như sau" ⇒ `Address(dieu=4)`.
4. `inherit(child, parent) -> Address` — điền cấp thô hơn từ cha; cha có `khoan_options` mà con thiếu `khoan` ⇒ con nhận `khoan_options`; con đã đủ `dieu` thì giữ nguyên (không ghi đè).
5. `canonical(addr) -> str` — đúng định dạng P1 §3 (`diem đ khoan 2 dieu 1`, `khoan 5 dieu 4`, `phu luc 1`, `diem d1 khoan 2 dieu 3`, `khoan 5a dieu 18`, `dieu 30a`); `insert_after` không vào canonical (canonical là địa chỉ **mới**).

### Chức năng — `resolver.py`

6. `StructureIndex.build(nodes, roles: Mapping[str, str]) -> StructureIndex` — gán địa chỉ cho từng node từ nhãn + chuỗi cha:
   - `Điều N` / `ĐIỀU N.` / `Article N` ⇒ `dieu`; `Điều N.M` / `N.M` / `N.M.` ⇒ `dieu, khoan`; `N.` / `khoản N` dưới một `dieu` ⇒ `khoan`; `a)` / `(a)` / `điểm a` dưới một `khoan` ⇒ `diem`; `Phụ lục N` hoặc `structure_level == "ANNEX"` ⇒ gốc phần phụ lục. Mọi nhãn nhận dạng hậu tố (RT-02): `Điều 30a` ⇒ `dieu="30a"`, `5a.` ⇒ `khoan="5a"`, `d1)` / `(d1)` ⇒ `diem="d1"`.
   - Ưu tiên `parent_id`; thiếu cha thì dùng ngữ cảnh tuần tự trong cùng phần (sort theo `(source_file_id, order, node_id)`; `relations.py:344` chỉ sort `(order, node_id)` vì không cần tách theo file).
   - **Phần** (`part`): `annex:<node_id>` cho cây con dưới node phụ lục; `body:<source_file_id>` cho phần còn lại; file có `role="annex"` mà không có node phụ lục ⇒ `annex:file:<source_file_id>`.
   - Bỏ node `type == "FIELD"` và `"TABLE"` khỏi chỉ mục địa chỉ.
   - Trùng địa chỉ trong một phần (đánh số lặp) ⇒ giữ cả danh sách để resolve ra `AMBIGUOUS`.
7. `resolve(addr, *, parts, source_node_id=None, require_existing=True) -> Resolution` với `Resolution(status, node_id, candidates, method, canonical, residual)`; `method ∈ {EXACT, ANCESTOR, SELF, ORDER_INFERENCE}`:
   - `self_level` ⇒ đi lên tổ tiên của `source_node_id` tới cấp đó ⇒ `UNIQUE/SELF` hoặc `NOT_FOUND`.
   - `phu_luc` ⇒ chỉ xét phần phụ lục đúng số; có thêm `dieu…` thì tìm trong phần đó.
   - `khoan_options` ⇒ mở thành các địa chỉ ứng viên, lọc theo tồn tại: còn 1 ⇒ `UNIQUE/EXACT`; >1 ⇒ `AMBIGUOUS(candidates)`; 0 ⇒ `NOT_FOUND`.
   - Tra chính xác trong `parts`: 1 ⇒ `UNIQUE/EXACT`; >1 ⇒ `AMBIGUOUS`; 0 ⇒ lùi về tổ tiên gần nhất tồn tại duy nhất ⇒ `UNIQUE/ANCESTOR` + `residual` (vd `("diem c",)`). Với `require_existing=True` (mọi op trừ INSERTION), `ANCESTOR` chỉ được chấp nhận khi nhãn phần dư xuất hiện ở đầu dòng trong text của node tổ tiên (`c)`, `3.`); không thấy ⇒ `NOT_FOUND`.
   - `insert_after` (INSERTION) ⇒ anchor phải tồn tại (node hoặc nhãn trong text container) ⇒ trả container làm `node_id`; anchor không có ⇒ `NOT_FOUND`.
   - **Bất biến INSERTION (RT-02)**: `canonical(addr) == canonical(addr.insert_after)` ⇒ `NOT_FOUND` (`residual=("insert_equals_anchor",)`), không bao giờ `UNIQUE`. Ca thật: "Bổ sung khoản 5a vào sau khoản 5" mà parser mất hậu tố sẽ ra địa chỉ mới = anchor = `khoan 5 dieu 18`; trên hợp đồng gốc khoản 5 có thật nên nếu không chặn sẽ thành cạnh sai lặng lẽ. Với INSERTION, `node_id` luôn là container (Điều/khoản cha), **không bao giờ** là node anchor.
   - Thiếu hẳn `dieu` và `phu_luc` sau khi kế thừa ⇒ `NOT_FOUND` (không đoán).
8. `default_target_parts(index, source_node_id, addr) -> set[str]` — `phu_luc` ⇒ các phần phụ lục; nguồn nằm trong phần phụ lục ⇒ các phần `body:*` (file `role="body"`, nếu không có role thì mọi phần không chứa nguồn); nguồn trong thân ⇒ chính phần của nguồn (trừ cây con của nguồn).
9. `disambiguate_by_order(resolutions: Sequence[Resolution], index) -> list[Resolution]` — cho dãy con của một mục cha nhiều khoản (theo thứ tự trong văn bản sửa đổi): một ứng viên được **chốt** khi nó là lựa chọn duy nhất của mục đó trong **mọi** cách gán làm thứ tự node đích không giảm (`index.position(node_id)`); chốt được ⇒ `UNIQUE/ORDER_INFERENCE`; không chốt được ⇒ giữ `AMBIGUOUS`. Giả định "mục con liệt kê theo thứ tự văn bản gốc" là `[ASSUMED]` — đo riêng ở báo cáo P2.

### Phi chức năng

- Thuần, deterministic, O(số node) để build, O(1) trung bình để tra; không gọi mạng/DB/LLM.
- `__init__.py` của package không import gì nặng (giữ `app.pipeline` lazy — `ai-service/tests/test_import_boundaries.py:21-28`).
- Mọi `node_id` trả về ∈ tập node đầu vào (bất biến "không bịa node", có test).

## Files — file inventory

| Hành động | Path | Cỡ ước tính | Ảnh hưởng test |
|---|---|---|---|
| Create | `ai-service/app/pipeline/contract_graph/__init__.py` | docstring | `test_import_boundaries.py` vẫn xanh |
| Create | `ai-service/app/pipeline/contract_graph/address.py` | ~180 dòng | `test_contract_graph_address.py` |
| Create | `ai-service/app/pipeline/contract_graph/resolver.py` | ~230 dòng | `test_contract_graph_resolver.py` |
| Create | `ai-service/tests/test_contract_graph_address.py` | ~30 case (parametrize) | mới |
| Create | `ai-service/tests/test_contract_graph_resolver.py` | ~25 case | mới |
| Create | `evals/contract_graph/resolver_eval.py` | ~110 dòng | `test_cg_resolver_eval.py` |
| Create | `evals/contract_graph/tests/test_cg_resolver_eval.py` | ~5 test | mới |
| Create | `evals/contract_graph/reports/p2-resolver.{json,md}` | nhỏ | — (sản phẩm đo) |

## Implementation Steps

1. Viết test RED cho `address.py` (bảng parametrize: chuỗi vào → `canonical`, `insert_after`, `khoan_options`, `self_level`) → chạy, FAIL vì chưa có module.
2. Implement `address.py`: chuẩn hoá NFC + casefold có giữ dấu; regex theo cấp (`điểm [a-zđ]\d*`, `khoản \d+[a-zđ]?(\.\d+)?`, `Điều \d+[a-zđ]?(\.\d+)?`, `Phụ lục (số )?<số|La Mã>`), mỗi cấp neo cuối `(?![\wđ])`; tách danh sách bằng `và`/`,`, kể cả danh sách trần `d1, d2` sau một cấp; nhận diện `vào sau`/`vào`; chữ điểm giữ `đ` (D12, D17).
3. Viết test RED cho `resolver.py` với cây dựng tay bằng `StructuralNode` (thân: `Điều 3` › `1.` › `a)`,`b)`,`c)`; `2.` › `a)`,`c)`,`d)`,`d1)`; `Điều 4` › `4.`; `Điều 5.3`; `Điều 18` › `5.`; `Điều 30`, `Điều 30a`; phụ lục `Phụ lục 1` › `Điều 1`; một cây có `Điều 2` lặp; một node `Điều 6` có text chứa "c) …" nhưng không tách node điểm).
4. Implement `StructureIndex.build`, `resolve`, `default_target_parts`, `disambiguate_by_order`.
5. Viết `evals/contract_graph/resolver_eval.py`: mỗi cặp → `segment(vbhn.txt)` → `StructuralNode(**node)` → `StructureIndex`; lấy `head` (và head cha) từ `baseline_predictor` → `parse_parent_context`/`parse_addresses` + `inherit` → `resolve(require_existing = op != "INSERTION")` → `disambiguate_by_order` trên từng nhóm con → so `canonical` (INSERTION: địa chỉ mới; còn lại: địa chỉ node + `residual`) với `target_address` của gold. Ghi `unique/ambiguous/not_found`, độ đúng trong `UNIQUE` (precision resolver), độ phủ (`UNIQUE`/tổng), tách theo `method`, Wilson 95%. Ghép gold dùng cùng luật một-một của `score.py` (RT-13).
   - **Hai hình dạng cây (RT-05)**: `--tree-shape full|article-only|both` (mặc định `both`). `article-only` dựng cây đích bằng `segment.collapse_to_articles` (P1) — giống hình dạng cây AI1 thật, nên đo được đường `ANCESTOR` + kiểm nhãn trong text mà runtime sẽ đi. Báo cáo có hai cột cạnh nhau; cột `article-only` chỉ báo cáo (không gate), nhưng mọi `UNIQUE` sai ở cột này được liệt kê từng dòng để người duyệt xem.
6. Chạy `python -m evals.contract_graph.resolver_eval --data evals/contract_graph/data --out evals/contract_graph/reports/p2-resolver` → commit báo cáo.
7. Nếu `ORDER_INFERENCE` có ca sai trên `nd50-2021`: tắt nhánh suy theo thứ tự (trả `AMBIGUOUS`), ghi lý do vào báo cáo — **không** nới tiêu chí.
8. Regression gate → commit phase.

## TDD

### Tests Before (RED)

`ai-service/tests/test_contract_graph_address.py`
- [ ] `test_full_address_canonical` — `"điểm c khoản 1 Điều 3"` ⇒ `diem c khoan 1 dieu 3`; `"Khoản 2 của Điều 5"` ⇒ `khoan 2 dieu 5`; `"ĐIỀU 7"` ⇒ `dieu 7`.
- [ ] `test_d_stroke_point_letter_is_preserved` — `"điểm đ khoản 2 Điều 1"` ≠ `"điểm d khoản 2 Điều 1"` (D12).
- [ ] `test_contract_style_numbering` — `"Điều 5.3"`, `"khoản 5.3"` ⇒ `khoan 3 dieu 5`.
- [ ] `test_insert_after_keeps_new_address_and_anchor` — `"khoản 5 vào sau khoản 4 Điều 4"` ⇒ canonical `khoan 5 dieu 4`, anchor `khoan 4 dieu 4`.
- [ ] `test_insert_into_container_without_anchor` — `"bổ sung điểm đ vào khoản 2 Điều 3"` ⇒ `insert_after is None`, canonical `diem đ khoan 2 dieu 3`.
- [ ] `test_suffix_addresses_canonical` (RT-02, parametrize) — `"khoản 5a Điều 18"` ⇒ `khoan 5a dieu 18`; `"điểm d1 khoản 2 Điều 3"` ⇒ `diem d1 khoan 2 dieu 3`; `"điểm i1 khoản 1 Điều 4"`; `"điểm a1 khoản 4 Điều 4"`; `"Điều 30a"` ⇒ `dieu 30a`; với mọi ca, canonical **không** bằng bản bỏ hậu tố.
- [ ] `test_insert_suffix_point_list` (RT-02) — `"Bổ sung điểm d1, d2 vào sau điểm d khoản 2 Điều 3"` ⇒ đúng 2 địa chỉ `diem d1 khoan 2 dieu 3`, `diem d2 khoan 2 dieu 3`, cả hai `insert_after` canonical `diem d khoan 2 dieu 3`.
- [ ] `test_insert_suffix_clause_differs_from_anchor` (RT-02) — `"Bổ sung khoản 5a vào sau khoản 5 Điều 18"` ⇒ canonical `khoan 5a dieu 18`, anchor `khoan 5 dieu 18`, hai giá trị khác nhau.
- [ ] `test_annex_numbers_arabic_padded_and_roman` — `Phụ lục 01`, `Phụ lục số 2`, `Phụ lục II`.
- [ ] `test_self_reference` — `"khoản này"` ⇒ `self_level == "khoan"`.
- [ ] `test_list_of_targets_shares_article` — `"khoản 3 và khoản 4 Điều 7"` ⇒ 2 địa chỉ, cả hai `dieu=7`.
- [ ] `test_parent_context_with_multiple_clauses` — `"một số điểm của khoản 1 và khoản 2 Điều 3"` ⇒ `khoan_options == ("1","2")`, `dieu == "3"`.
- [ ] `test_inherit_fills_missing_levels_without_overwrite`.
- [ ] `test_nfd_input_parses_like_nfc`.
- [ ] `test_non_address_text_returns_empty` — `"sửa chữa hàng lỗi"` ⇒ `[]`.

`ai-service/tests/test_contract_graph_resolver.py`
- [ ] `test_exact_unique` — `điểm c khoản 1 Điều 3` ⇒ `UNIQUE/EXACT`, đúng node.
- [ ] `test_contract_style_label_indexed` — node `"Điều 5.3"` resolve được `khoản 3 Điều 5`.
- [ ] `test_duplicate_numbering_is_ambiguous` — hai `Điều 2` cùng phần ⇒ `AMBIGUOUS`, `candidates` đủ 2.
- [ ] `test_missing_target_not_found_never_invents` — `Điều 99` ⇒ `NOT_FOUND`, `node_id is None`.
- [ ] `test_ancestor_with_label_in_text` — `điểm c Điều 6` (điểm không tách node, text có "c)") ⇒ `UNIQUE/ANCESTOR`, `residual == ("diem c",)`.
- [ ] `test_ancestor_without_label_evidence_is_not_found` — `require_existing=True`, text không có "c)" ⇒ `NOT_FOUND`.
- [ ] `test_insertion_resolves_container_when_anchor_exists` — `khoản 5 vào sau khoản 4 Điều 4` ⇒ container `Điều 4`; anchor thiếu ⇒ `NOT_FOUND`.
- [ ] `test_insertion_suffix_never_resolves_to_existing_anchor` (RT-02) — cây có `Điều 18` › `5.`; `"Bổ sung khoản 5a vào sau khoản 5 Điều 18"` ⇒ `UNIQUE`, `canonical == "khoan 5a dieu 18"`, `node_id` = node `Điều 18` (container), `node_id` ≠ node `5.`.
- [ ] `test_insertion_new_equal_anchor_is_not_found` (RT-02) — `Address(dieu="18", khoan="5", insert_after=Address(dieu="18", khoan="5"))` (mô phỏng parser mất hậu tố) ⇒ `NOT_FOUND`, `node_id is None`.
- [ ] `test_suffix_labels_indexed` (RT-02) — node `d1)`, `Điều 30a` resolve `UNIQUE/EXACT`; `điểm d1 khoản 2 Điều 3` không trúng node `d)`; `Điều 30` không trúng `Điều 30a`.
- [ ] `test_multi_clause_parent_existence_filter` — điểm `b` chỉ có ở khoản 1 ⇒ `UNIQUE/EXACT`.
- [ ] `test_multi_clause_parent_both_exist_is_ambiguous`.
- [ ] `test_order_inference_forces_monotone_assignment` — con a) "điểm c", con b) "điểm a" dưới "khoản 1 và khoản 2" ⇒ a→`diem c khoan 1`, b→`diem a khoan 2`, `method == ORDER_INFERENCE`.
- [ ] `test_order_inference_keeps_ambiguous_when_not_forced`.
- [ ] `test_annex_address_limited_to_annex_parts` — `Điều 1 Phụ lục 1` không trúng `Điều 1` của thân.
- [ ] `test_default_parts_annex_source_targets_body` — nguồn ở phụ lục ⇒ chỉ phần `body:*`.
- [ ] `test_self_reference_walks_source_ancestors`.
- [ ] `test_relative_without_parent_is_not_found` — `"điểm a"` không có cha ⇒ `NOT_FOUND`.
- [ ] `test_resolved_node_ids_are_always_input_nodes` — chạy mọi case, mọi `node_id`/`candidates` ⊆ id đầu vào.

`evals/contract_graph/tests/test_cg_resolver_eval.py`
- [ ] `test_gold_and_app_canonical_forms_agree` — cùng bảng chuỗi (kể cả hậu tố `d1`, `5a`, `30a`, `đ`), `evals.contract_graph.gold` và `app.pipeline.contract_graph.address.canonical` ra cùng kết quả (chặn lệch định dạng giữa hai bản cài đặt).
- [ ] `test_resolver_eval_on_mini_fixture` — trên fixture P1: mục 1, 4 `EXACT` đúng; mục 3 (INSERTION) đúng địa chỉ mới `khoan 5 dieu 6`; 2a/2b được chốt bằng thứ tự hoặc `AMBIGUOUS`, **không** sai.
- [ ] `test_resolver_eval_on_suffix_fixture` (RT-02) — trên `mini_suffix_*`: 4 gold (`diem d1 …`, `diem d2 …`, `khoan 5a dieu 18`, `dieu 30a`) đều `UNIQUE` đúng; không pred nào ra `diem d …`/`khoan 5 …`/`dieu 30`.
- [ ] `test_report_has_method_breakdown_and_wilson`.
- [ ] `test_report_has_both_tree_shapes` (RT-05) — báo cáo có cột `full` và `article-only`; trên fixture mini, cột `article-only` có `method == ANCESTOR` > 0 và liệt kê từng `UNIQUE` sai (nếu có).

### Implement

Theo Implementation Steps 2, 4, 5.

### Tests After

- [ ] `test_cg_resolver_eval.py::test_nd50_no_wrong_unique_on_multi_clause_items` — trên `nd50-2021`, 10 mục cha nhiều khoản: mỗi mục là `UNIQUE` đúng hoặc `AMBIGUOUS`; số `UNIQUE` sai = 0.
- [ ] `test_cg_resolver_eval.py::test_nd50_correct_unique_not_below_p1_baseline` (RT-10) — số đích `UNIQUE` đúng (cây `full`) trên `nd50-2021` ≥ `by_pair["nd50-2021"].target_correct` đọc từ `evals/contract_graph/reports/p1-baseline.json` (số OBSERVED ở P1 bước 8, đã tính trên gold có hậu tố). Không dùng mốc 16: đó là số "đủ cấp" của spike, không phải số "đúng".

### Regression Gate

- ai-service (từ `ai-service/`): `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q -p no:cacheprovider --basetemp=<writable>` — chỉ 13 lỗi môi trường đã nêu; passed = 1061 + số test mới của P2.
- Harness (từ repo root): lệnh ở `plan.md` §Acceptance — PASS 100%.
- Focused nhanh khi lặp: `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q tests/test_contract_graph_address.py tests/test_contract_graph_resolver.py tests/test_import_boundaries.py`.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Bịa node / trả id không có trong cây | `test_resolved_node_ids_are_always_input_nodes`, `test_missing_target_not_found_never_invents` |
| Critical | Mục cha nhiều khoản bị resolve sai thành UNIQUE | `test_multi_clause_parent_both_exist_is_ambiguous`, `test_nd50_no_wrong_unique_on_multi_clause_items` |
| Critical | Địa chỉ phụ lục trúng nhầm thân (cùng số Điều) | `test_annex_address_limited_to_annex_parts` |
| High | "đ" ≡ "d" | `test_d_stroke_point_letter_is_preserved` |
| Critical | Địa chỉ hậu tố đọc thành địa chỉ gốc ("khoản 5a" → khoản 5 có thật) ⇒ cạnh sai lặng lẽ (RT-02) | `test_suffix_addresses_canonical`, `test_insertion_suffix_never_resolves_to_existing_anchor`, `test_insertion_new_equal_anchor_is_not_found`, `test_resolver_eval_on_suffix_fixture` |
| High | INSERTION dùng anchor làm đích (lỗi regex spike) | `test_insert_after_keeps_new_address_and_anchor`, `test_insertion_resolves_container_when_anchor_exists` |
| High | Chỉ đo trên cây lý tưởng, không đo đường `ANCESTOR` của cây AI1 (RT-05) | `test_report_has_both_tree_shapes` |
| Medium | Mốc so sánh là số "đủ cấp" thay vì số "đúng" (RT-10) | `test_nd50_correct_unique_not_below_p1_baseline` |
| High | Lùi về tổ tiên không có bằng chứng ⇒ đích sai | `test_ancestor_without_label_evidence_is_not_found` |
| High | Đánh số lặp | `test_duplicate_numbering_is_ambiguous` |
| High | Lệch định dạng canonical P1↔P2 | `test_gold_and_app_canonical_forms_agree` |
| Medium | Số kiểu hợp đồng `5.3` | `test_contract_style_numbering`, `test_contract_style_label_indexed` |
| Medium | La Mã, số 0 đầu ở phụ lục | `test_annex_numbers_arabic_padded_and_roman` |
| Medium | NFD từ OCR | `test_nfd_input_parses_like_nfc` |
| Medium | Tự tham chiếu | `test_self_reference`, `test_self_reference_walks_source_ancestors` |

## Success

- [ ] Mọi test P2 xanh; suite ai-service chỉ 13 lỗi môi trường; suite harness xanh.
- [ ] `evals/contract_graph/reports/p2-resolver.{json,md}` commit: `unique/ambiguous/not_found`, precision trong `UNIQUE`, độ phủ, tách theo `method`, Wilson 95%, trên toàn bộ dữ liệu P1 và riêng `nd50-2021`, hai cột `full` / `article-only` (RT-05).
- [ ] Trên `nd50-2021` (cây `full`): `UNIQUE` đúng ≥ `p1-baseline.by_pair["nd50-2021"].target_correct` (RT-10); `UNIQUE` sai trên 10 mục cha nhiều khoản = 0.
- [ ] Mọi INSERTION có hậu tố trên `mini_suffix_*` resolve đúng địa chỉ mới; bất biến `canonical(new) != canonical(anchor)` có test (RT-02).
- [ ] Không node nào được tạo (bất biến có test).

## Risks

| Rủi ro | L × I | Xử lý |
|---|---|---|
| Giả định thứ tự liệt kê sai ⇒ ORDER_INFERENCE chọn nhầm | Trung bình × Cao | `ORDER_INFERENCE` không bao giờ PASS (P3 review policy); đo riêng; sai trên nd50 ⇒ tắt nhánh (bước 7) |
| Cây AI1 thật không tách khoản/điểm (chỉ có node Điều) | Cao × Trung bình | `ANCESTOR` + `residual` có kiểm nhãn trong text; số `ANCESTOR` báo riêng; cột `article-only` trong `p2-resolver` đo đúng hình dạng này (RT-05) |
| Địa chỉ hậu tố (`5a`, `d1`, `30a`) bị cắt về địa chỉ gốc (RT-02) | Cao (nếu không sửa) × Cao | Grammar hậu tố + neo `(?![\wđ])`; bất biến INSERTION `canonical(new) != canonical(anchor)` ⇒ `NOT_FOUND`; fixture `mini_suffix_*` |
| Cây VBHN ≠ cây văn bản gốc (VBHN đã chứa phần bổ sung) | Chắc chắn × Trung bình | INSERTION so **địa chỉ mới**, không so node; ghi giới hạn trong báo cáo |
| Nhãn lạ (`Điều thứ ba`, `I.`, `Mục 2`) | Trung bình × Thấp | Không hỗ trợ đợt này ⇒ `NOT_FOUND` có issue ở P3; liệt kê trong báo cáo |
| Phụ lục nhúng chung file không được nhận diện là `ANNEX` | Trung bình × Trung bình | Dựa `structure_level == "ANNEX"` do AI2 dựng (`ai-service/app/pipeline/result_structure.py:63`, `structure.py:119`) + nhãn `Phụ lục N`; không đoán thêm |

## Rollback

`git revert <commit P2>`: xoá package `contract_graph/` (mới, chưa ai import trong runtime) + `resolver_eval.py` + báo cáo P2. Không ảnh hưởng `run_idp`.
