---
phase: 4
title: "Integration Storage"
status: pending
plan: 261008-1500-ai2-contract-graph-implicit
created: 2026-10-08
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 4 — Integration + Storage

## Overview

Nối luồng 2 vào `run_idp` sau cờ con `AI2_CONTRACT_GRAPH_PAIRS_ENABLED` (D2) tại **sau** `issues.extend(graph_issues)` (D11, RT-03); đọc consent từ request (D4, Q1); rule-only phát issue `CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE` (D7, Q2); chiếu ≤5 `CONFLICT` thành candidate `COMPARABLE_DIFFERENCE` với evidence cả node (D8, RT-10); ghi `coverage.contract_graph` (`graph_mode` + `pairs`); lưu quan hệ vào bảng `ai2.contract_pair_relations` (migration `0006`) trong savepoint, chỉ thay dòng theo RT-14. Sửa 2 test luồng 1 hard-code head `0005` (RT-06). Phase **bắt đầu** bằng capture golden graph-on trước khi sửa `idp.py`. Kèm doc `AI2-20` và runbook rollback dừng process (RT-11).

## Dependency map

- Phụ thuộc P3: `build_pair_relations`, `pairs_enabled`, `PairResult` (`relations`, `mode`, `rule_only_reason`, `stats`, `node_parts`, `batches_completed`), `PairRelation`, `PairLabel`.
- Điểm sửa / tái dùng (đã đọc):
  - `run_idp` (`ai-service/app/pipeline/idp.py:47`): `llm` tắt ở `:80`, `:102`; `graph_enabled` `:281`; builder luồng 1 `:283-299`; pairer `:300`; clause_compare `:308-311`; `_downgrade_uncertain_candidates` `:327`; `build_contract_context` `:329`; `graph_coverage_value` `:332-351`; `context_issues` `:352-359`; `issues.extend(graph_issues)` `:361`; `coverage = {...}` `:362-375`; `record.contract_edges`/`contract_graph_ran` `:393-394`; `_contract_graph_enabled` `:431-434`; review id theo vị trí `:541-570` (`review:{code}:{index}` `:556`).
  - `build_contract_context` sinh `CONTEXT_CONFLICT` cho candidate có evidence ở ≥2 phần **cùng file** (`ai-service/app/pipeline/contract_context.py:254-278`; nhánh khác file bỏ qua `:260-263`) — lý do đặt khối pairs sau nó (RT-03, red-team repro OBSERVED).
  - `adapt_be_ai2_processing_request` (`ai-service/app/pipeline/ai1_snapshot_adapter.py:76`, `:170`).
  - `DossierRecord` (`ai-service/app/tools/store.py:27-61`; `TYPE_CHECKING` `:23-24`; attr D8 luồng 1 `:58-61`); `record_to_dict` (`ai-service/app/tools/persist.py:55`).
  - Candidate cấp khoản (`ai-service/app/pipeline/clause_compare.py:442-456`); scope (`compare.py:427-433`); `_candidate_pair` (`contract_graph/projection.py:26-29`); `citation_for_node` + `CitationResolver.verify` (`builder.py:221-231`).
  - BE: severity `high` cho mọi finding `NEEDS_REVIEW` (`persistence.py:1095`), `key_or_topic = item_key or finding_id` (`persistence.py:1087`).
  - Luồng 1: `0005_ai2_contract_edges.py`, `graph_metadata` (`ai-service/app/db/tables.py:66`), `contract_edge_store.py:21-90`, `PostgresJobStore.complete_with_snapshot` (`ai-service/app/tools/jobs.py:537-577`), savepoint (`jobs.py:579-593`), downgrade entrypoint (`ai-service/app/db/migrate.py:86-133`), `migrate()` mỗi process (`ai-service/app/db/engine.py:39-44`).
  - Golden: `ai-service/scripts/capture_idp_golden.py`, `ai-service/tests/test_contract_graph_flag_off_regression.py` (`HASHSEED_SENSITIVE`).
  - Test hard-code head: `ai-service/tests/test_contract_graph_edge_store.py:112-121` (chạy không DB), `ai-service/tests/test_contract_graph_postgres_store.py:20-21, 85, 113, 116`.
  - Fixture: `ai-service/fixtures/contract_graph_records.py` (`graph_record()`, `dossier`).
- Được dùng bởi: P5.

## Requirements

### Chức năng

