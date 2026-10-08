---
phase: 3
title: "Operation Parser"
status: pending
plan: 261007-1735-ai2-contract-graph-op-first
created: 2026-10-07
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 3 — Operation Parser

## Overview

Biến câu thao tác thành cạnh có kiểu: `(op, target_address, new_text, scope)` → resolve đích (P2) → `ContractEdge` có citation hai phía và `review_state` theo cổng PASS (mặc định `NEEDS_REVIEW`). Thêm nhánh thao tác ngầm qua `item_key` cho phụ lục không ghi địa chỉ. Nối vào `run_idp` (`ai-service/app/pipeline/idp.py:46`) sau trích fact/chunk, trước `CandidatePairer`, **sau flag** `AI2_CONTRACT_GRAPH_ENABLED`. Đo trên harness P1, báo `op_lexical_agreement` + target accuracy kèm Wilson CI. Không LLM, không nới cổng.

Phase này cũng **khoá output flag-tắt** bằng golden capture trước khi sửa `idp.py` (K2). Golden được capture và kiểm trong **subprocess với `PYTHONHASHSEED=0`** (D16/RT-01): đường cũ có phụ thuộc thứ tự `set` (`ai-service/app/pipeline/compare.py:67-71`), red-team OBSERVED case `SERVICE-BRD-08` ra 2 sha khác nhau giữa các seed.

## Dependency map

- Phụ thuộc P1: `run_eval.py` (`--predictor module:function`), `score.py`, dữ liệu `evals/contract_graph/data/`, báo cáo `p1-baseline.json` (mốc so sánh).
- Phụ thuộc P2: `address.parse_addresses`, `parse_parent_context`, `inherit`, `canonical`; `resolver.StructureIndex`, `resolve`, `default_target_parts`, `disambiguate_by_order`.
- Code tái dùng (đã đọc):
  - `has_amend_marker` (`ai-service/app/pipeline/relation_markers.py:42-46`) làm bộ lọc đầu cho nhóm INSERTION/SUBSTITUTION/REPEAL; `_AMEND_EXCLUDE` (`relation_markers.py:27`) đã loại "sửa chữa", "điều chỉnh theo CPI/chỉ số/giá thị trường/tỷ giá" — không chép lại regex.
  - `citation_for_node` (`ai-service/app/pipeline/outline.py:73-79`, trả `dict`) để dựng citation; `CitationResolver(record.pages, record.tables).verify` như `idp.py:422-428`. `[ASSUMED]`: các key của dict khớp field `Citation` (`ai-service/app/contracts/models.py:213-236`) — kiểm ở test đầu tiên của builder.
  - Mẫu issue `INSUFFICIENT_EVIDENCE` + id hash như `relations.py:596-607` (`_graph_issue`).
  - `Fact.item_key`, `source_role`, `normalized_value`, `citation.node_id` (`models.py:438-457`).
- Được dùng bởi P4: `ContractEdge`, `ContractGraphResult` (`app/contracts/contract_graph.py`), biến `graph` trong `run_idp`.

## Requirements

### Chức năng

1. **Model** — `ai-service/app/contracts/contract_graph.py` (D1):
   - `EdgeOp(str, Enum)`: `INSERTION, SUBSTITUTION, REPEAL, REJECTION, SCOPE_LIMIT`.
   - `EdgeMethod(str, Enum)`: `EXACT, ANCESTOR, SELF, ORDER_INFERENCE, ITEM_KEY`.
   - `ContractEdge(BaseModel, extra="forbid")`: `edge_id`, `op`, `source_node_id`, `target_node_id`, `target_address` (canonical), `anchor_node_id|None`, `method`, `support: RelationSupport` (`EXPLICIT_TEXT` cho tường minh, `HEURISTIC` cho ngầm), `standard: bool`, `implicit: bool`, `new_text|None` (≤2000 ký tự), `scope_text|None`, `source_citation: Citation`, `target_citation: Citation`, `review_state` (mặc định `NEEDS_REVIEW`), `source_snapshot_digest`.
   - `ContractGraphResult(BaseModel)`: `edges`, `issues: list[EvidenceIssue]`, `stats: dict[str, int | dict[str, int]]`.
   - `edge_id = "cedge:" + sha256(f"{digest}|{op}|{source}|{target}|{target_address}|{source_span}")[:24]` (D10).
