---
id: 261007-1735-ai2-contract-graph-op-first
title: "AI2 contract graph - luong 1 operation-first"
description: "Đồ thị cạnh sửa đổi (INSERTION/SUBSTITUTION/REPEAL/REJECTION/SCOPE_LIMIT) deterministic, sau flag tắt mặc định, đo trên bộ VBHN, gửi BE dưới dạng AMENDS."
status: in_progress
priority: P2
effort: "~6 ngày công (P1 1,5 · P2 1 · P3 2 · P4 1,5)"
mode: hard
tdd: true
branch: feature/ai2-contract-graph
tags: [ai2, contract-graph, operation-parser, vbhn-eval, feature-flag, postgres]
created: 2026-10-07
author: 
decisions: []
phases:
  - phases/phase-1-vbhn-eval-harness.md
  - phases/phase-2-address-resolver.md
  - phases/phase-3-operation-parser.md
  - phases/phase-4-edge-storage.md
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Plan: AI2 contract graph - luong 1 operation-first

Chế độ: `--hard --deep --tdd`. Mỗi phase có file inventory, test-scenario matrix, dependency map, cặp TDD red→green. Không `--parallel` (4 phase chuỗi tuyến tính, xem §Dependency).
Nhãn bằng chứng: **OBSERVED** = đã chạy/đọc trong phiên lập plan; `file:line` = đã đọc; `[ASSUMED]` = chưa kiểm; `[PRIOR]` = kiến thức có sẵn.

## Tổng quan

AI2 hiện chỉ có `AMENDS` thô: sinh khi một node vừa có tham chiếu "Điều N" vừa có từ sửa ở bất kỳ đâu trong node (`ai-service/app/reasoning/relations.py:482-483`), không biết khoản/điểm, không phân loại thao tác. Plan này xây **luồng 1 (operation-first)**: đọc câu thao tác tường minh ("Sửa đổi, bổ sung điểm c khoản 1 Điều 3 như sau:"), phân loại thành 5 loại cạnh, resolve địa chỉ đích tới node có thật trong cây cấu trúc của `DossierRecord`, và phát cạnh có citation hai phía. Tất cả deterministic, không LLM.

Spike đã chứng minh phần phát hiện + phân loại rẻ và chính xác trên văn bản pháp quy (OBSERVED: op 26/26, địa chỉ nguồn 26/26, đích đủ cấp 16/26 trên NĐ 50/2021 + VBHN 02/VBHN-BXD — `plans/reports/spike-261007-1719-operation-parser-vbhn-report.md`). Điểm khó thật là **resolve địa chỉ** (10/26 hụt do mục cha nêu nhiều khoản) và **đo cho đáng tin** (n=1 cặp, một cơ quan). Vì vậy thứ tự là: bộ đo trước (P1) → resolver (P2) → parser + tích hợp sau flag (P3) → lưu trữ + đưa ra wire (P4).

Toàn bộ chạy sau `AI2_CONTRACT_GRAPH_ENABLED` (mặc định tắt). Flag tắt thì output `run_idp` phải **byte-identical** với hôm nay (golden regression, P3). Contract BE không đổi.

## Quyết định đã khoá (không re-litigate)

| # | Quyết định | Nguồn |
|---|---|---|
| K1 | Phạm vi REDUCTION: chỉ luồng 1, đúng 4 phase P1–P4 | user |
| K2 | Flag `AI2_CONTRACT_GRAPH_ENABLED` mặc định OFF; OFF ⇒ output `run_idp` byte-identical (có regression test) | user |
| K3 | Contract BE không đổi: cả 5 loại cạnh ra BE là `relation_type="AMENDS"`. BE so chuỗi tại `backend/src/contract_intelligence/shared/ai/persistence.py:834`; `FindingItem`/`Ai2ComparisonPayload` `extra="forbid"` (`backend/src/contract_intelligence/shared/ai/schemas.py:253-288`). Thông tin thêm **chỉ** ở `index_contribution.coverage` (schema `{"type": "object"}`, `docs/contracts/ai2.be.processing.result.v1.schema.json:74`, OBSERVED) và bảng ai2 mới | user |
| K4 | Thao tác ngầm (phụ lục không có địa chỉ, vd "thay đổi số lượng hàng hóa" + bảng) → tìm đích qua `item_key` khớp fact thân → `SUBSTITUTION` ngầm, **luôn** `NEEDS_REVIEW` | user |
| K5 | `PASS` chỉ khi: câu thao tác chuẩn + đích resolve duy nhất + citation hai phía **và** loại cạnh đó đạt cận dưới Wilson ≥ 0,85 với n ≥ 60. Trước đó mọi cạnh `NEEDS_REVIEW`. Cổng qua config, mặc định tắt | user |
| K6 | Không LLM đợt này | user |
| K7 | Tái dùng `ai-service/app/pipeline/relation_markers.py` (`has_amend_marker`, `defined_term`) từ commit `70998af`; nhánh `feature/ai2-contract-graph` cắt từ commit đó | user |
| K8 | Lưu trữ: Postgres schema `ai2` (DEC-BE-AI2-01 D11, `docs/contracts/DEC-BE-AI2-01-contract-decisions.vi.md:40`) | user + doc |
| K9 | Out: phân loại cặp bằng LLM (luồng 2), đổi query/L1, UI, Kafka, bump contract version, cạnh `GENERAL_SPECIFIC`/`CONFLICT` | user |