1. **Golden graph-on (trước mọi sửa `idp.py`)** — `capture_idp_golden.py`:
   - `--profile {flag_off,graph_on}` (mặc định `flag_off`, giữ nguyên bytes `idp_flag_off_golden.json`). `graph_on`: env `AI2_CONTRACT_GRAPH_ENABLED=1`, xoá `AI2_CONTRACT_GRAPH_PAIRS_ENABLED`, `_PAIRS_MODEL`, `_PAIRS_BASE_URL`, `_PAIRS_API_KEY`, `AI2_CONTRACT_GRAPH_AUTO_PASS`; case = case `flag_off` + `contract_graph.graph_record` + `contract_graph.pair_record_embedded` (fixture mới, phụ lục **nhúng cùng file**); ghi `ai-service/fixtures/contract_graph/idp_graph_on_golden.json`.
   - `--strip-pairs` (chuẩn hoá trước khi băm, cho so sánh rule-only): xoá `coverage.contract_graph.pairs`; đặt `coverage.contract_graph.graph_mode = "operation_first"`; xoá mọi issue/review item có `issue_id`/`review_item_id`/`kind` chứa `CONTRACT_GRAPH_PAIRS_`; trừ tương ứng `coverage.n_evidence_issues`; bỏ khoá `review_state` cấp job khỏi phép băm (kiểm riêng: chỉ được giữ nguyên hoặc thành `NEEDS_REVIEW`).
   - Capture từ `ai-service/`: `PYTHONHASHSEED=0 uv run --frozen --extra web --extra dev --extra kafka --extra openai python scripts/capture_idp_golden.py --profile graph_on` **trên code P3 chưa sửa `idp.py`**; sha256 vào `verification-P4.json`.
2. **Consent** (D4): `DossierRecord.content_sharing_consent: bool = False` (không vào `record_to_dict`); sau `ai1_snapshot_adapter.py:170`: `result.record.content_sharing_consent = bool(request.policy_flags.egress_allowed)`. Không đổi `ProcessingPolicyFlags`/schema.
3. **Record attrs** — `store.py`: `pair_relations: list[PairRelation]` (import `TYPE_CHECKING`), `pair_relations_ran: bool = False`. Ngữ nghĩa (RT-14): `True` ⇒ job store **thay** dòng của hồ sơ bằng `pair_relations`; chỉ đặt `True` khi (`mode == "llm"` ∧ `batches_completed ≥ 1`) **hoặc** `rule_only_reason == "NO_CONSENT"` (xoá dòng do LLM sinh khi không còn consent); mọi trường hợp khác (cờ tắt, luồng 1 lỗi, pairs lỗi, rule-only vì egress/model/ngân sách/hạn, LLM hỏng trước lô đầu) ⇒ `False`, giữ dòng cũ.
4. **Tích hợp `run_idp`** — `idp.py` (D11, RT-03):
   - Cạnh `:281`: `pairs_on = graph_enabled and _contract_graph_pairs_enabled()` (hàm env cục bộ như `:431-434`, đọc một lần, không import module pairs khi tắt).
   - **Ngay sau** `issues.extend(graph_issues)` (`:361`), **trước** `coverage = {...}` (`:362`): nếu `pairs_on`:
     - `graph is None` ⇒ `pairs_status = "SKIPPED_GRAPH_FAILED"`, không gọi builder.
     - ngược lại import lười `build_pair_relations`, `pair_conflict_candidates`, `pair_coverage`, `limited_coverage_issue`; trong `try/except Exception`: `pair_result = build_pair_relations(record, graph.edges, llm=llm, runtime=runtime)`; `conflicts, conflict_stats = pair_conflict_candidates(pair_result, candidates, record)`; `candidates.extend(conflicts)`; nếu `pair_result.mode == "rule_only"` ⇒ `issues.append(limited_coverage_issue(pair_result))`. Lỗi ⇒ `pair_result = None`, `pairs_status = "FAILED"`, `issues.append(EvidenceIssue(issue_id="contract-graph:CONTRACT_GRAPH_PAIRS_FAILED", missing="CONTRACT_GRAPH_PAIRS_FAILED", reason="Không phân loại được quan hệ giữa các khoản ({type}); không có quan hệ luồng 2.", review_state=NEEDS_REVIEW))`.
     - `graph_coverage_value.update(pair_coverage(pair_result, status=pairs_status, conflict_stats=conflict_stats))` (`graph_mode` giữ vị trí khoá, `pairs` thêm cuối).
   - Cạnh `:393-394`: `record.pair_relations = list(pair_result.relations) if pair_result else []`; `record.pair_relations_ran` theo §3.
   - Không chạm `relation_pairs` (`:274-299`), `build_contract_context`, `context_issues`; không đổi gì khi `pairs_on` False.