2. **Tách đơn vị + parse câu** — `operations.py`:
   - `split_operation_units(text) -> list[Unit]` (`label`, `level` khoan/diem/None, `text`, `char_start`, `char_end`, `parent`), tách theo nhãn đầu dòng `\d+[a-zđ]?\.` / `[a-zđ]\d*\)` (nhận cả `5a.`, `d1)` — RT-02) và ranh giới câu `.;` khi không có nhãn. Bất biến: `text[char_start:char_end] == unit.text`.
   - `parse_operation(unit_text) -> Operation | None`; `Operation(op, target_text, addresses, new_text, scope_text, standard, template)`.
   - Mẫu (khớp không phân biệt hoa thường, NFC):

     | Mẫu | Op | `standard` |
     |---|---|---|
     | `^(Sửa đổi, bổ sung\|Sửa đổi\|Thay thế\|Thay cụm từ) <địa chỉ> (như sau)?:?` | SUBSTITUTION | True |
     | `^Bổ sung <địa chỉ mới> (vào sau <anchor>\|vào <container>) (như sau)?:?` | INSERTION | True |
     | `^(Bãi bỏ\|Bỏ cụm từ\|Hủy bỏ) … <địa chỉ>` | REPEAL | True |
     | `^<địa chỉ> không áp dụng (đối với\|cho) <phạm vi>` | SCOPE_LIMIT (`scope_text`) | True |
     | `<địa chỉ> (được\|bị) (sửa đổi\|bổ sung\|bãi bỏ\|thay thế)` (bị động) | theo động từ | False |
     | `<địa chỉ> (không còn\|hết) hiệu lực` | REPEAL | False |
     | `(sửa\|điều chỉnh\|thay đổi) <X> thành <Y>` **có** địa chỉ | SUBSTITUTION | False |
     | `^(Điều chỉnh\|Thay đổi) <địa chỉ> (của Hợp đồng)? như sau:?` (RT-08 — văn phong phụ lục hợp đồng) | SUBSTITUTION | False |
     | `^<địa chỉ> được thay bằng (nội dung sau)?:?` (RT-08) | SUBSTITUTION | False |
     | `có quyền từ chối … (theo\|tại\|quy định tại) <địa chỉ>` | REJECTION | False |

   - Địa chỉ trong mẫu dùng grammar P2 (kể cả hậu tố `5a`/`d1`/`30a` và danh sách trần `d1, d2` — RT-02). "Bổ sung điểm d1, d2 vào sau điểm d khoản 2 Điều 3 như sau:" ⇒ 1 `Operation` INSERTION với 2 `addresses`.
   - Thứ tự map động từ như gold P1 (`sửa đổi, bổ sung` trước `bổ sung`; `bỏ cụm từ`→REPEAL; `thay cụm từ`→SUBSTITUTION) — cùng quy ước `vbhn_notes.py` OPS để so được với gold.
   - **Loại trừ** (trả `None`): mọi câu mà `has_amend_marker` = False **và** không khớp mẫu SCOPE_LIMIT/REJECTION/hai mẫu RT-08 (red-team probe: "Thay đổi Điều 7 của Hợp đồng như sau:" và "Khoản 2 Điều 5 được thay bằng nội dung sau:" cho marker `False`; hai mẫu RT-08 neo đầu câu + bắt buộc có địa chỉ nên không mở cửa cho "thay đổi số lượng hàng hóa" — ca đó vẫn đi nhánh ngầm K4); "hoàn thành"; phủ định "`không (được|bị) (sửa đổi|bổ sung|bãi bỏ|thay thế)`" (red-team: "Điều 8 … không bị sửa đổi" cho marker `True`); REJECTION không có địa chỉ (đếm `rejection_without_address`); câu nằm trong phần **văn bản mới** sau `như sau:` của một đơn vị cha (kể cả trong ngoặc kép).
   - **Giới hạn nguồn REJECTION/SCOPE_LIMIT (RT-06)**: hai op này đi vòng qua `has_amend_marker`, nên chỉ được sinh cạnh khi đơn vị nguồn nằm trong phần `annex:*` (theo `StructureIndex`) **hoặc** có tổ tiên là một đơn vị thao tác (đơn vị chứa có mẫu ở bảng trên). Ngoài hai trường hợp đó `plan_edges` bỏ, đếm `scope_rejection_out_of_context` trong `stats`. Lý do: "Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7." và "Điều 5 không áp dụng đối với lô hàng 2." trong thân là quyền/phạm vi bình thường, nhưng ra BE thành `candidate_amendment` `severity="high"` (`backend/src/contract_intelligence/shared/ai/persistence.py:834,851`). `parse_operation` vẫn nhận diện (thuần text); việc lọc theo phần nằm ở `plan_edges`.
   - **Đơn vị chứa**: đơn vị có con mang mẫu thao tác ⇒ chỉ cung cấp `parse_parent_context` cho con, không tự sinh cạnh. Đơn vị không có con thao tác ⇒ tự sinh cạnh (vd "Sửa đổi, bổ sung Điều 4 như sau: …").
   - `new_text` = phần sau `như sau:` tới hết đơn vị (cắt 2000 ký tự).
3. **Thao tác ngầm** — `implicit.py` (K4):
   - Chỉ xét phần phụ lục (`annex:*` từ `StructureIndex`) có marker ngầm (`nội dung (điều chỉnh|sửa đổi|thay đổi)`, `thay đổi <danh từ>`, `điều chỉnh <danh từ>` **không** kèm địa chỉ) **và** chưa có cạnh tường minh nào xuất phát từ phần đó.
   - Fact phụ lục (`source_role="annex"`, node thuộc phần) có `item_key` ↔ fact thân cùng `item_key`: đúng 1 node thân và giá trị chuẩn hoá khác nhau ⇒ cạnh `SUBSTITUTION`, `implicit=True`, `method=ITEM_KEY`, `support=HEURISTIC`, `standard=False`, **luôn** `NEEDS_REVIEW`; giá trị bằng nhau ⇒ không cạnh (đếm `implicit_same_value`); ≥2 node thân ⇒ `TARGET_AMBIGUOUS`; 0 ⇒ `TARGET_NOT_FOUND`.
4. **Cổng PASS** — `review_policy.py` + `calibration.json` (K5, D13):
   - Hằng số `MIN_N = 60`, `MIN_WILSON_LOWER = 0.85` (không đọc từ env).
   - `auto_pass_enabled()` đọc `AI2_CONTRACT_GRAPH_AUTO_PASS` (mặc định tắt, tập truthy D2).
   - `calibration.json`: `{"schema": "contract-graph-calibration.v1", "ground_truth": "approved-only", "ops": {<op>: {"n": 0, "k": 0, "report": null}}}` — commit với mọi op `n=0`.
   - `review_state_for(edge, calibration, enabled) -> ReviewState`: `PASS` **chỉ khi** `enabled` ∧ `edge.standard` ∧ `method == EXACT` ∧ `not implicit` ∧ cả hai citation `validation_status == "VALID"` ∧ `n ≥ 60` ∧ `wilson_lower(k, n) ≥ 0.85`; ngược lại `NEEDS_REVIEW`.