## Quyết định kỹ thuật của plan (tinh chỉnh, có bằng chứng)

| # | Quyết định | Lý do / bằng chứng |
|---|---|---|
| D1 | Model cạnh **tách riêng** `ai-service/app/contracts/contract_graph.py` (`EdgeOp`, `ContractEdge`), **không** mở rộng `RelationType` (`ai-service/app/contracts/models.py:76-82`) | `wire.py:318` serialize `original.relation_type.value` thẳng ra BE; nếu `RelationType` có `INSERTION` thì một lỗi map là lộ loại con sang BE. Tách enum làm việc lộ không thể xảy ra về cấu trúc. Model nằm ở tầng `contracts/` vì cả `pipeline/` lẫn `tools/store.py` đều import (tránh vòng import pipeline↔tools). P3 tạo model (producer đầu tiên); P4 lo lưu + wire — tinh chỉnh so với phase guidance |
| D2 | Đọc flag lúc gọi bằng `os.getenv`, tập truthy `{"1","true","yes","on"}`; flag phụ `AI2_CONTRACT_GRAPH_AUTO_PASS` (mặc định tắt) | Cùng quy ước `ai-service/app/reasoning/vector_recall.py:238` |
| D3 | Điểm tích hợp: trong `run_idp` sau khối `annex_labels` (`ai-service/app/pipeline/idp.py:259-272`), trước `pairer = CandidatePairer()` (`idp.py:278`). Cạnh mới được hợp vào `relation_pairs` (`idp.py:273-277`) | `relation_pairs` là cổng cho phép ghép fact khác file (`ai-service/app/pipeline/compare.py:188-193` `_pairing_allowed`). Flag bật ⇒ có thể mở thêm candidate thân↔phụ lục: **cố ý**, có test |
| D4 | Issue của graph append **sau** `idp.py:318` (RT-12: issue còn được thêm sau `idp.py:292` tới `:318`, nên chèn ở `:292` sẽ đổi id) | `_review_items_for_result` đặt id `review:{code}:{index}` theo vị trí (`idp.py:495-500`); append sau mọi issue cũ giữ nguyên tiền tố id cũ. Khi cạnh mở khoá candidate mới thì id phía sau có thể dịch — test chỉ khẳng định cho fixture không mở khoá cặp nào (phase-3 §TDD) |
| D5 | Ra BE: mỗi cạnh → `ContextFinding(kind="AMENDMENT_SIGNAL", relation_type=RelationType.AMENDS)` append vào `contract_context.findings` ngay sau `idp.py:306`; `subject_key` = địa chỉ đích chuẩn hoá; `metadata={}`; `reason` chung cho mọi loại (không nêu loại con) | Đi qua `wire.py:308-324` sẵn có; `idp.py:307-318` tự sinh review issue như `AMENDMENT_SIGNAL` cũ (`contract_context.py:208-221`). BE bỏ finding có citation từ < 2 tài liệu (`persistence.py:825`) và finding `PASS` (`persistence.py:811`) |
| D6 | Coverage: đúng **một** key lồng `coverage["contract_graph"]`, chỉ ghi khi flag bật | Flag tắt không thêm key ⇒ giữ byte-identical; BE đọc coverage như dict (`persistence.py:193`) |
| D7 | Bảng `ai2.contract_edges` (migration `0005`) ghi trong transaction của `PostgresJobStore.complete_with_snapshot` (`ai-service/app/tools/jobs.py:535-573`), cùng advisory lock, chỉ khi job là SUCCEEDED mới nhất **và** graph đã chạy; thay thế theo `(tenant_id, dossier_id)`. Không có bảng SQLite | D11 bỏ SQLite (A7); bảng mới không có tiền lệ SQLite nên không có nghĩa vụ parity. `SQLiteJobStore.complete_with_snapshot` (`jobs.py:395-403`) giữ nguyên |
| D8 | Cạnh đi tới job store qua thuộc tính dataclass `DossierRecord.contract_edges` (`ai-service/app/tools/store.py:24-54`), **không** thêm field vào `JobResult`/`IndexContribution` | `ai-service/app/api/main.py:309` lưu `result.model_dump()` vào `result_json`: thêm field Pydantic đổi bytes kể cả khi flag tắt. `record_to_dict` liệt kê field tường minh (`ai-service/app/tools/persist.py:55-80`) nên query snapshot không đổi |
| D9 | `contract_edges` khai báo trong `tables.py` bằng **`MetaData` riêng** | `0001_ai2_initial.py:13` gọi `metadata.create_all(cx)`: nếu dùng chung `metadata`, DB mới sẽ có bảng từ 0001 rồi 0005 nổ `DuplicateTable` |
| D10 | `edge_id = "cedge:" + sha256(...)[:24]`, không uuid | Cùng mẫu `relations.py:414-416`; retry cùng snapshot ra cùng id |
| D11 | Builder bọc `try/except` trong `run_idp` → issue `CONTRACT_GRAPH_FAILED` (`NEEDS_REVIEW`), pipeline chạy tiếp; trần `MAX_EDGES=500` → `CONTRACT_GRAPH_TRUNCATED` | Graph là phần làm giàu, không được làm FAILED job |
| D12 | Địa chỉ chuẩn hoá **giữ `đ`** của chữ điểm | `fold_for_match` đổi `đ→d` (`ai-service/app/pipeline/ai1_snapshot_adapter.py:2455`) ⇒ "điểm đ" va "điểm d" |
| D13 | Gold tự trích từ chú thích VBHN mang `approved=false`; calibration cho cổng PASS chỉ đếm bản ghi `approved=true` ⇒ đợt này cổng PASS không thể mở, kể cả khi bật env | `docs/code-standards.md` §Testing: "Candidate corpus không tự thành ground truth" |
| D14 | Test của harness nằm ở `evals/contract_graph/tests/`, chạy từ repo root bằng python của venv ai-service | `ai-service/pyproject.toml:61` `testpaths = ["tests"]` nên lệnh suite ai-service không gom `evals/`; quy ước chạy eval: `evals/docs/production-eval-setup.md:28` |
| D15 | Fixture DOCX dựng trong test bằng `zipfile`, không commit `.docx` | `.gitignore:5` `*.docx` |