5. **Projection** — `ai-service/app/pipeline/contract_graph/pair_projection.py`:
   - `pair_conflict_candidates(result, candidates, record) -> (list[Candidate], dict)`: duyệt quan hệ `CONFLICT` theo thứ tự `result.relations` (= thứ tự ứng viên); cặp `sorted((a, b))` đã có candidate (`_candidate_pair`) ⇒ bỏ, `conflict_deduped_with_candidates += 1`; đã đủ `PAIRS_MAX_CONFLICT_FINDINGS = 5` ⇒ bỏ, `conflict_capped += 1`; evidence = citation **cả node** `citation_for_node(nodes, record.pages, node_id, text_span=None)` + `verify`, một phía không `VALID` ⇒ bỏ, `conflict_citation_invalid += 1` (RT-10: span LLM chỉ ở bảng); `Candidate(candidate_id="cand_pair_" + sha256(f"{digest}|{a}|{b}")[:12], left_id=a, right_id=b, finding_type=COMPARABLE_DIFFERENCE, model_disposition=UNCLEAR, review_state=NEEDS_REVIEW, evidence_left=[cit_a], evidence_right=[cit_b], reason=_CONFLICT_REASON, disposition=COMPARABLE_DIFFERENCE, scope=_scope(result.node_parts[a], result.node_parts[b]), item_key=f"{canon_a} ↔ {canon_b}" nếu cả hai có canonical, ngược lại None)`. `_scope` như `compare.py:427-433` theo phần `body:*`/`annex:*`.
   - `_CONFLICT_REASON` (không chứa tên nhãn): "AI2 gợi ý hai khoản có thể quy định khác nhau cho cùng một nội dung (mô hình ngôn ngữ đề xuất, trích dẫn đã được kiểm); cần người duyệt đối chiếu, AI2 không kết luận khoản nào được áp dụng."
   - `limited_coverage_issue(result) -> EvidenceIssue` (Q2): `issue_id="contract-graph:CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE"`, `missing="CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE"`, `review_state=NEEDS_REVIEW`, `reason` tiếng Việt theo `rule_only_reason` (vd `NO_CONSENT`: "Chưa có đồng ý chia sẻ nội dung hợp đồng cho mô hình ngôn ngữ; quan hệ ngầm giữa các khoản chưa được phân tích ({n} cặp ứng viên). Không có phát hiện không có nghĩa là không có rủi ro.") — không chứa tên nhãn.
   - GENERAL_SPECIFIC/DUPLICATE/REFERENCE không sinh finding/candidate.
   - `pair_coverage(result, *, status, conflict_stats) -> dict`: `{"graph_mode": "operation_first+pairs_llm" | "operation_first+pairs_rule_only" | "operation_first" (status ≠ OK), "pairs": {status, mode, rule_only_reason, classifier_model, prompt_version, candidates_total, candidates_by_source, candidates_kept, candidates_capped, excluded_luong1, excluded_external_ref, pairs_sent, pairs_unclassified, llm_calls, prompt_tokens, completion_tokens, injection_signals, relations_total, relations_by_label, rejected, stopped_reason, batches_completed, conflict_findings, conflict_capped, conflict_deduped_with_candidates, conflict_citation_invalid}}` — khoá cố định, 0 khi FAILED/SKIPPED.