5. **Builder** — `builder.py`:
   - `contract_graph_enabled()` đọc `AI2_CONTRACT_GRAPH_ENABLED` lúc gọi (D2).
   - `plan_edges(source_nodes, index) -> list[PlannedEdge]` — **thuần** (không citation, không review): đơn vị → op → (giới hạn nguồn REJECTION/SCOPE_LIMIT, RT-06) → địa chỉ (+kế thừa cha) → `default_target_parts` → `resolve(require_existing = op != INSERTION)` → `disambiguate_by_order` theo từng nhóm con của mục cha nhiều khoản; kèm `source_address` của đơn vị (để harness chấm). Dùng chung cho runtime và `pipeline_predictor` ⇒ cùng code; phân phối đầu vào khác nhau (cây VBHN vs cây AI1) được đo riêng bằng cột `article-only` (RT-05).
   - `build_contract_graph(record, facts, *, calibration=None, auto_pass=None) -> ContractGraphResult`: `StructureIndex.build(record.evidence_nodes(), roles)`; `plan_edges`; dựng 2 citation (nguồn: span câu thao tác ≤240 ký tự; đích: node đích) + verify; `review_state_for`; issue `TARGET_NOT_FOUND` (`INSUFFICIENT_EVIDENCE`) / `TARGET_AMBIGUOUS` (`NEEDS_REVIEW`) với `issue_id = "contract-graph:" + sha256(...)[:24]`; bỏ cạnh tự trỏ; dedupe theo `edge_id`; trần `MAX_EDGES = 500` ⇒ issue `CONTRACT_GRAPH_TRUNCATED` (D11); thêm cạnh ngầm từ `implicit.py`; `stats` (theo op, theo method, unresolved, ambiguous, implicit, excluded, truncated).
   - **Không** mutate `record`/`facts`; không gọi `runtime.checkpoint()`.
6. **Tích hợp `run_idp`** — `idp.py`:
   - Sau `relation_pairs = {...}` (`idp.py:273-277`), trước `pairer = CandidatePairer()` (`idp.py:278`): nếu `contract_graph_enabled()` ⇒ import **lười** builder trong nhánh `if`, gọi `build_contract_graph(record, facts)` trong `try/except Exception`; thành công ⇒ `relation_pairs |= {tuple(sorted((e.source_node_id, e.target_node_id))) for e in graph.edges}`; lỗi ⇒ giữ `EvidenceIssue(missing="CONTRACT_GRAPH_FAILED", review_state=NEEDS_REVIEW)`.
   - Ngay sau `issues.extend(context_issues)` (`idp.py:318`), trước `store_idx = index or IndexStore()` (`idp.py:319`): append `graph.issues` (hoặc issue lỗi) — D4 (RT-12). **Không** chèn sau `idp.py:292`: sau dòng đó còn issue `table-context:*` (`idp.py:293-304`) và `context_issues` (`idp.py:307-318`); id review `review:{code}:{index}` đánh theo vị trí trong `[*record.handoff_issues, *issues]` (`idp.py:495-500`) nên chèn giữa sẽ dịch id các issue phía sau.
   - Giới hạn đã biết (chỉ khi flag bật): cạnh mở khoá cặp thân↔phụ lục ⇒ pairer (`idp.py:279`) có thể không còn phát issue `BODY_ANNEX_RELATION` (`compare.py:196-221`, gọi ở `compare.py:64`) và có thêm candidate ⇒ id review phía sau dịch. Chấp nhận (cố ý theo D3), không khẳng định tiền tố id cho fixture có mở khoá cặp.
   - Flag tắt: không import, không gọi, không biến nào khác đổi giá trị.
7. **Golden flag-tắt** — `ai-service/scripts/capture_idp_golden.py` + `ai-service/fixtures/contract_graph/idp_flag_off_golden.json`:
   - Input: `fixtures.mock_record()` + `fixtures.envelope()` (`ai-service/fixtures/__init__.py:38,52`); mọi case pack `fixtures.catalog.all_cases()` (`ai-service/fixtures/catalog.py:1332`); request body+annex từ `docs/contracts/examples/ai1.snapshot.v1.{body,annex}.example.json` qua `adapt_be_ai2_processing_request` (mẫu dựng request: `ai-service/tests/test_processing_wire_contract.py:99-100, 378-380`).
   - uuid4 deterministic: patch `app.pipeline.idp.uuid4`, `app.pipeline.clause.uuid4`, `app.pipeline.compare.uuid4` (nguồn uuid trên đường `run_idp` — OBSERVED grep: `idp.py:56`, `clause.py:18,29`, `compare.py:452,511`) bằng bộ đếm reset mỗi case; `job_id` truyền tường minh; env flag bị xoá.
   - **Hash seed cố định (D16/RT-01)**: script có chế độ `--emit-shas` in JSON `{case_id: {job_result, wire, record}}` ra stdout; capture **và** mọi lần kiểm golden đều chạy script này trong subprocess `[sys.executable, "scripts/capture_idp_golden.py", "--emit-shas"]`, `cwd=ai-service/`, env có `PYTHONHASHSEED=0` (env khác giữ nguyên, flag bị xoá). Nguyên nhân: `compare.py:67` dựng `fee_keys` là `set` chuỗi, `:68` lặp set thành list, `:70-71` lấy `scopes[0]`/`scopes[1]` làm hai vế ⇒ thứ tự đổi theo hash seed (red-team OBSERVED: `SERVICE-BRD-08` ra `2b99d4e14780226f` ở seed 1, 6, 7 và `ca5b52137ea6e838` ở seed 2, 3, 4, 5; 65/66 case còn lại ổn định). **Không** sửa `compare.py` trong đợt này: sửa là đổi bytes đường cũ (K2) và file nằm ngoài phạm vi phase. Ghi nhận ở Q5 (plan.md).
   - Golden ghi kèm `{"hashseed": "0", "python": "<major.minor>"}` (venv hiện tại: Python 3.12.14, `ai-service/pyproject.toml:9` `requires-python = ">=3.11,<3.13"`). Thứ tự lặp `set` với seed cố định chỉ ổn định trong cùng một bản CPython minor `[PRIOR]`, nên test so `python` trước và báo lỗi rõ ràng (không skip) nếu khác.
   - `HASHSEED_SENSITIVE = {"SERVICE-BRD-08": "compare.py:67-71 set order"}` khai báo tường minh trong test. Chỉ được thêm mục khi có `file:line` nguyên nhân nằm trong code **cũ** (không phải code P3/P4) và người duyệt đồng ý; golden seed 0 vẫn kiểm **mọi** case kể cả case trong danh sách.
   - Lưu theo case: sha256 của JSON chuẩn (`sort_keys`) cho `job_result.model_dump(mode="json")`, `job_result_to_wire(...)` (case có request), `record_to_dict(record)`; lưu JSON đầy đủ cho 3 case đại diện (để in diff khi lệch).