## Ràng buộc (constraint-scan)

- `harness/data/ownership.yaml`: zone `plans: [plans/]`, `docs: [docs/]`, `state: [.harness/state/]` (không enforce). Code dưới `ai-service/` và `evals/` **ngoài** mọi zone harness → không bị fs_guard ràng; là vùng code thường của repo. Plan chỉ ghi trong `plans/` [IN].
- Không đụng core được bảo vệ (`harness/`, `.claude/settings.json`).
- Schema wire: `docs/contracts/ai2.be.processing.result.v1.schema.json` — `context_finding` `additionalProperties: false` với tập field cố định (dòng 48-56), `relation_type` là `string|null`; `coverage` là object mở (dòng 74). Không sửa file schema.
- `job_result_to_wire` tự gọi `validate_processing_result` (`ai-service/app/contracts/wire.py:389`) ⇒ payload lệch schema sẽ fail ngay trong test.
- Code standards: không suy ra legal winner; thiếu/mơ hồ → `NEEDS_REVIEW`/`INSUFFICIENT_EVIDENCE` (`docs/code-standards.md` §Contract); evals tách `denominator`/`covered`/`passed` + nguồn ground truth (§Testing).
- Caller (liệt kê bằng grep, không qua `hs-run … --fact-subjects` vì planner chạy dạng subagent không có facts snapshot):
  - `run_idp` — 9 call site: `ai-service/app/api/main.py:292, 1136, 1492, 1699, 1714, 1750`; `ai-service/app/pipeline/ai2_batch.py:115, 179`; `ai-service/app/transport/kafka_idp_worker.py:180`. Tất cả đi qua cùng một hàm ⇒ golden ở mức `run_idp` phủ cả 9; chỉ `main.py:292` dẫn tới `complete_with_snapshot`.
  - `complete_with_snapshot` — 1 call site: `ai-service/app/api/main.py:302`.
  - Test gọi `run_idp`: 22 file trong `ai-service/tests/` (OBSERVED grep) — đều phải giữ xanh sau P3/P4.
- Postgres test chỉ chạy khi có `AI2_TEST_DATABASE_URL` hoặc Docker (`ai-service/tests/conftest.py:12-24`), nếu không thì skip. Lần chạy suite trong phiên lập plan: 36 skipped (OBSERVED); máy lập plan **không có Docker** (OBSERVED: `docker: command not found`) ⇒ Postgres test bị skip ở đây. P4 cần `AI2_TEST_DATABASE_URL` trỏ một Postgres 16 (+pgvector nếu muốn chạy cả test vector) hoặc máy có Docker.

## Data flow