6. **Bảng** (D3):
   - `ai-service/app/db/migrations/versions/0006_ai2_contract_pair_relations.py` (`revision = "0006_ai2_contract_pair_relations"`, `down_revision = "0005_ai2_contract_edges"`), cột tường minh: `tenant_id`, `dossier_id`, `relation_id` (PK 3 cột), `job_id`, `source_snapshot_digest`, `label` (CHECK `ck_ai2_contract_pair_relations_label` IN 4 nhãn), `directed` int, `node_a_id`, `node_b_id`, `candidate_sources_json`, `span_a`, `span_b`, `citation_a_json`, `citation_b_json`, `classifier_model`, `prompt_version`, `review_state`, `digest`, `created_ms` bigint; index `idx_ai2_contract_pair_relations_job (tenant_id, dossier_id, job_id)`; `downgrade()` chỉ drop của revision này.
   - `tables.py`: `CONTRACT_PAIR_LABELS`, `contract_pair_relations` trên `graph_metadata`.
   - `ai-service/app/tools/pair_relation_store.py`: `relation_digest`, `relation_row` (lọc `\x00`; import `_canonical`, `_clean`, `_citation_json` từ `contract_edge_store.py:21-38`), `replace_pair_relations(cx, *, tenant_id, dossier_id, job_id, relations, now_ms)` (DELETE + INSERT, không commit).
   - `jobs.py`: sau `:575-576`: `if getattr(record, "pair_relations_ran", False): self._replace_pair_relations(cx, record, job_id)` — savepoint riêng, lỗi ⇒ log `ai2.contract_pair_relations_write_failed … exc_info=True`, job vẫn `SUCCEEDED`, dòng cũ giữ. `SQLiteJobStore` không đổi.
7. **Test luồng 1 hard-code head** (RT-06, R12):
   - `tests/test_contract_graph_edge_store.py::test_0005_is_the_single_head_after_0004` → đổi tên `test_migration_chain_has_single_head`: `script.get_heads()` có đúng 1 phần tử; chuỗi `0006_ai2_contract_pair_relations → 0005_ai2_contract_edges → 0004_ai2_job_indexes` qua `down_revision`.
   - `tests/test_contract_graph_postgres_store.py`: `NEW_HEAD` = `ScriptDirectory.get_current_head()` (mẫu `tests/test_ai2_postgres_store.py:460, 612`); sau `downgrade 0004_ai2_job_indexes` tập bảng = `before - {"contract_edges", "contract_pair_relations"}`.
8. **Doc** — `docs/ai2/AI2-20-contract-graph-pairs.vi.md`: mục tiêu; cờ + quan hệ cờ luồng 1; env (`_PAIRS_MODEL`, `_PAIRS_BASE_URL`, `_PAIRS_API_KEY` — không ghi giá trị); cổng D5 + bảng lý do rule-only + issue độ phủ hạn chế; consent = `policy_flags.egress_allowed` + DEC; 4 nhãn + hướng; đường ra D8 + **ánh xạ BE**: CONFLICT ⇒ finding `semantic`, `disposition=comparable_difference`, severity `high` (`persistence.py:1095`), `key_or_topic` = `item_key` (`:1087`), tối đa 5/hồ sơ; coverage before/after (JSON thật từ fixture); bảng; ngữ nghĩa thay dòng RT-14; chống injection; ngân sách; **runbook rollback RT-11**; giới hạn; §Số đo (P5 điền). `docs/ai2/README.md` thêm mục lục; `docs/system-architecture.md` thêm đoạn "Contract graph (luồng 2, phân loại cặp) — sau cờ".

### Phi chức năng

- Pairs tắt (hoặc cờ luồng 1 tắt) ⇒ không import module `pair_*`; output byte-identical với golden tương ứng.
- Pairs bật rule-only ⇒ khác golden graph-on chỉ ở những gì `--strip-pairs` loại (§1).
- Không field Pydantic mới trên `JobResult`/`IndexContribution`/wire; `ProcessingPolicyFlags` không đổi.
- Lỗi pairs không làm FAILED job hay đổi output luồng 1.

## Files — file inventory