8. **Predictor harness** — `evals/contract_graph/pipeline_predictor.py`: `predict(pair_dir)` dựng node nguồn từ `operative_body(amending.txt)` (vai trò `annex`) và cây đích từ `segment(vbhn.txt)` (vai trò `body`), gọi `plan_edges`, trả `{src_address, op, target_address}`. Thêm `predict_article_only(pair_dir)` — giống hệt nhưng cây đích qua `segment.collapse_to_articles` (RT-05); cả hai khớp chữ ký `predict(pair_dir: Path) -> list[dict]` của P1 nên không sửa `run_eval.py`.

### Phi chức năng

- Deterministic hoàn toàn (không uuid/time trong builder, không lặp `set` khi sinh output); O(số node × số câu).
- Flag tắt ⇒ output `run_idp` byte-identical (golden dưới `PYTHONHASHSEED=0`), không import module mới. Sau P4, `store.py` chỉ import `ContractEdge` dưới `TYPE_CHECKING` (P4 §3) nên câu này vẫn đúng.
- Không thông tin loại con nào chạm wire ở phase này (P4 mới nối ra wire; P3 chỉ thêm issue + `relation_pairs` khi flag bật).

## Files — file inventory

| Hành động | Path | Cỡ ước tính | Ảnh hưởng test |
|---|---|---|---|
| Create | `ai-service/app/contracts/contract_graph.py` | ~70 dòng | mọi test P3/P4 |
| Create | `ai-service/app/pipeline/contract_graph/operations.py` | ~200 dòng | `test_contract_graph_operations.py` |
| Create | `ai-service/app/pipeline/contract_graph/implicit.py` | ~110 dòng | `test_contract_graph_implicit.py` |
| Create | `ai-service/app/pipeline/contract_graph/review_policy.py` | ~70 dòng | `test_contract_graph_review_policy.py` |
| Create | `ai-service/app/pipeline/contract_graph/calibration.json` | ~15 dòng | `test_contract_graph_review_policy.py` |
| Create | `ai-service/app/pipeline/contract_graph/builder.py` | ~220 dòng | `test_contract_graph_idp_integration.py` |
| Modify | `ai-service/app/pipeline/idp.py` | +~25 dòng quanh `:273-278` (builder, `relation_pairs`) và `:318` (append issue) | golden + integration; mọi test gọi `run_idp` (22 file, OBSERVED grep) phải giữ xanh |
| Create | `ai-service/scripts/capture_idp_golden.py` | ~110 dòng (thêm `--emit-shas`) | sinh golden; được test gọi qua subprocess |
| Create | `ai-service/fixtures/contract_graph/idp_flag_off_golden.json` | sha256/case + 3 case đầy đủ + `hashseed`/`python` | `test_contract_graph_flag_off_regression.py` |
| Create | `ai-service/fixtures/contract_graph_records.py` | ~180 dòng (dossier thân + phụ lục có câu thao tác, theo mẫu `mock_record`; có câu RT-08 "Điều chỉnh …/Thay đổi … như sau:", "… được thay bằng …"; có REJECTION/SCOPE_LIMIT ở cả thân lẫn phụ lục — RT-06; có câu hậu tố "Bổ sung khoản 5a vào sau khoản 5" — RT-02; một dossier riêng có cạnh nhưng **không** mở khoá cặp fact nào — RT-12) | integration/implicit |
| Create | `ai-service/tests/test_contract_graph_{operations,implicit,review_policy,flag_off_regression,idp_integration}.py` | 5 file | mới |
| Create | `evals/contract_graph/pipeline_predictor.py` | ~60 dòng | `test_cg_pipeline_predictor.py` |
| Create | `evals/contract_graph/tests/test_cg_pipeline_predictor.py` | ~4 test | mới |
| Create | `evals/contract_graph/reports/p3-operation-parser.{json,md}` | nhỏ | — (sản phẩm đo, cây `full`) |
| Create | `evals/contract_graph/reports/p3-operation-parser-article-only.{json,md}` | nhỏ | — (sản phẩm đo, cây `article-only` — RT-05) |

Hơn 8 file: phase đã khoá ở 4 phase (K1) nên không tách; mỗi module một trách nhiệm (model / tách câu / ngầm / cổng / builder) và test 1:1.

## Implementation Steps