```
DossierRecord (evidence_nodes, source_files.role, pages, tables)
 └─ run_idp (idp.py:46)
     … facts dedupe (idp.py:255) → chunks (256) → events (257) → annex_labels (259-272)
     ├─ [flag ON] build_contract_graph(record, facts)                         P3 builder.py
     │    nodes ─► split_operation_units ─► parse_operation (op, target_text,  P3 operations.py
     │             new_text, scope, standard, span)   [lọc: has_amend_marker + loại trừ]
     │          ─► parse_addresses(target_text) + inherit(parent) ─► Address   P2 address.py
     │          ─► StructureIndex.resolve(Address, scope parts)               P2 resolver.py
     │               UNIQUE → ContractEdge(review_state=review_policy(...))    P3 review_policy.py
     │               AMBIGUOUS → EvidenceIssue TARGET_AMBIGUOUS (NEEDS_REVIEW)
     │               NOT_FOUND → EvidenceIssue TARGET_NOT_FOUND (INSUFFICIENT_EVIDENCE)
     │    annex facts không địa chỉ ─► item_key ↔ body facts ─► SUBSTITUTION ngầm   P3 implicit.py
     │    ⇒ ContractGraphResult(edges, issues, stats)
     ├─ relation_pairs |= {(src,tgt)}  ─► CandidatePairer (idp.py:278)
     ├─ issues += graph.issues (sau idp.py:292)
     ├─ contract_context.findings += AMENDS findings (sau idp.py:306)          P4 projection.py
     ├─ coverage["contract_graph"] = {...}                                      P4 projection.py
     └─ record.contract_edges = graph.edges                                     P4
 └─ main._execute_wire_job (main.py:243) → job_result_to_wire → JOB_STORE.complete_with_snapshot (main.py:302)
     └─ PostgresJobStore: UPDATE jobs → UPSERT query snapshot → REPLACE ai2.contract_edges   P4 jobs.py + contract_edge_store.py
```

Ngoài pipeline: `evals/contract_graph/` (P1) lấy cặp (văn bản sửa đổi, VBHN) → chuẩn hoá text → gold từ chú thích VBHN → bộ dữ liệu đông cứng + manifest sha256 → predictor (P1 baseline spike, P3 pipeline thật) → scorer per-op + Wilson CI → báo cáo commit trong repo.

## Features

- **F1 vbhn-eval** — bộ đo tự động cho luồng 1: ≥10 cặp văn bản, nhiều cơ quan, có REPEAL; báo precision/recall/độ đúng đích theo loại cạnh kèm Wilson CI.
- **F2 address-resolution** — địa chỉ tiếng Việt ("điểm c khoản 1 Điều 3", "khoản 5 vào sau khoản 4 Điều 4", "điểm a" tương đối, "Phụ lục 01", "khoản này") resolve tới node có thật; trả unique/ambiguous/not_found, không bịa node.
- **F3 operation-edges** — cạnh `INSERTION`/`SUBSTITUTION`/`REPEAL`/`REJECTION`/`SCOPE_LIMIT` từ câu thao tác tường minh, citation hai phía, mặc định `NEEDS_REVIEW`.
- **F4 implicit-annex-substitution** — phụ lục không ghi địa chỉ → cạnh `SUBSTITUTION` ngầm qua `item_key`, luôn `NEEDS_REVIEW`.
- **F5 graph-flag** — toàn bộ sau `AI2_CONTRACT_GRAPH_ENABLED` (mặc định tắt); tắt thì output không đổi một byte.
- **F6 be-amends-projection** — cạnh tới BE dưới dạng `AMENDS` + `coverage.contract_graph`; contract không đổi.
- **F7 edge-persistence** — bảng `ai2.contract_edges` có downgrade.

## Phases

| # | Theme | Phụ thuộc | Cỡ | File chính |
|---|---|---|---|---|
| 1 | VBHN eval harness | — | M (1,5 ngày) | `evals/contract_graph/*` |
| 2 | Address resolver | P1 (đo trên dữ liệu P1) | S–M (1 ngày) | `ai-service/app/pipeline/contract_graph/{address,resolver}.py` |
| 3 | Operation parser + tích hợp `run_idp` sau flag | P1, P2 | L (2 ngày) | `contract_graph/{operations,implicit,review_policy,builder}.py`, `app/contracts/contract_graph.py`, `idp.py` |
| 4 | Edge storage + wire | P3 | M (1,5 ngày) | migration `0005`, `tables.py`, `jobs.py`, `store.py`, `contract_graph/projection.py`, `tools/contract_edge_store.py`, `idp.py` |

### Dependency

```
P1 ──► P2 ──► P3 ──► P4
```

Tuyến tính. P2 không cần P1 để viết unit test, nhưng tiêu chí thành công của P2 đo trên bộ dữ liệu P1; P3 cần cả resolver (P2) và harness (P1); P4 cần model cạnh + builder (P3). Không có antichain đáng chạy song song ⇒ không `--parallel`.

### File ownership

Mỗi file thuộc đúng một phase, **trừ** `ai-service/app/pipeline/idp.py`: P3 sửa (gọi builder, `relation_pairs`, issues) và P4 sửa (findings, coverage, `record.contract_edges`). Hai phase nối bằng cạnh P3→P4 nên không chạy đồng thời; `plan_graph.py` chỉ báo xung đột cho cặp phase không có đường đi (`harness/scripts/plan_graph.py:525-552`). Golden flag-off (`ai-service/fixtures/contract_graph/idp_flag_off_golden.json`) do P3 tạo và **không** phase nào sau được sửa.

## Out of scope