| Hành động | Path | Cỡ ước tính | Ảnh hưởng test |
|---|---|---|---|
| Modify | `ai-service/scripts/capture_idp_golden.py` | +~70 dòng | 2 test golden |
| Create | `ai-service/fixtures/contract_graph/idp_graph_on_golden.json` | sha/case + case đầy đủ | `test_contract_graph_pairs_flag_regression.py` |
| Modify | `ai-service/app/pipeline/idp.py` | +~45 dòng quanh `:281`, `:361-362`, `:393`, `:434` | 25 file test gọi `run_idp` + 2 golden |
| Modify | `ai-service/app/tools/store.py` | +3 field | golden (record) |
| Modify | `ai-service/app/pipeline/ai1_snapshot_adapter.py` | +1 dòng sau `:170` | consent, `tests/test_processing_wire_contract.py` |
| Create | `ai-service/app/pipeline/contract_graph/pair_projection.py` | ~160 dòng | `test_contract_graph_pair_projection.py` |
| Create | `ai-service/app/db/migrations/versions/0006_ai2_contract_pair_relations.py` | ~65 dòng | Postgres + chuỗi migration |
| Modify | `ai-service/app/db/tables.py` | +~12 dòng | store tests |
| Create | `ai-service/app/tools/pair_relation_store.py` | ~80 dòng | store tests |
| Modify | `ai-service/app/tools/jobs.py` | +~18 dòng sau `:576` | Postgres |
| Create | `ai-service/fixtures/contract_graph_pair_records.py` | ~240 dòng: (a) thân + phụ lục **file riêng**; (b) **phụ lục nhúng cùng file** (`page_revision_id` cùng `source_file_id`); cặp chung–riêng, mâu thuẫn, cụm "nêu trên", dẫn chiếu "Luật Thương mại", câu thao tác luồng 1, khoản có câu injection; `FakePairLLM` (JSON theo `id`, đếm lời gọi, có `served_model`) | integration/wire/store/golden |
| Create | `ai-service/tests/test_contract_graph_pairs_flag_regression.py` | ~8 test | mới |
| Create | `ai-service/tests/test_contract_graph_pairs_idp_integration.py` | ~15 test | mới |
| Create | `ai-service/tests/test_contract_graph_pairs_consent.py` | ~4 test | mới |
| Create | `ai-service/tests/test_contract_graph_pair_projection.py` | ~11 test | mới |
| Create | `ai-service/tests/test_contract_graph_pairs_wire.py` | ~4 test | mới |
| Create | `ai-service/tests/test_contract_graph_pair_store.py` | ~5 test | mới |
| Create | `ai-service/tests/test_contract_graph_pairs_postgres_store.py` | ~7 test | mới |
| Modify | `ai-service/tests/test_contract_graph_edge_store.py` | head động + chuỗi (RT-06) | suite mặc định |
| Modify | `ai-service/tests/test_contract_graph_postgres_store.py` | head động + tập bảng | Postgres |
| Create | `docs/ai2/AI2-20-contract-graph-pairs.vi.md` | ~200 dòng | — |
| Modify | `docs/ai2/README.md` | +1 dòng | — |
| Modify | `docs/system-architecture.md` | +1 đoạn | — |

Hơn 8 file: số phase khoá 5; tách P4 sẽ phải capture golden graph-on hai lần và chia đôi `idp.py`/`store.py` mà không giảm rủi ro; module mới một trách nhiệm, test 1:1.

## Implementation Steps

1. **Khoá golden trước** (chưa sửa `idp.py`, `store.py`, adapter): viết fixture `contract_graph_pair_records.py`; sửa `capture_idp_golden.py`; viết `test_contract_graph_pairs_flag_regression.py`; capture `--profile graph_on` (`PYTHONHASHSEED=0`); capture `flag_off` vào thư mục tạm ⇒ bytes bằng file commit; test khoá PASS.
2. Viết test RED còn lại → FAIL.
3. `store.py` + adapter → golden vẫn xanh.
4. `pair_projection.py`.
5. Sửa `idp.py` (§4) → 2 golden + test pairs-off xanh; test rule-only + review-id (phụ lục nhúng) xanh.
6. Migration `0006` + `tables.py` + `pair_relation_store.py` + `jobs.py`; sửa 2 test head (§7) → suite mặc định xanh (gồm `test_migration_chain_has_single_head`).
7. Postgres với `AI2_REQUIRE_DOCKER=1` + `AI2_TEST_DATABASE_URL`: `pytest -q tests/test_contract_graph_pairs_postgres_store.py tests/test_contract_graph_postgres_store.py tests/test_ai2_postgres_store.py`. Không có ⇒ BLOCKED, không PASS.
8. Doc AI2-20 + README + system-architecture.
9. Regression gate → commit phase. Nhắc main ghi DEC Q1 (§DEC cần ghi trong plan.md) trước merge.

## TDD

### Tests Before (PASS-khoá / RED)