1. **Khoá flag-tắt trước** (chưa sửa `idp.py`): viết `capture_idp_golden.py` + `test_contract_graph_flag_off_regression.py`; từ `ai-service/` chạy `PYTHONHASHSEED=0 uv run --frozen --extra web --extra dev --extra kafka --extra openai python scripts/capture_idp_golden.py` → golden; test PASS. Kiểm chéo: `git worktree add <tmp> 70998af`, chạy capture ở đó **cũng với `PYTHONHASHSEED=0`** và cùng interpreter (cùng script, `PYTHONPATH` trỏ worktree) → sha256 từng case phải bằng golden. Chạy thêm `--emit-shas` với `PYTHONHASHSEED=1` và `=2`: tập case lệch so với seed 0 phải đúng bằng khoá của `HASHSEED_SENSITIVE` (OBSERVED red-team: chỉ `SERVICE-BRD-08`). Ghi sha256 file golden + tập case lệch vào `verification-P3.json`. Từ đây golden **không** được sửa (P4 cũng không).
2. Viết test RED: model + operations + implicit + review_policy + integration (flag bật) + harness predictor → chạy, FAIL.
3. Implement `app/contracts/contract_graph.py`.
4. Implement `operations.py` (tách đơn vị, mẫu, loại trừ, đơn vị chứa, văn bản mới).
5. Implement `review_policy.py` + `calibration.json` (mọi op `n=0`).
6. Implement `builder.py` (`plan_edges` thuần → `build_contract_graph`); test đầu tiên kiểm `Citation(**citation_for_node(...))` dựng được — nếu key lệch thì viết adapter nhỏ trong builder, không sửa `outline.py`.
7. Implement `implicit.py` và nối vào builder.
8. Sửa `idp.py` đúng 2 điểm (Requirements §6). Chạy golden test → phải còn xanh.
9. `pipeline_predictor.py`; chạy `python -m evals.contract_graph.run_eval score --data evals/contract_graph/data --predictor evals.contract_graph.pipeline_predictor:predict --out evals/contract_graph/reports/p3-operation-parser` và lần nữa với `--predictor evals.contract_graph.pipeline_predictor:predict_article_only --out evals/contract_graph/reports/p3-operation-parser-article-only` → commit cả hai báo cáo, có cột so với `p1-baseline`.
10. Regression gate cả hai suite → commit phase.

## TDD

### Tests Before (RED, hoặc PASS-khoá)

`ai-service/tests/test_contract_graph_flag_off_regression.py` (PASS ngay — khoá hành vi hiện tại; mọi so sánh golden chạy qua subprocess `--emit-shas`, kết quả seed 0 cache bằng fixture `scope="module"` để chỉ chạy một lần)
- [ ] `test_run_idp_is_deterministic_under_patched_uuid` — trong cùng process, mỗi case chạy 2 lần cho cùng sha256. Chỉ chứng minh patch uuid đủ; **không** chứng minh độc lập hash seed (cùng process = cùng seed) — việc đó thuộc test cross-seed bên dưới.
- [ ] `test_flag_unset_matches_golden` — subprocess `PYTHONHASHSEED=0`: mọi case (kể cả `HASHSEED_SENSITIVE`) sha256 `job_result`/`wire`/`record` == golden.
- [ ] `test_flag_explicit_false_values_match_golden` — subprocess `PYTHONHASHSEED=0` với `AI2_CONTRACT_GRAPH_ENABLED` ∈ {`""`, `"0"`, `"false"`, `"off"`} ⇒ như golden.
- [ ] `test_golden_equal_across_hash_seeds_except_declared` (RT-01) — subprocess `PYTHONHASHSEED=1` và `=2`: mọi case **ngoài** `HASHSEED_SENSITIVE` có sha bằng seed 0; tập case có sha khác nhau giữa {0, 1, 2} **đúng bằng** khoá của `HASHSEED_SENSITIVE` (case mới lệch ⇒ đỏ: có phụ thuộc thứ tự set mới; case trong danh sách hết lệch ⇒ đỏ: gỡ khỏi danh sách). Seed 1 và 2 chọn vì red-team OBSERVED `SERVICE-BRD-08` khác sha giữa hai seed này.
- [ ] `test_golden_records_interpreter_and_seed` — golden có `hashseed == "0"`; `python` == `f"{sys.version_info.major}.{sys.version_info.minor}"`, khác ⇒ `pytest.fail` kèm hướng dẫn (không skip).
- [ ] `test_flag_off_does_not_import_builder` — subprocess sạch chạy `run_idp` với flag tắt ⇒ `"app.pipeline.contract_graph.builder" not in sys.modules`.