- Luồng 2: phân loại cặp bằng LLM, NLI, cross-encoder.
- Đổi query/L1/L3, vector, UI, Kafka worker (`ai-service/app/transport/kafka_idp_worker.py` vẫn gọi `run_idp` và nhận cạnh in-memory khi flag bật nhưng **không** ghi bảng — không có `complete_with_snapshot` trên đường đó).
- Bump `ai2.be.processing.result.v1`, sửa schema JSON, sửa BE.
- Cạnh `GENERAL_SPECIFIC`, `CONFLICT`, `REPLACEMENT`, `RENUMBERING`; mâu thuẫn vẫn là `COMPARABLE_DIFFERENCE`.
- Sửa `relations.py` `AMENDS` cũ. (`contract_context.py` `AMENDMENT_SIGNAL` cũ **được** tắt khi flag bật và builder thành công — Q3, phase-4 §Requirements 10.)
- Gán nhãn thủ công / duyệt gold (`approved=true`) — việc của người, ngoài plan (Câu hỏi mở Q1).
- Đọc bảng `ai2.contract_edges` từ bất kỳ consumer nào.

## Acceptance (toàn plan)

- [ ] Mỗi phase red→green TDD; test đầu tiên của phase được chạy và thấy FAIL (hoặc PASS nếu là test khoá regression) trước khi viết code.
- [ ] Suite ai-service: từ `ai-service/` chạy `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q -p no:cacheprovider --basetemp=<thư mục ghi được>` → xanh **trừ đúng 13 lỗi môi trường có sẵn** (OBSERVED 2026-10-07: 13 failed / 1061 passed / 36 skipped trên `70998af`):
  - `tests/unit/test_mistral_ocr.py` × 7 (`ModuleNotFoundError: mistralai`): `test_text_block_becomes_a_measured_line`, `test_table_block_becomes_a_table_with_heading_before`, `test_requests_blocks_and_block_level_confidence_and_leaves_table_format_unset`, `test_raw_markdown_is_written_to_raw_md`, `test_full_page_text_is_authoritative_even_when_block_geometry_is_missing`, `test_table_text_remains_in_reading_order_for_clause_extraction`, `test_no_blocks_returns_empty_result_without_crashing`.
  - Thiếu `HD-TONG-HOP.sample.pdf` (`FileNotFoundError`): `tests/test_hd_gold.py::test_hd_tong_hop_gold_two_source_findings`, `tests/test_ingest.py::test_hd_tong_hop_sample_pdf_extracts_and_answers_dieu_9`, `tests/test_structure_reconstruction.py::test_master_contract_reconstruction_keeps_scopes_and_does_not_promote_inline_annex_reference`, `tests/test_structure_reconstruction.py::test_citation_contains_full_structure_path_and_source_scope`, `tests/test_structure_reconstruction.py::test_pdf_party_declarations_are_not_confused_with_clause_mentions`.
  - Thiếu artifact `plans/260923-1023-ai2-long-running-architecture`: `tests/test_p0_contract_baseline.py::test_p0_artifact_freezes_decisions_and_executable_case_refs`.
  - Mọi lỗi khác tên, hoặc số passed giảm so với 1061 + test mới, là regression.
- [ ] Suite harness: từ repo root `uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m pytest -q -p no:cacheprovider evals/contract_graph/tests` xanh (fallback: `ai-service/.venv/Scripts/python.exe -m pytest -q evals/contract_graph/tests`). OBSERVED 2026-10-07: cách gọi `uv run --project ai-service … python -m pytest` từ repo root chạy được (`pytest 9.1.1`; `evals/tests/test_clause_key_spike.py` 102 passed, import `evals.*` OK).
- [ ] Flag tắt: `ai-service/tests/test_contract_graph_flag_off_regression.py` xanh sau P3 **và** sau P4, với golden không đổi sha256 kể từ lúc capture.
- [ ] Báo cáo đo commit trong repo có số thật: `evals/contract_graph/reports/p1-baseline.{json,md}`, `p2-resolver.{json,md}`, `p3-operation-parser.{json,md}` — mỗi loại cạnh có `n`, `k`, tỷ lệ, Wilson 95%.
- [ ] Payload wire khi flag bật validate qua `docs/contracts/ai2.be.processing.result.v1.schema.json` (`validate_contract`) và không chứa chuỗi `INSERTION|SUBSTITUTION|REPEAL|REJECTION|SCOPE_LIMIT` ngoài `index_contribution.coverage`.
- [ ] Migration `0005` upgrade/downgrade/upgrade chạy thật trên Postgres (Docker hoặc `AI2_TEST_DATABASE_URL`, `AI2_REQUIRE_DOCKER=1` để không bị skip). Nếu máy cook không có Postgres: P4 verification ghi `SKIPPED` kèm lý do, **không** ghi PASS cho tiêu chí này.
- [ ] Không có ngưỡng nào bị nới: `MIN_N=60`, `MIN_WILSON_LOWER=0.85` là hằng số, có test khẳng định.

### Test matrix tổng