`ai-service/tests/test_contract_graph_pairs_flag_regression.py` (subprocess `--emit-shas`, `PYTHONHASHSEED=0`)
- [ ] `test_flag_off_capture_reproduces_committed_file`.
- [ ] `test_pairs_flag_alone_matches_flag_off_golden`.
- [ ] `test_graph_on_pairs_unset_matches_graph_on_golden`.
- [ ] `test_graph_on_pairs_false_values_match_graph_on_golden` (`""`, `"0"`, `"false"`, `"off"`).
- [ ] `test_graph_on_golden_records_seed_python_and_cases` — có `contract_graph.graph_record`, `contract_graph.pair_record_embedded`; lệch seed ⊆ `HASHSEED_SENSITIVE`.
- [ ] `test_pairs_rule_only_differs_only_by_stripped_fields` (RED tới bước 5) — `PAIRS=1`, không `llm` ⇒ `--strip-pairs` == golden graph-on mọi case; `review_state` cấp job ∈ {giá trị golden, `NEEDS_REVIEW`}; case `pair_record_embedded`: `graph_mode == "operation_first+pairs_rule_only"`, `pairs.rule_only_reason == "NO_CONSENT"`, issue `CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE` là phần tử **cuối** `evidence_issues`.
- [ ] `test_pairs_off_does_not_import_pair_modules`.

`ai-service/tests/test_contract_graph_pairs_consent.py`
- [ ] `test_adapter_maps_egress_allowed_to_consent` (`True`/`False`/vắng ⇒ `True`/`False`/`False`).
- [ ] `test_consent_not_in_record_to_dict`.
- [ ] `test_policy_flags_contract_unchanged` — `ProcessingPolicyFlags.model_fields` == `{"egress_allowed","use_vector","budget_limits"}`; khoá lạ vẫn bị từ chối.
- [ ] `test_consent_default_false_for_non_adapter_records`.

`ai-service/tests/test_contract_graph_pair_projection.py`
- [ ] `test_conflict_becomes_comparable_difference_needs_review`.
- [ ] `test_conflict_evidence_is_whole_node_citation` (RT-10) — `evidence_left[0].text_span` = text cả node (không phải span LLM), `validation_status == "VALID"`.
- [ ] `test_conflict_findings_capped_per_dossier` (RT-10) — 8 CONFLICT ⇒ 5 candidate, `conflict_capped == 3`, giữ theo thứ tự ứng viên.
- [ ] `test_conflict_deduped_against_existing_candidate_pair`.
- [ ] `test_general_specific_duplicate_reference_emit_no_candidate`.
- [ ] `test_scope_from_parts` (body/body, annex/annex, body/annex).
- [ ] `test_item_key_is_canonical_address_pair`.
- [ ] `test_candidate_id_stable`.
- [ ] `test_reason_and_issue_texts_have_no_label_tokens`.
- [ ] `test_limited_coverage_issue_per_reason` (Q2, parametrize 6 lý do) — `NEEDS_REVIEW`, id cố định.
- [ ] `test_pair_coverage_keys_fixed_and_failed_zero` + `test_graph_mode_values`.

`ai-service/tests/test_contract_graph_pairs_idp_integration.py` (`contract_graph_pair_records` + `FakePairLLM`)
- [ ] `test_no_consent_is_rule_only_without_llm_call_and_one_issue` (Q2) — `FakePairLLM.calls == 0`; đúng 1 issue `CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE` ở cuối; `pairs.candidates_kept > 0`.
- [ ] `test_consent_llm_mode_emits_relations_and_conflict_candidate` — GENERAL_SPECIFIC (a = khoản chung) + CONFLICT; `cand_pair_*` là phần tử cuối `contribution.candidates`; không issue LIMITED_COVERAGE; mọi `NEEDS_REVIEW`.
- [ ] `test_rule_only_reasons_in_coverage` (egress tắt / `llm=None` không env pairs / model trống / hết lời gọi / hạn).
- [ ] `test_existing_review_item_ids_prefix_preserved_separate_file`.
- [ ] `test_existing_review_item_ids_prefix_preserved_embedded_annex` (RT-03) — hồ sơ phụ lục **nhúng cùng file** có CONFLICT: danh sách `review_item_id` khi pairs tắt là tiền tố đúng thứ tự khi pairs bật.
- [ ] `test_conflict_candidate_adds_no_context_finding` (RT-03) — `contract_context.findings` giống hệt giữa pairs tắt/bật trên hồ sơ nhúng.
- [ ] `test_pairs_do_not_change_relation_pairs_or_fact_candidates`.
- [ ] `test_pairs_builder_failure_is_issue_not_job_failure` — issue `CONTRACT_GRAPH_PAIRS_FAILED` cuối, `pairs.status == "FAILED"`, `pair_relations_ran is False`, cạnh luồng 1 không đổi.
- [ ] `test_graph_failure_skips_pairs`.
- [ ] `test_llm_calls_counted_in_runtime_snapshot`.
- [ ] `test_ran_semantics` (RT-14, parametrize) — LLM ≥1 lô ⇒ `True`; `NO_CONSENT` ⇒ `True` + list rỗng; `EGRESS_DENIED`/`MODEL_UNSET`/`BUDGET_EXHAUSTED`/`DEADLINE` ⇒ `False`; `LLM_FALLBACK` trước lô đầu ⇒ `False`.
- [ ] `test_pairs_flag_read_once_per_run`.
- [ ] `test_injection_clause_counted_and_cannot_fabricate` — khoản injection trong hồ sơ ⇒ `pairs.injection_signals ≥ 1`, cặp có trong prompt; `FakePairLLM` "nghe lời" không tạo được quan hệ.
- [ ] `test_external_law_reference_not_a_candidate` — "khoản 2 Điều 7 Luật Thương mại" không thành cặp.
- [ ] `test_kafka_and_http_share_adapter_consent`.