`ai-service/tests/test_contract_graph_operations.py` (RED)
- [ ] `test_operation_templates` (parametrize, bảng Requirements §2): `"Sửa đổi, bổ sung khoản 2 Điều 3 như sau:"`→SUBSTITUTION/std; `"Bổ sung khoản 5 vào sau khoản 4 Điều 4 như sau:"`→INSERTION/std/`khoan 5 dieu 4`; `"Bãi bỏ khoản 3 và khoản 4 Điều 7."`→REPEAL/2 đích; `"Thay cụm từ \"A\" bằng cụm từ \"B\" tại khoản 2 Điều 5"`→SUBSTITUTION; `"Bỏ cụm từ \"X\" tại điểm a khoản 1 Điều 2"`→REPEAL; `"Điều 4 được sửa đổi như sau:"`→SUBSTITUTION/không std; `"Khoản 2 Điều 8 không còn hiệu lực."`→REPEAL/không std; `"Điều 5 không áp dụng đối với lô hàng 2."`→SCOPE_LIMIT/`scope_text="lô hàng 2"`; `"Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7."`→REJECTION (mức parser thuần text; lọc theo phần ở `plan_edges` — RT-06).
- [ ] `test_contract_annex_verbs` (RT-08) — `"Điều chỉnh khoản 2 Điều 5 như sau:"`, `"Thay đổi Điều 7 của Hợp đồng như sau:"`, `"Khoản 2 Điều 5 được thay bằng nội dung sau:"` ⇒ SUBSTITUTION, `standard=False`, đích lần lượt `khoan 2 dieu 5`, `dieu 7`, `khoan 2 dieu 5`.
- [ ] `test_suffix_operation_targets` (RT-02) — `"Bổ sung điểm d1, d2 vào sau điểm d khoản 2 Điều 3 như sau:"` ⇒ INSERTION, 2 địa chỉ `diem d1 khoan 2 dieu 3`, `diem d2 khoan 2 dieu 3`; `"Bổ sung khoản 5a vào sau khoản 5 Điều 18 như sau:"` ⇒ INSERTION `khoan 5a dieu 18` (≠ `khoan 5 dieu 18`); `"Bổ sung Điều 30a vào sau Điều 30"` ⇒ `dieu 30a`; `split_operation_units` tách `5a.`/`d1)` thành đơn vị riêng.
- [ ] `test_exclusions_return_none` — "Bên B có trách nhiệm sửa chữa hàng lỗi theo Điều 7.", "Giá được điều chỉnh theo chỉ số CPI tại Điều 4.", "Sau khi hoàn thành nghiệm thu theo Điều 6", "Bên A có quyền từ chối nhận hàng." (REJECTION không địa chỉ), "Điều 8 của Hợp đồng không bị sửa đổi." (phủ định — rủi ro tồn dư red-team), "Thay đổi số lượng hàng hóa theo bảng dưới đây." (không địa chỉ ⇒ không vào mẫu RT-08, để nhánh ngầm xử lý).
- [ ] `test_research_probe_sentences` — đúng 6 câu probe ở `plans/reports/contract-graph-research-261007.md` §2.2 cho kết quả đúng ("Bổ sung khoản 3 vào Điều 5"→INSERTION, "Bãi bỏ Điều 9"→REPEAL, "không áp dụng"→SCOPE_LIMIT; 3 câu FP → None).
- [ ] `test_units_offsets_roundtrip` — `text[u.char_start:u.char_end] == u.text` cho mọi đơn vị.
- [ ] `test_container_unit_emits_no_edge_and_passes_parent_context` — "Sửa đổi, bổ sung một số điểm của khoản 1 và khoản 2 Điều 3 như sau:" + con a)/b).
- [ ] `test_new_text_after_nhu_sau_is_not_parsed_as_operation` — văn bản mới trong ngoặc kép chứa "bãi bỏ"/"sửa đổi" ⇒ không sinh op.
- [ ] `test_d_stroke_target_preserved` — "Bổ sung điểm đ vào sau điểm d khoản 2 Điều 3".

`ai-service/tests/test_contract_graph_implicit.py` (RED)
- [ ] `test_implicit_substitution_by_item_key_is_always_needs_review` — kể cả khi `auto_pass=True` và calibration n=60/k=60.
- [ ] `test_implicit_same_value_emits_no_edge`.
- [ ] `test_implicit_multiple_body_nodes_is_ambiguous_issue`.
- [ ] `test_implicit_no_body_match_is_not_found_issue`.
- [ ] `test_implicit_skipped_when_annex_part_has_explicit_edges`.
- [ ] `test_annex_without_implicit_marker_emits_nothing`.

`ai-service/tests/test_contract_graph_review_policy.py` (RED)
- [ ] `test_default_env_is_needs_review`.
- [ ] `test_committed_calibration_blocks_pass` — env bật + `calibration.json` thật ⇒ `NEEDS_REVIEW` cho mọi op.
- [ ] `test_pass_only_when_every_condition_holds` — calibration tiêm n=60, k=60 + std + EXACT + 2 citation VALID ⇒ `PASS`.
- [ ] `test_each_missing_condition_blocks_pass` (parametrize: n=59; n=60,k=54 ⇒ cận dưới ≈0,80; không std; ANCESTOR; ORDER_INFERENCE; SELF; ITEM_KEY; implicit; citation nguồn INVALID; citation đích UNVERIFIED).
- [ ] `test_thresholds_are_constants` — `MIN_N == 60`, `MIN_WILSON_LOWER == 0.85`.
- [ ] `test_calibration_entries_with_n_reference_existing_report` — op nào `n>0` phải trỏ file báo cáo tồn tại.

`ai-service/tests/test_contract_graph_idp_integration.py` (RED, dùng `fixtures/contract_graph_records.py`)
- [ ] `test_flag_on_emits_typed_edges_with_two_sided_citations` — SUBSTITUTION (điểm c khoản 1 Điều 3), INSERTION (khoản 4 vào sau khoản 3 Điều 7), SCOPE_LIMIT (Điều 5; câu nằm ở phụ lục theo RT-06).
- [ ] `test_flag_on_missing_target_is_insufficient_evidence_issue` — "Bãi bỏ Điều 9." (thân không có Điều 9) ⇒ issue `TARGET_NOT_FOUND`, không cạnh.
- [ ] `test_flag_on_excluded_sentences_emit_nothing`.
- [ ] `test_flag_on_every_edge_needs_review_by_default`.
- [ ] `test_flag_on_relation_pairs_unlock_cross_file_candidate` — fact thân (Điều 5, `don_gia`) + fact phụ lục khác file: flag tắt không có candidate cặp này (`compare.py:188-193`), flag bật có.
- [ ] `test_flag_on_keeps_existing_review_item_ids` (viết lại theo RT-12) — **chỉ** trên dossier riêng có cạnh nhưng không mở khoá cặp fact nào (khẳng định trước: tập `candidates` và issue `BODY_ANNEX_RELATION` giống hệt giữa flag tắt/bật): danh sách `review_item_id` của lần flag tắt là tiền tố đúng thứ tự của lần flag bật, và mọi id mới nằm sau tiền tố (D4: append sau `idp.py:318`). Không dùng chung fixture với test mở khoá ở trên.
- [ ] `test_rejection_scope_limit_require_annex_or_operation_context` (RT-06) — "Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7." và "Điều 5 không áp dụng đối với lô hàng 2." trong **thân**, không có đơn vị thao tác cha ⇒ không cạnh, `stats["scope_rejection_out_of_context"] == 2`; cùng hai câu trong phụ lục ⇒ có cạnh REJECTION/SCOPE_LIMIT.
- [ ] `test_flag_on_contract_annex_verbs_emit_substitution` (RT-08) — phụ lục của `contract_graph_records.py` có ba câu RT-08 ⇒ 3 cạnh SUBSTITUTION `standard=False`, `NEEDS_REVIEW`.
- [ ] `test_flag_on_suffix_insertion_targets_new_address` (RT-02) — "Bổ sung khoản 5a vào sau khoản 5 Điều 18" trên thân có khoản 5 ⇒ cạnh INSERTION `target_address == "khoan 5a dieu 18"`, `target_node_id` = node Điều 18, **không** = node khoản 5.
- [ ] `test_builder_failure_becomes_issue_not_job_failure` — patch builder ném lỗi ⇒ `SUCCEEDED` + issue `CONTRACT_GRAPH_FAILED`.
- [ ] `test_builder_does_not_mutate_record_or_facts`.
- [ ] `test_edge_cap_truncates_with_issue` — `MAX_EDGES=1` ⇒ 1 cạnh + `CONTRACT_GRAPH_TRUNCATED`.
- [ ] `test_flag_truthy_values` — `"1"`,`"true"`,`"yes"`,`"on"` bật; còn lại tắt.
- [ ] `test_citation_for_node_maps_to_citation_model` — khoá giả định `[ASSUMED]` ở Dependency map.