| Tầng | Cái gì | Ở đâu |
|---|---|---|
| Unit | chuẩn hoá text, trích gold, segment, scorer/Wilson, manifest | `evals/contract_graph/tests/` (P1) |
| Unit | parse địa chỉ, resolver, disambiguate theo thứ tự | `ai-service/tests/test_contract_graph_{address,resolver}.py` (P2) |
| Unit | parse câu thao tác, loại trừ, implicit, review policy | `ai-service/tests/test_contract_graph_{operations,implicit,review_policy}.py` (P3) |
| Integration | `run_idp` flag tắt = golden; flag bật sinh cạnh/issue/`relation_pairs` | `ai-service/tests/test_contract_graph_{flag_off_regression,idp_integration}.py` (P3) |
| Unit + Integration | projection AMENDS + coverage; wire + schema + không lộ loại con; edge row/digest + SQLite bỏ qua; Postgres replace/fence/nguyên tử; migration down/up | `ai-service/tests/test_contract_graph_{projection,wire,edge_store,postgres_store}.py` (P4) |
| E2E đo | harness chạy predictor thật trên toàn bộ dữ liệu, ra báo cáo | `evals/contract_graph/run_eval.py` (P1 baseline, P2 resolver, P3 parser) |

## Rollback

- Mỗi phase là **một commit** (hoặc một dải commit liên tiếp có tag `p<N>`); hoàn tác = `git revert <commit-của-phase>` theo thứ tự ngược (P4 → P3 → P2 → P1). Sau revert chạy lại suite ai-service + suite harness.
- **Rollback mặc định = tắt flag**, không revert code.
- P4 có schema, **thứ tự bắt buộc** (RT-03): trên môi trường đã migrate, chạy **trước** `python -m app.db.migrate downgrade 0004_ai2_job_indexes` (từ `ai-service/`; CLI `alembic` không dùng được vì `env.py:5` cần connection truyền vào) — drop `ai2.contract_edges`, dữ liệu cạnh tái sinh được. **Revert code P4 khi DB còn ở 0005 làm hỏng boot**: `migrate()` (qua `ensure_database`, `engine.py:43`) nổ `Can't locate revision '0005_ai2_contract_edges'` ⇒ mọi đường Postgres lỗi. Chi tiết: phase-4 §Rollback.
- Rollback runtime không cần deploy: đặt `AI2_CONTRACT_GRAPH_ENABLED=false` (mặc định) ⇒ luồng mới không chạy, output về đúng như hôm nay (được golden test bảo đảm).
- P1 chỉ thêm file dưới `evals/contract_graph/`, revert không ảnh hưởng runtime.

## Risks

| # | Rủi ro | Khả năng × Tác động | Mitigation |
|---|---|---|---|
| R1 | Flag tắt nhưng output đổi (import side-effect, thứ tự issue, field mới trong model Pydantic) | Trung bình × Cao | Golden capture **trước** khi sửa `idp.py` (P3 bước 1); uuid4 patch deterministic; D8 (không thêm field Pydantic); test chạy lại sau P4 |
| R2 | 0005 nổ `DuplicateTable` trên DB mới vì 0001 `create_all` | Cao (nếu làm ngây thơ) × Cao | D9 MetaData riêng; test fresh-DB upgrade head + downgrade + upgrade |
| R3 | Resolver chọn sai khoản khi mục cha nêu nhiều khoản (10/26 spike) | Cao × Cao | Lọc tồn tại → suy theo thứ tự đánh dấu `ORDER_INFERENCE` (không bao giờ PASS) → còn mơ hồ thì `AMBIGUOUS`, không đoán; đo riêng trong báo cáo P2 |
| R4 | Gold tự trích sai (lỗi spike: tên nghị định chứa "sửa đổi, bổ sung"; mục lục) ⇒ số đo sai | Trung bình × Cao | Lấy op trước "theo quy định tại"; chọn thân "Điều 1." dài nhất; test từ chính 2 lỗi spike; gold `approved=false` (D13) |
| R5 | Không lấy đủ ≥10 cặp (mạng, trang đổi cấu trúc, HTML nhúng JSON escape) | Trung bình × Trung bình | Cache raw; normalizer xử lý HTML escape trong JSON (OBSERVED trên `vbhn02bxd.html`: phần chú thích nằm trong chuỗi `<…`); thiếu thì P1 **BLOCKED** kèm số đếm thật, không tự hạ ngưỡng |
| R6 | Trùng hàng review: `AMENDMENT_SIGNAL` cũ (`contract_context.py:208-221`) + cạnh mới cho cùng phụ lục | Cao × Trung bình | Q3 (người dùng chốt 2026-10-08): flag bật + builder thành công ⇒ tắt `AMENDMENT_SIGNAL` cũ; builder lỗi ⇒ giữ. RT-07: `edge_findings` bỏ cạnh trùng cặp node với `CANDIDATE_AMENDMENT` cũ, đếm `deduped_with_legacy` (phase-4 §Requirements 10) |
| R7 | BE bỏ cạnh nội tài liệu (`persistence.py:825` cần ≥2 tài liệu) và cạnh PASS (`persistence.py:811`) | Chắc chắn × Thấp đợt này | Cạnh vẫn có trong coverage + bảng; ghi rõ trong doc AI2-19; Q2 cho lúc mở cổng PASS |
| R8 | Precision op trên phụ lục hợp đồng thấp hơn văn bản pháp quy (văn phong khác, n=1 mẫu phụ lục) | Cao × Trung bình | Mọi cạnh `NEEDS_REVIEW`; cổng PASS khoá (D13); báo cáo ghi rõ domain = VBQPPL |
| R9 | Postgres test bị skip trên máy cook ⇒ tưởng migration xanh (máy lập plan không có Docker — OBSERVED) | Cao × Cao | `AI2_REQUIRE_DOCKER=1` khi chạy test P4; verification ghi SKIPPED nếu không chạy được |
| R10 | Builder hoặc bước ghi cạnh ném lỗi/timeout làm FAILED cả job | Thấp × Cao | D11 bọc try/except + issue cho builder; ghi cạnh trong savepoint `begin_nested()` + lọc NUL (RT-04, phase-4 §Requirements 7); không gọi `runtime.checkpoint()` trong builder |