`ai-service/tests/test_contract_graph_pairs_wire.py`
- [ ] `test_wire_validates_with_pairs_llm_mode`.
- [ ] `test_pair_labels_only_inside_coverage` (positive control: coverage có khớp).
- [ ] `test_conflict_reaches_findings_as_comparable_difference` — `finding_type == "COMPARABLE_DIFFERENCE"`, `review_state == "NEEDS_REVIEW"`, citation 2 phía có `source_file_id`, `item_key` không rỗng.
- [ ] `test_general_specific_not_in_context_findings`.

`ai-service/tests/test_contract_graph_pair_store.py`
- [ ] `test_relation_row_columns_match_table`.
- [ ] `test_relation_row_strips_nul`.
- [ ] `test_relation_digest_stable`.
- [ ] `test_sqlite_store_ignores_pairs`.
- [ ] `test_check_constraint_labels_match_enum`.

`ai-service/tests/test_contract_graph_edge_store.py` (sửa, RT-06)
- [ ] `test_migration_chain_has_single_head` — 1 head; chuỗi `0006 → 0005 → 0004`.

`ai-service/tests/test_contract_graph_pairs_postgres_store.py` (`AI2_REQUIRE_DOCKER=1`)
- [ ] `test_fresh_database_migrates_to_head_with_pair_relations`.
- [ ] `test_0006_downgrade_entrypoint_then_upgrade` — `python -m app.db.migrate downgrade 0005_ai2_contract_edges` ⇒ chỉ mất `contract_pair_relations`.
- [ ] `test_completion_replaces_pair_relations_for_latest_success`.
- [ ] `test_older_job_completion_does_not_overwrite_newer_relations`.
- [ ] `test_ran_false_leaves_relations_untouched`.
- [ ] `test_pair_write_failure_keeps_job_succeeded_and_edges_written`.
- [ ] `test_check_constraint_rejects_unknown_label`.

### Implement

Theo Implementation Steps 3–8.

### Tests After

- [ ] Hai golden xanh sau bước 5 và 6; sha golden graph-on không đổi từ bước 1; sha golden flag-off == bản `83f2d75`.
- [ ] `tests/test_contract_graph_edge_store.py` (đã sửa) xanh trong suite mặc định; Postgres tests xanh hoặc BLOCKED ghi rõ.
- [ ] Mọi test luồng 1 khác xanh **không sửa** (chỉ 2 file ở §7 được sửa).

### Regression Gate