`evals/contract_graph/tests/test_cg_pipeline_predictor.py` (RED)
- [ ] `test_pipeline_predictor_on_mini_fixture` — `op_lexical_agreement` 5/5; đích: không có `UNIQUE` sai (mục 3 ra `khoan 5 dieu 6`); mục cha 2 **không** còn là `unmatched_prediction` (đơn vị chứa không sinh cạnh).
- [ ] `test_pipeline_predictor_on_suffix_fixture` (RT-02) — trên `mini_suffix_*`: 4/4 đích đúng (`diem d1 …`, `diem d2 …`, `khoan 5a dieu 18`, `dieu 30a`).
- [ ] `test_pipeline_predictor_article_only_mode` (RT-05) — `predict_article_only` trên fixture mini chạy được, mọi `target_address` không rỗng hoặc ghi rõ unresolved; không ném lỗi khi cây chỉ có node Điều.
- [ ] `test_wilson_parity_app_vs_harness` — `review_policy.wilson_lower(k, n) == score.wilson(k, n)[0]` trên lưới k ≤ n ≤ 100.

### Implement

Theo Implementation Steps 3–9.

### Tests After

- [ ] `test_cg_pipeline_predictor.py::test_p3_report_not_worse_than_baseline` — đọc `reports/p1-baseline.json` và `p3-operation-parser.json`: với mỗi op có `n_gold > 0`, `op_lexical_agreement_p3 ≥ op_lexical_agreement_p1` và `target_correct_p3 ≥ target_correct_p1`; **thêm điều kiện precision (RT-09)**: với mỗi op, số pred không ghép được gold (`n_pred − matched`) của P3 ≤ của P1, và tổng `len(unmatched_predictions)` P3 ≤ P1 (parser sinh thêm cạnh rác thì đỏ, dù recall không đổi).
- [ ] `test_cg_pipeline_predictor.py::test_p3_nd50_no_wrong_unique_target` — trên `nd50-2021`, số đích `UNIQUE` sai = 0.
- [ ] Golden test chạy lại sau bước 8 vẫn xanh, sha256 file golden không đổi so với bước 1.

### Regression Gate

- ai-service (từ `ai-service/`): `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q -p no:cacheprovider --basetemp=<writable>` — chỉ 13 lỗi môi trường đã nêu; mọi test gọi `run_idp` (vd `tests/test_processing_wire_contract.py`, `tests/test_a8_env_flags.py`, `tests/test_contract_context.py`) xanh.
- Harness (từ repo root): lệnh ở `plan.md` §Acceptance.
- Focused khi lặp: `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q tests/test_contract_graph_*.py tests/test_relation_markers.py tests/test_processing_wire_contract.py`.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Flag tắt mà output đổi (byte) | `test_flag_unset_matches_golden`, `test_flag_explicit_false_values_match_golden`, `test_flag_off_does_not_import_builder` |
| Critical | Golden flaky giữa các process do thứ tự `set` theo hash seed (RT-01) | `test_golden_equal_across_hash_seeds_except_declared`, `test_golden_records_interpreter_and_seed` (capture + kiểm đều `PYTHONHASHSEED=0`) |
| Critical | "Bổ sung khoản 5a vào sau khoản 5" thành cạnh trỏ khoản 5 có thật (RT-02) | `test_suffix_operation_targets`, `test_flag_on_suffix_insertion_targets_new_address`, `test_pipeline_predictor_on_suffix_fixture` |
| Critical | Cạnh PASS khi chưa đủ calibration / thiếu điều kiện | `test_committed_calibration_blocks_pass`, `test_each_missing_condition_blocks_pass` |
| Critical | Ngầm (implicit) thành PASS | `test_implicit_substitution_by_item_key_is_always_needs_review` |
| Critical | Lỗi builder làm FAILED cả job | `test_builder_failure_becomes_issue_not_job_failure` |
| Critical | Đích không có ⇒ bịa cạnh | `test_flag_on_missing_target_is_insufficient_evidence_issue` |
| High | FP "sửa chữa"/"điều chỉnh theo CPI"/"hoàn thành" | `test_exclusions_return_none`, `test_research_probe_sentences` |
| High | Văn bản mới sau "như sau:" bị parse thành thao tác | `test_new_text_after_nhu_sau_is_not_parsed_as_operation` |
| High | Mục cha sinh cạnh trùng với con | `test_container_unit_emits_no_edge_and_passes_parent_context` |
| High | `relation_pairs` không mở cặp khác file như thiết kế | `test_flag_on_relation_pairs_unlock_cross_file_candidate` |
| High | Id review item cũ bị đánh số lại khi flag bật (fixture không mở khoá cặp — RT-12) | `test_flag_on_keeps_existing_review_item_ids` |
| High | Số đo harness không phản ánh runtime (code chung, nhưng cây khác hình dạng — RT-05) | `plan_edges` dùng chung; `test_pipeline_predictor_on_mini_fixture`, `test_pipeline_predictor_article_only_mode` + báo cáo `article-only` |
| High | Quyền/phạm vi bình thường trong thân thành cạnh REJECTION/SCOPE_LIMIT ⇒ BE `candidate_amendment` high (RT-06) | `test_rejection_scope_limit_require_annex_or_operation_context` |
| High | Bỏ sót động từ phụ lục hợp đồng "Điều chỉnh/Thay đổi … như sau", "được thay bằng" (RT-08) | `test_contract_annex_verbs`, `test_flag_on_contract_annex_verbs_emit_substitution` |
| High | Parser sinh thêm cạnh rác mà cổng không-kém-baseline vẫn xanh (RT-09) | `test_p3_report_not_worse_than_baseline` (điều kiện precision) |
| Medium | Phủ định "không bị sửa đổi" thành cạnh | `test_exclusions_return_none` |
| Medium | Ngưỡng bị đổi lén | `test_thresholds_are_constants`, `test_wilson_parity_app_vs_harness` |
| Medium | Bùng nổ cạnh | `test_edge_cap_truncates_with_issue` |
| Medium | Citation dict ↔ model lệch | `test_citation_for_node_maps_to_citation_model` |
| Medium | Builder sửa record/facts | `test_builder_does_not_mutate_record_or_facts` |