## Red-team disposition

Nguồn: `reports/from-code-reviewer-to-planner-red-team-eval-integrity-plan-review-report.md` (15 finding: 4 High, 10 Medium, 1 Low). Không còn ô mở.

| ID | Mức | Xử lý | Sửa ở đâu | Lý do / cách sửa |
|---|---|---|---|---|
| RT-01 | High | ACCEPTED-FIXED | phase-3 §Requirements (dòng 18, 86), §TDD (141), §Implementation (215, 249); phase-1 (58, 131) | Golden flag-off capture và kiểm trong **subprocess** với `PYTHONHASHSEED=0`; thêm test so 2 seed khác nhau; hướng dẫn đổi thành "uuid/time/thứ tự set" (`compare.py:67-71`) |
| RT-02 | High | ACCEPTED-FIXED | phase-1 §3–4 (38–43, 109–118); phase-2 §2 grammar (31–59, 105–107, 124–126); phase-3 (42, 59, 148, 181) | Thêm địa chỉ hậu tố `khoản \d+[a-zđ]?`, `điểm [a-zđ]\d*`, `Điều \d+[a-zđ]?`, danh sách trần "d1, d2"; bất biến INSERTION `canonical(new) != canonical(anchor)`; test "Bổ sung khoản 5a vào sau khoản 5" không resolve vào khoản 5 |
| RT-03 | High | ACCEPTED-FIXED | phase-4 §Requirements 8, §Implementation 8/10, test `test_0005_downgrade_entrypoint_then_upgrade`, §Rollback; plan.md §Rollback | Entrypoint `python -m app.db.migrate downgrade <rev>` có test; runbook: downgrade **trước** revert; ghi rõ revert trước làm hỏng boot; rollback mặc định = tắt flag |
| RT-04 | High | ACCEPTED-FIXED | phase-4 §Requirements 7, test `test_edge_write_failure_keeps_job_succeeded`, `test_edge_row_strips_nul_from_text_columns`; R10 | Ghi cạnh trong `cx.begin_nested()`; lỗi ⇒ log, giữ cạnh cũ, job vẫn SUCCEEDED; lọc `\x00` |
| RT-05 | Medium | ACCEPTED-FIXED | phase-1 (44, 118, 164); phase-2 (90, 142, 169, 182, 192); phase-3 (75, 90, 116, 191, 226) | Chế độ đo thứ hai: gập cây VBHN về node "Điều N" (hình dạng AI1), báo cả hai |
| RT-06 | Medium | ACCEPTED-FIXED | phase-3 (62, 75, 111, 146, 173, 179, 227, 251) | REJECTION/SCOPE_LIMIT chỉ phát khi nguồn ở `annex:*` hoặc dưới đơn vị chứa thao tác; sửa đánh giá tác động |
| RT-07 | Medium | ACCEPTED-FIXED | phase-4 §Requirements 10, tests `test_edge_duplicating_legacy_candidate_amendment_is_not_projected`, `test_flag_on_suppresses_legacy_amendment_signal`, `test_flag_on_builder_failure_keeps_legacy_amendment_signal`; R6 | Flag bật + builder OK ⇒ tắt `AMENDMENT_SIGNAL` cũ (Q3); bỏ cạnh trùng `CANDIDATE_AMENDMENT` theo cặp node; đếm `deduped_with_legacy`; cạnh vẫn ghi bảng |
| RT-08 | Medium | ACCEPTED-FIXED | phase-3 (55–61, 111, 147–149, 180, 228) | Thêm SUBSTITUTION (không std) cho "Điều chỉnh/Thay đổi <địa chỉ> … như sau:" và "<địa chỉ> được thay bằng"; fixture phụ lục hợp đồng |
| RT-09 | Medium | ACCEPTED-FIXED | phase-1 (47, 66, 124, 163); phase-3 (200, 229, 240) | Đổi tên chỉ số thành `op_lexical_agreement`; cổng không-kém-baseline P3 kiểm thêm precision (`unmatched_predictions` không tăng) |
| RT-10 | Medium | ACCEPTED-FIXED | phase-2 (16, 151, 170, 183); phase-1 (49, 125, 178) | Bỏ mốc "16/26 đúng"; baseline = `target_correct` đo ở `p1-baseline` |
| RT-11 | Medium | ACCEPTED-FIXED | phase-4 §Requirements 9, file inventory, §Implementation 8; plan-graph P4 | `test_ai2_postgres_store.py:612` so với script head thay vì hardcode `0004_ai2_job_indexes` |
| RT-12 | Medium | ACCEPTED-FIXED | plan.md D4; phase-3 (80, 111, 178, 225) | Append issue graph **sau** `idp.py:318`; test id review chỉ khẳng định cho fixture không mở khoá cặp nào |
| RT-13 | Medium | ACCEPTED-FIXED | phase-1 (48, 123, 160); phase-2 (89) | Scorer ghép một-một theo `(src_address, target_address)`; pred thừa cùng src ⇒ unmatched; test 2 gold cùng src |
| RT-14 | Medium | ACCEPTED-FIXED | phase-1 (33, 103, 161, 193) | `operative_body` bỏ qua `Điều N.` nằm trong ngoặc kép; fixture "Sửa đổi Điều 2 như sau: “Điều 2. …”" |
| RT-15 | Low | ACCEPTED-FIXED | phase-1 (90–91, 194) | Cook trong worktree `contract-intelligence-develop` hoặc chép `raw/` vào cache trước; P2 được bắt đầu với nd50 + mini fixture khi P1 BLOCKED vì thiếu cặp |