- ai-service (từ `ai-service/`): lệnh ở `plan.md` §Acceptance — đúng 13 lỗi môi trường.
- Postgres: `AI2_REQUIRE_DOCKER=1 AI2_TEST_DATABASE_URL=<postgres 16>` cho 3 file (bước 7).
- Harness (repo root): lệnh ở `plan.md` §Acceptance.
- Focused: `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q tests/test_contract_graph_*.py tests/test_processing_wire_contract.py tests/test_a8_env_flags.py tests/test_contract_context.py`.
- Lint: `uv run --frozen --extra dev ruff check` mọi `.py` mới/sửa.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Cờ tắt mà bytes đổi | `test_flag_off_capture_reproduces_committed_file`, `test_pairs_flag_alone_matches_flag_off_golden`, `test_graph_on_pairs_unset_matches_graph_on_golden`, `test_pairs_off_does_not_import_pair_modules` |
| Critical | CONFLICT sinh `CONTEXT_CONFLICT` và dịch review id luồng 1 (RT-03) | `test_existing_review_item_ids_prefix_preserved_embedded_annex`, `test_conflict_candidate_adds_no_context_finding` |
| Critical | Rule-only đổi output ngoài phần cho phép | `test_pairs_rule_only_differs_only_by_stripped_fields` |
| Critical | Gọi LLM khi không consent | `test_no_consent_is_rule_only_without_llm_call_and_one_issue`, `test_rule_only_reasons_in_coverage` |
| Critical | Nhãn luồng 2 lộ ra BE / sai nghĩa | `test_pair_labels_only_inside_coverage`, `test_general_specific_not_in_context_findings`, `test_reason_and_issue_texts_have_no_label_tokens` |
| Critical | Đổi request contract | `test_policy_flags_contract_unchanged` |
| Critical | Lỗi pairs làm FAILED job / hỏng luồng 1 | `test_pairs_builder_failure_is_issue_not_job_failure`, `test_pair_write_failure_keeps_job_succeeded_and_edges_written` |
| Critical | Suite mặc định đỏ vì head mới (RT-06) | `test_migration_chain_has_single_head` |
| High | Evidence do LLM chọn / BE ngập finding high (RT-10) | `test_conflict_evidence_is_whole_node_citation`, `test_conflict_findings_capped_per_dossier` |
| High | Sự cố provider xoá quan hệ (RT-14) | `test_ran_semantics` |
| High | Thiếu cảnh báo độ phủ hạn chế (Q2) | `test_limited_coverage_issue_per_reason`, `test_no_consent_is_rule_only_without_llm_call_and_one_issue` |
| High | LLM output mở khoá so sánh fact | `test_pairs_do_not_change_relation_pairs_or_fact_candidates` |
| High | Job cũ ghi đè job mới | `test_older_job_completion_does_not_overwrite_newer_relations` |
| Medium | Wire lệch schema | `test_wire_validates_with_pairs_llm_mode` |
| Medium | NUL trong span | `test_relation_row_strips_nul` |

## Success

- [ ] Golden graph-on capture trước khi sửa `idp.py` (sha trong `verification-P4.json`), không đổi sau đó; golden flag-off không đổi sha.
- [ ] Mọi test P4 xanh; hai suite xanh (đúng 13 lỗi môi trường); ruff sạch.
- [ ] Migration 0006 up/down(entrypoint)/up chạy thật — hoặc BLOCKED, không PASS.
- [ ] Wire validate; nhãn chỉ trong coverage; CONFLICT ra `findings` `COMPARABLE_DIFFERENCE` `NEEDS_REVIEW`, ≤5/hồ sơ, evidence cả node.
- [ ] Doc AI2-20 commit (JSON coverage thật, runbook RT-11, ánh xạ severity BE).

## Risks

| Rủi ro | L × I | Xử lý |
|---|---|---|
| Golden graph-on capture sau khi đã sửa `idp.py` | Trung bình × Cao | Bước 1 bắt buộc trên code P3; kiểm chéo bằng `git worktree add <tmp> <commit P3>` cùng seed + interpreter |
| Field dataclass đổi bytes qua `dataclasses.asdict` `[ASSUMED: không có]` | Thấp × Cao | Golden phủ `record_to_dict`; grep `asdict(` ở bước 3, ghi kết quả |
| Issue LIMITED_COVERAGE làm job PASS thành NEEDS_REVIEW | Chắc chắn (khi cờ bật) × Thấp | Đúng ý Q2; chỉ khi cờ bật; test ghi rõ |
| Không có Postgres trên máy cook | Cao × Cao | BLOCKED (R11) |
| Dòng cũ còn sau khi tắt cờ | Chắc chắn × Thấp | Ghi giới hạn trong AI2-20; `NO_CONSENT` xoá dòng |

## Rollback

Runbook (RT-11; `migrate()` chạy ở lần dùng DB đầu của **mỗi** process, `engine.py:39-44`):
1. Dừng/scale về 0 **mọi** process chạy code P4: API, Kafka worker, `ai2_batch`, job định kỳ.
2. Từ `ai-service/` với `AI2_DATABASE_URL`: `python -m app.db.migrate downgrade 0005_ai2_contract_edges` (drop `ai2.contract_pair_relations`, `alembic_version` về 0005).
3. `git revert <commit P4>`, deploy code cũ, rồi mới khởi động process.
Rollback nóng không cần deploy: để `AI2_CONTRACT_GRAPH_PAIRS_ENABLED` tắt (golden graph-on bảo đảm output = luồng 1).