## Success

- [ ] Golden flag-tắt (`PYTHONHASHSEED=0`): sha256 khớp kiểm chéo worktree `70998af` (bước 1, cùng seed + interpreter) và vẫn khớp sau khi sửa `idp.py`; sha256 file golden + tập case nhạy seed (== `HASHSEED_SENSITIVE`) ghi trong `verification-P3.json`.
- [ ] Mọi test P3 xanh; suite ai-service chỉ 13 lỗi môi trường; suite harness xanh.
- [ ] `evals/contract_graph/reports/p3-operation-parser.{json,md}` và `p3-operation-parser-article-only.{json,md}` commit: mỗi op `n`, `k`, tỷ lệ, Wilson 95% cho `op_lexical_agreement`/op precision và target accuracy; cột so với `p1-baseline`; không op nào (n>0) kém baseline về recall **và** precision (RT-09); `UNIQUE` sai trên nd50 (cây `full`) = 0.
- [ ] Flag bật trên fixture: cạnh có đủ 2 citation; 100% `NEEDS_REVIEW` với cấu hình mặc định.
- [ ] `MIN_N = 60`, `MIN_WILSON_LOWER = 0.85` không đổi; `calibration.json` mọi op `n=0`.

## Risks

| Rủi ro | L × I | Xử lý |
|---|---|---|
| Flag tắt nhưng bytes đổi (import, thứ tự, field) | Trung bình × Cao | Golden trước khi sửa; import lười; kiểm chéo worktree `70998af`; test không-import |
| Golden lệch giữa các process (RT-01: thứ tự `set` theo hash seed ở `compare.py:67-71`, OBSERVED `SERVICE-BRD-08`) | Cao (nếu không cố định seed) × Cao | Capture + kiểm trong subprocess `PYTHONHASHSEED=0` (D16); test cross-seed với `HASHSEED_SENSITIVE` khai báo tường minh; golden ghi interpreter minor. Lệch giữa seed ở case mới ⇒ đó là phụ thuộc thứ tự `set`/hash: tìm `file:line` nguyên nhân, **không** nới so sánh, không tự thêm vào danh sách khi chưa có người duyệt |
| `relation_pairs` mở candidate sai (cạnh sai ⇒ so sánh thân↔phụ lục vô nghĩa) | Trung bình × Trung bình | Chỉ khi flag bật; candidate vẫn qua `_downgrade_uncertain_candidates` (`idp.py:576-588`) và review; đo số candidate thêm trong `stats` |
| REJECTION/SCOPE_LIMIT là quyền/phạm vi hợp đồng, không phải thao tác văn bản; ra BE thành `candidate_amendment` `severity="high"` (`persistence.py:834,851`) | Cao × Trung bình (RT-06; trước đây ghi "Thấp" là sai) | Chỉ sinh khi có địa chỉ **và** nguồn ở `annex:*` hoặc dưới đơn vị thao tác; không std; n=0 ⇒ không bao giờ PASS; báo cáo ghi "không có gold". Tồn dư: phụ lục kỹ thuật file riêng ghi "có quyền từ chối … theo Điều 7" vẫn ra cạnh — `NEEDS_REVIEW` |
| Địa chỉ hậu tố bị mất ⇒ INSERTION trỏ đơn vị anchor có thật (RT-02) | Cao (nếu không sửa) × Cao | Grammar P2 + bất biến INSERTION; test câu 5a/d1/30a ở cả parser, integration và harness |
| Câu thao tác vắt dòng ⇒ citation nguồn không VALID | Trung bình × Thấp | Cạnh vẫn sinh, `NEEDS_REVIEW`; đếm `citation_invalid` trong `stats` |
| Văn phong phụ lục hợp đồng khác VBQPPL ⇒ recall thấp | Cao × Trung bình | Ngoài khả năng đo đợt này; ghi trong báo cáo + doc AI2-19 |

## Rollback

`git revert <commit P3>`: gỡ 2 điểm trong `idp.py`, model, parser, builder, golden, báo cáo P3. Runtime về đúng trạng thái P2 (không cạnh). Rollback nóng không cần revert: để `AI2_CONTRACT_GRAPH_ENABLED` tắt.