## Validation Log

- VL-1 | complexity hint: complex · 4 phases · risk: address resolution + flag-off byte-identity | khớp `--hard` | giữ mode.
- VL-2 | red-team REVISE (4 High) | 15/15 finding ACCEPTED-FIXED, xem §Red-team disposition | phần P4 + bảng disposition hoàn tất tại main sau khi planner bị dừng do rate limit.
- VL-3 | validate interview 2026-10-08 | Q1: người dùng duyệt mẫu gold; Q3: tắt `AMENDMENT_SIGNAL` cũ khi flag bật (thêm `contract_context.py` vào P4) | Q2 ngoài phạm vi; Q4 cook chọn nguồn theo khả năng truy cập.
- VL-4 | consistency sweep | không còn tham chiếu tới cách làm cũ (rollback alembic CLI, test rollback-cả-transaction, "16/26 đúng") ngoài báo cáo red-team | 0 mâu thuẫn còn mở.
- VL-5 | cook P1 2026-10-08 | nd50 ra 25/26 dưới ghép một-một RT-13 (chú thích [8],[9] cùng src, 1 câu "Bổ sung điểm d1, d2") | người dùng chọn giữ 26, sửa scorer: pred mang `target_addresses` ghép tối đa một gold mỗi đích liệt kê; thêm `.gitattributes` `evals/contract_graph/data/** text eol=lf`. Dataset 11 cặp / 4 cơ quan (không có Quốc hội) / 12 REPEAL.
- VL-6 | cook P2 2026-10-08 | deviation bảo thủ (không đoán), main chấp nhận: (a) nhãn không đọc được (`điểm b.7`, `Phụ lục XXV`) ⇒ bỏ địa chỉ, không lùi cấp thô; (b) `disambiguate_by_order` dùng span cây con; (c) bảng parity bỏ `Phụ lục số N`/La Mã (gold P1 chưa hỗ trợ, ghi giới hạn). P3 lưu ý: INSERTION Điều/Phụ lục mới ⇒ `UNIQUE` với `node_id=None`. Số: nd50 target 26/26 (P1 13/26); toàn bộ UNIQUE đúng 63/65, NOT_FOUND 4; ORDER_INFERENCE 0 ca thật `[ASSUMED]`.

## Câu hỏi mở

- ~~Q1~~ **Đã chốt (2026-10-08):** người dùng (chủ dự án) tự duyệt mẫu gold — toàn bộ REPEAL + ≥30 bản ghi phân tầng theo op — rồi chuyển `approved=true`. Việc duyệt diễn ra **sau** P1 (cần dataset), ngoài thời gian cook; cổng PASS chỉ mở khi đã duyệt **và** đạt Wilson ≥ 0,85, n ≥ 60 mỗi loại. Trong đợt cook, `calibration.json` vẫn n=0 ⇒ cổng đóng.
- Q2: Khi cổng PASS mở, cạnh `PASS` sẽ biến mất khỏi danh sách finding của BE (`persistence.py:811`). Muốn BE vẫn hiển thị cạnh đã PASS thì cần quyết định phía BE — ngoài đợt này.
- ~~Q3~~ **Đã chốt (2026-10-08):** tắt `AMENDMENT_SIGNAL` cũ khi flag bật và builder thành công; giữ lại khi builder lỗi. Flag tắt vẫn byte-identical.
- Q4: Nguồn tải chính cho ≥10 cặp. OBSERVED trong phiên 2026-10-07: vcci.com.vn và caselaw.vn tải được bằng `curl`; thuvienphapluat.vn trả 403; luatvietnam.vn chỉ đọc qua tóm tắt. vbpl.vn `[ASSUMED khả dụng]`. Cook chọn theo khả năng truy cập, ghi URL vào manifest.
