---
phase: 4
title: "Edge Storage"
status: pending
plan: 261007-1735-ai2-contract-graph-op-first
created: 2026-10-07
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 4 — Edge Storage

## Overview

Đưa cạnh của P3 ra ngoài theo đúng contract hiện có và lưu bền:
1. **Wire**: mỗi cạnh → `context_finding` với `relation_type="AMENDS"` (K3, D5); số liệu graph → một key `index_contribution.coverage.contract_graph` (D6). Không chuỗi loại con nào xuất hiện ngoài coverage.
2. **Lưu trữ**: bảng `ai2.contract_edges` (migration `0005`, có downgrade), ghi trong cùng transaction hoàn tất job của `PostgresJobStore` nhưng **cô lập bằng savepoint** — lỗi ghi cạnh không làm FAILED job (D7, RT-04); cạnh đi qua `DossierRecord.contract_edges` (D8).
3. **Rollback chạy được**: entrypoint `python -m app.db.migrate downgrade <revision>` có test (D18, RT-03).
4. **Tài liệu**: `docs/ai2/AI2-19-contract-graph-operation-first.vi.md`.

Flag tắt: không key coverage mới, không finding mới, không câu SQL mới — golden P3 phải còn xanh.

## Dependency map

- Phụ thuộc P3: `ContractEdge`, `ContractGraphResult`, `EdgeOp` (`ai-service/app/contracts/contract_graph.py`); biến `graph` (và trạng thái lỗi) trong `run_idp`; golden `ai-service/fixtures/contract_graph/idp_flag_off_golden.json` (chỉ đọc).
- Điểm chạm đã đọc:
  - `run_idp`: `build_contract_context` (`ai-service/app/pipeline/idp.py:306`), `context_issues` (`idp.py:307-318`), `coverage={...}` truyền vào `IndexStore.propose` (`idp.py:327-338`), `record.events = events` (`idp.py:344`), `mem.put(record)` (`idp.py:356`).
  - Wire: `job_result_to_wire` chép `contract_context.findings` thành `context_findings` (`ai-service/app/contracts/wire.py:308-324`) và `coverage` nguyên trạng (`wire.py:368`); tự validate (`wire.py:389`).
  - BE: `_context_findings_as_items` (`backend/src/contract_intelligence/shared/ai/persistence.py:791`) bỏ finding `review_state` ngoài `{None, NEEDS_REVIEW, INSUFFICIENT_EVIDENCE}` (`:811`), bỏ finding có `metadata.candidate_id`, cần citation từ ≥2 tài liệu (`:825`), map `relation_type == "AMENDS"` → `candidate_amendment` (`:834`). BE đọc coverage là dict (`:193`), chỉ dùng key `input` (`:171`) — không va `contract_graph`.
  - Job store: `PostgresJobStore.complete_with_snapshot` (`ai-service/app/tools/jobs.py:535-573`) — advisory lock theo `(tenant, dossier)`, fence `worker_token`, chỉ upsert snapshot khi job là SUCCEEDED mới nhất. `SQLiteJobStore.complete_with_snapshot` (`jobs.py:395-403`) không đổi. Gọi duy nhất từ `ai-service/app/api/main.py:302` (OBSERVED grep) ⇒ Kafka worker và `ai2_batch.py` không ghi bảng (đúng phạm vi).
  - Migration: `0001_ai2_initial.py:13` `metadata.create_all(cx)` (lý do D9); head hiện tại `0004_ai2_job_indexes` (`ai-service/app/db/migrations/versions/0004_ai2_job_indexes.py:4-5`); `migrate()` chỉ chạy `upgrade head` dưới advisory lock (`ai-service/app/db/migrate.py:16-35`, `command.upgrade(config, "head")` ở `:29`), được gọi từ `ensure_database` ở lần dùng DB đầu tiên của mỗi engine (`ai-service/app/db/engine.py:39-44`). `env.py:5` đọc `context.config.attributes["connection"]` ⇒ CLI `alembic` không chạy được (red-team OBSERVED `alembic current` → `KeyError: 'connection'`); mọi lệnh Alembic phải đi qua code path của `migrate.py`. Revert file 0005 khi DB đã ở 0005 ⇒ `upgrade head` ném `CommandError: Can't locate revision identified by '0005_ai2_contract_edges'` (red-team OBSERVED trên env Alembic tạm) ⇒ hỏng boot mọi đường Postgres.
  - Savepoint có tiền lệ trong repo: `cx.begin_nested()` ở `ai-service/app/db/migrate.py:57,70` (lỗi pgvector không làm hỏng transaction migration).
  - Worker boundary: exception thoát khỏi `complete_with_snapshot` bị bắt ở `ai-service/app/api/main.py:319` rồi `main.py:328-336` gọi `set_wire(status="FAILED")` với `worker_token` còn hiệu lực ⇒ BE nhận job FAILED/`AI2_WORKER_FAILED` dù trích xuất đã xong (lý do RT-04).
  - Test Postgres hiện có hardcode head: `ai-service/tests/test_ai2_postgres_store.py:612` `assert version == "0004_ai2_job_indexes"` (trong `test_job_indexes_back_sweep_and_latest_success_queries`, `:584`); mẫu đúng là so với script head như `_ai2_state` (`:444-460`). CI ai-service không chạy pytest (`.github/workflows/ai-service.yml:23-24` chỉ `echo`) nên lỗi chỉ lộ khi có Postgres (RT-11).
  - Fixture `pg_url` là `scope="session"` (`ai-service/tests/conftest.py:11-29`) ⇒ test downgrade dùng chung DB với test khác, phải trả DB về head khi kết thúc.
  - `DossierRecord` dataclass (`ai-service/app/tools/store.py:24-54`); `record_to_dict` liệt kê field tường minh (`ai-service/app/tools/persist.py:55-80`); không có `asdict(DossierRecord)` trong `app/` (OBSERVED grep) ⇒ thêm field không đổi serialization.

## Requirements

### Chức năng

1. **Projection** — `ai-service/app/pipeline/contract_graph/projection.py`:
   - `edge_findings(edges, candidates) -> list[ContextFinding]`: `finding_id = "contract-graph:" + edge.edge_id`; `kind="AMENDMENT_SIGNAL"`; `relation_type=RelationType.AMENDS` cho **cả 5** op; `subject_key=edge.target_address`; `source_node_ids=[source, target]`; `reason` một câu chung cho mọi loại, không nêu loại con (vd "AI2 phát hiện quan hệ sửa đổi tới {địa chỉ}; cần người duyệt đối chiếu hai phía."); `review_state=edge.review_state`; `citations=[source_citation, target_citation]`.
   - `metadata` (D5, RT-07): nếu có candidate mà cặp node fact khớp cặp node của cạnh — tức `tuple(sorted((c.evidence_left[0].node_id, c.evidence_right[0].node_id))) == tuple(sorted((edge.source_node_id, edge.target_node_id)))`, cùng khoá mà `compare.py:188-193` dùng để mở cặp — thì `metadata={"candidate_id": c.candidate_id}` (candidate đầu tiên theo thứ tự `candidates`); ngược lại `metadata={}`. Lý do: BE bỏ context finding có `metadata.candidate_id` (`persistence.py:815`), nên cặp thân↔phụ lục mà cạnh đã mở khoá chỉ còn **một** hàng review (candidate) thay vì hai (`persistence.py:1047-1050` gộp cả hai). Cùng quy ước `contract_context.py:272` (`CONTEXT_CONFLICT`). `candidate_id` (`cand_…`) không chứa chuỗi loại con nên không vi phạm K3.
   - `graph_coverage(result, *, failed=False) -> dict`: `{"graph_mode": "operation_first", "status": "OK"|"FAILED", "edges_total", "edges_by_op": {đủ 5 op, kể cả 0}, "unresolved_targets", "ambiguous_targets", "implicit_edges", "auto_pass_enabled", "truncated"}`.
2. **`run_idp`** — `idp.py` (chỉ khi flag bật, dùng `graph` của P3, import lười):
   - Sau `idp.py:306`, trước comprehension `context_issues` (`idp.py:307`): `contract_context.findings.extend(edge_findings(graph.edges, candidates))` ⇒ `idp.py:307-318` tự sinh issue/review item cho cạnh như `AMENDMENT_SIGNAL` cũ; các issue này nằm cuối `context_issues`, trước issue graph mà P3 append sau `idp.py:318` ⇒ tiền tố id review cũ vẫn giữ (D4).
   - Coverage: thêm `coverage["contract_graph"] = graph_coverage(...)` (key cuối, sau `runtime`). Builder lỗi ⇒ `status="FAILED"`, số đếm 0.
   - Sau `idp.py:344`: `record.contract_edges = list(graph.edges)`; `record.contract_graph_ran = True` (lỗi ⇒ giữ `False` để không xoá cạnh cũ trong DB).
3. **`DossierRecord`** — `store.py`: thêm `contract_edges: list[ContractEdge] = field(default_factory=list)`, `contract_graph_ran: bool = False`. Không thêm vào `record_to_dict`/`record_from_dict`. `ContractEdge` import dưới `if TYPE_CHECKING:` (file đã có `from __future__ import annotations`, `store.py:1`) ⇒ flag tắt không import module mới.
4. **Migration** — `0005_ai2_contract_edges.py` (`revision="0005_ai2_contract_edges"`, `down_revision="0004_ai2_job_indexes"`):
   - `op.create_table("contract_edges", schema="ai2")` với cột khai báo **tường minh** (không dùng `metadata`): `tenant_id`, `dossier_id`, `edge_id`, `job_id`, `source_snapshot_digest`, `op`, `source_node_id`, `target_node_id`, `anchor_node_id?`, `target_address`, `method`, `support`, `standard` (int 0/1), `implicit` (int 0/1), `review_state`, `source_citation_json`, `target_citation_json`, `new_text?`, `scope_text?`, `digest`, `created_ms` (bigint); PK `(tenant_id, dossier_id, edge_id)`; `CHECK op IN ('INSERTION','SUBSTITUTION','REPEAL','REJECTION','SCOPE_LIMIT')`; index `(tenant_id, dossier_id, job_id)`.
   - `downgrade()`: drop index + drop table (chỉ bảng này; khác `0001` vốn chặn downgrade).
5. **Khai báo bảng** — `tables.py`: `graph_metadata = MetaData(schema="ai2")`; `contract_edges = Table(..., graph_metadata, ...)` cùng cột với migration, kèm comment vì sao tách metadata (D9).
6. **Store** — `ai-service/app/tools/contract_edge_store.py`:
   - `edge_digest(edge) -> str`: sha256 JSON chuẩn (`sort_keys`) của `edge.model_dump(mode="json")`.
   - `edge_row(edge, *, tenant_id, dossier_id, job_id, now_ms) -> dict`.
   - `replace_contract_edges(cx, *, tenant_id, dossier_id, job_id, edges, now_ms) -> int`: `DELETE` theo `(tenant_id, dossier_id)` rồi `INSERT` toàn bộ, trên connection/transaction được truyền vào (không tự commit).
7. **Ghi trong transaction, cô lập bằng savepoint (RT-04)** — `jobs.py` `PostgresJobStore.complete_with_snapshot`: trong nhánh `status == "SUCCEEDED" and latest == job_id`, sau upsert snapshot: nếu `getattr(record, "contract_graph_ran", False)` ⇒ `with cx.begin_nested(): replace_contract_edges(cx, ...)` (tiền lệ `migrate.py:57,70`). Lỗi ghi cạnh ⇒ chỉ savepoint rollback; `log.warning` + job vẫn hoàn tất SUCCEEDED với snapshot mới; cạnh cũ trong DB giữ nguyên. `edge_row` lọc `\x00` khỏi mọi cột text (Postgres từ chối NUL trong `text`).
8. **Entrypoint downgrade (RT-03)** — `ai-service/app/db/migrate.py`: thêm `downgrade(engine, revision)` dùng cùng `Config`/connection như `migrate()` (CLI `alembic` không chạy được vì `env.py:5` cần `connection` truyền vào) và `if __name__ == "__main__"`: `python -m app.db.migrate downgrade <revision>` đọc `AI2_DATABASE_URL`.
9. **Test hardcode head (RT-11)** — `ai-service/tests/test_ai2_postgres_store.py:612`: thay `"0004_ai2_job_indexes"` bằng head lấy từ `ScriptDirectory` (mẫu `_ai2_state`, `:444-460`).
10. **Tắt `AMENDMENT_SIGNAL` cũ khi flag bật + chống trùng (RT-07, quyết định Q3 của người dùng 2026-10-08)** —
    - `contract_context.py:211-217`: `build_contract_context(..., suppress_amendment_signal: bool = False)`; khi `True` thì không phát finding `AMENDMENT_SIGNAL` cấp phụ lục. `idp.py:306` truyền `True` **chỉ khi** flag bật **và** builder P3 chạy thành công (builder chạy trước, ở `idp.py:278`). Flag tắt ⇒ tham số mặc định `False`, đường cũ không đổi (golden P3 bảo đảm).
    - Trong `edge_findings`: bỏ cạnh mà `(source_node_id, target_node_id)` đã có candidate `CANDIDATE_AMENDMENT` cũ (`compare.py`) trỏ cùng cặp node; đếm vào `coverage.contract_graph.deduped_with_legacy`. Cạnh vẫn được ghi bảng.
    - Nếu graph builder lỗi (coverage `failed`) thì **giữ** `AMENDMENT_SIGNAL` cũ để không mất tín hiệu.
11. **Tài liệu** — `docs/ai2/AI2-19-contract-graph-operation-first.vi.md`: mục tiêu, flag + giá trị mặc định, 5 loại cạnh ↔ Akoma Ntoso `textualMod`/`scopeMod`, ánh xạ ra BE (`AMENDS`) và hệ quả lọc phía BE (`persistence.py:811,825`), schema `coverage.contract_graph` (before/after), bảng `ai2.contract_edges` + migration/downgrade, cổng PASS và vì sao đang đóng, link 3 báo cáo đo, giới hạn (VBQPPL ≠ phụ lục hợp đồng, Kafka/batch không ghi bảng). Thêm 1 dòng chỉ mục vào `docs/ai2/README.md`.

### Phi chức năng

- Flag tắt: không SQL mới, không key/finding mới (golden P3).
- Idempotent: retry cùng snapshot ⇒ cùng `edge_id`/`digest`; replace theo dossier ⇒ không trùng dòng.
- Bảng chỉ phản ánh **job SUCCEEDED mới nhất có chạy graph**; mỗi dòng mang `job_id` + `source_snapshot_digest` để consumer tương lai tự phát hiện cũ (flag tắt sau khi từng bật ⇒ dòng cũ còn, có `job_id` cũ).
- Không bảng SQLite (D7).

## Files — file inventory

| Hành động | Path | Cỡ ước tính | Ảnh hưởng test |
|---|---|---|---|
| Create | `ai-service/app/db/migrations/versions/0005_ai2_contract_edges.py` | ~45 dòng | `test_contract_graph_postgres_store.py`; `test_ai2_postgres_store.py::test_migrations_stay_inside_ai2_and_are_repeatable` phải còn xanh |
| Modify | `ai-service/app/db/tables.py` | +~20 dòng (metadata riêng) | postgres tests |
| Create | `ai-service/app/tools/contract_edge_store.py` | ~70 dòng | `test_contract_graph_edge_store.py`, postgres tests |
| Modify | `ai-service/app/tools/jobs.py` | +~8 dòng trong `PostgresJobStore.complete_with_snapshot` (savepoint) | `test_ai2_postgres_store.py` (fence/snapshot) phải còn xanh |
| Modify | `ai-service/app/pipeline/contract_context.py` | +~3 dòng quanh `:211` (điều kiện flag) | golden P3 (flag tắt không đổi), `test_contract_graph_projection.py` |
| Modify | `ai-service/app/db/migrate.py` | +~25 dòng (`downgrade()` + `__main__`) | `test_contract_graph_postgres_store.py::test_0005_downgrade_entrypoint_then_upgrade` |
| Modify | `ai-service/tests/test_ai2_postgres_store.py` | `:612` so với script head (RT-11) | chính nó |
| Modify | `ai-service/app/tools/store.py` | +2 field dataclass | mọi test dựng `DossierRecord` |
| Create | `ai-service/app/pipeline/contract_graph/projection.py` | ~70 dòng | `test_contract_graph_projection.py` |
| Modify | `ai-service/app/pipeline/idp.py` | +~15 dòng quanh `:306`, `:327-338`, `:344` | golden P3 + `test_contract_graph_wire.py` |
| Create | `ai-service/tests/test_contract_graph_projection.py` | ~6 test | mới |
| Create | `ai-service/tests/test_contract_graph_wire.py` | ~6 test | mới |
| Create | `ai-service/tests/test_contract_graph_edge_store.py` | ~4 test | mới |
| Create | `ai-service/tests/test_contract_graph_postgres_store.py` | ~7 test (cần Postgres) | mới |
| Create | `docs/ai2/AI2-19-contract-graph-operation-first.vi.md` | ~120 dòng | — |
| Modify | `docs/ai2/README.md` | +1 dòng chỉ mục | — |

## Implementation Steps

1. Xác nhận môi trường Postgres cho test: `AI2_TEST_DATABASE_URL` hoặc Docker (`ai-service/tests/conftest.py:12-24`). Máy lập plan không có Docker (OBSERVED `docker: command not found`) — cook phải có `AI2_TEST_DATABASE_URL` hoặc chạy trên máy khác. Chạy test P4 với `AI2_REQUIRE_DOCKER=1` để skip biến thành fail. Không có Postgres ⇒ vẫn làm phần còn lại, verification ghi tiêu chí migration là `SKIPPED` kèm lý do. `AI2_TEST_DATABASE_URL` **phải là DB dùng một lần**: test downgrade drop `ai2.contract_edges` trên DB đó.
2. Viết test RED: projection, wire, edge store, postgres store → chạy, FAIL.
3. `projection.py` (findings + coverage).
4. `store.py` thêm 2 field; chạy nhanh các test dựng `DossierRecord` + golden.
5. `idp.py` 3 điểm (Requirements §2); chạy golden P3 (phải xanh, file golden không đổi).
6. `tables.py` (`graph_metadata`), `0005_ai2_contract_edges.py`, `contract_edge_store.py` (lọc NUL).
7. `jobs.py` gọi `replace_contract_edges` trong `cx.begin_nested()`; lỗi ⇒ log, job vẫn SUCCEEDED.
8. `migrate.py` thêm `downgrade()` + `__main__`; sửa `test_ai2_postgres_store.py:612` (RT-11).
9. `edge_findings` chống trùng với `AMENDMENT_SIGNAL`/`CANDIDATE_AMENDMENT` cũ (RT-07).
10. Postgres test thật: fresh DB → `migrate()` → bảng có, `alembic_version = 0005_ai2_contract_edges`, cột khớp `tables.contract_edges`; `python -m app.db.migrate downgrade 0004_ai2_job_indexes` → bảng mất, bảng khác còn; `migrate()` → bảng lại có.
11. Viết `AI2-19` + dòng chỉ mục README.
12. Regression gate cả hai suite (+ postgres có Docker) → commit phase; chạy `hs:code-review` lấy `review-decision.json` (post obligation của P4).

## TDD

### Tests Before (RED)

`ai-service/tests/test_contract_graph_projection.py`
- [ ] `test_every_op_projects_to_amends` — 5 op ⇒ `relation_type == RelationType.AMENDS`, `kind == "AMENDMENT_SIGNAL"`.
- [ ] `test_findings_carry_no_subtype_strings` — `json.dumps(finding.model_dump(mode="json"))` không chứa `INSERTION|SUBSTITUTION|REPEAL|REJECTION|SCOPE_LIMIT`; `metadata == {}`.
- [ ] `test_findings_keep_two_sided_citations_and_review_state`.
- [ ] `test_edge_duplicating_legacy_candidate_amendment_is_not_projected` — cùng cặp node đã có `CANDIDATE_AMENDMENT` ⇒ không sinh finding `contract-graph:*`, `deduped_with_legacy == 1` (RT-07).
- [ ] `test_flag_on_suppresses_legacy_amendment_signal` — flag bật, builder chạy thành công ⇒ không còn finding `kind == "AMENDMENT_SIGNAL"` từ `contract_context` (Q3).
- [ ] `test_flag_on_builder_failure_keeps_legacy_amendment_signal` — builder lỗi ⇒ `AMENDMENT_SIGNAL` cũ vẫn còn.
- [ ] `test_coverage_counts_every_op_including_zero`.
- [ ] `test_coverage_failed_status_has_zero_counts`.

`ai-service/tests/test_contract_graph_wire.py`
- [ ] `test_flag_on_wire_validates_against_result_schema` — `job_result_to_wire` + `validate_contract(wire, "ai2.be.processing.result.v1.schema.json", error_code=...)`.
- [ ] `test_flag_on_subtypes_only_inside_coverage` — bỏ `result.index_contribution.coverage` khỏi bản sao payload ⇒ không còn chuỗi loại con nào.
- [ ] `test_cross_document_edge_meets_be_context_finding_filter` — finding của cạnh thân↔phụ lục thoả đúng các điều kiện ở `persistence.py:811-835` (state, không `candidate_id`, citation 2 tài liệu có `text_span`, `relation_type == "AMENDS"`).
- [ ] `test_flag_on_sets_record_contract_edges_and_ran_flag`.
- [ ] `test_flag_on_builder_failure_sets_failed_coverage_and_keeps_ran_false`.
- [ ] `test_flag_off_has_no_contract_graph_coverage_key` — bổ trợ golden: `"contract_graph" not in coverage`, không finding `contract-graph:*`.

`ai-service/tests/test_contract_graph_edge_store.py`
- [ ] `test_edge_digest_is_stable_and_content_sensitive`.
- [ ] `test_edge_row_has_every_table_column` — key của `edge_row` == tập cột `tables.contract_edges`.
- [ ] `test_contract_edges_table_not_in_initial_metadata` — `"contract_edges" not in tables.metadata.tables` (khoá D9).
- [ ] `test_edge_row_strips_nul_from_text_columns` — span chứa `\x00` ⇒ mọi cột text trong `edge_row` không còn `\x00` (RT-04).
- [ ] `test_sqlite_job_store_ignores_contract_edges` — `SQLiteJobStore.complete_with_snapshot` với record có cạnh ⇒ không lỗi, không tạo bảng mới trong SQLite.

`ai-service/tests/test_contract_graph_postgres_store.py` (dùng `pg_url`; chạy với `AI2_REQUIRE_DOCKER=1`)
- [ ] `test_fresh_database_migrates_to_0005_with_contract_edges` — không `DuplicateTable`; cột khớp `tables.contract_edges`.
- [ ] `test_0005_downgrade_entrypoint_then_upgrade` — `app.db.migrate.downgrade(engine, "0004_ai2_job_indexes")` (đường `python -m app.db.migrate downgrade`) chỉ mất `contract_edges`, `alembic_version = 0004_ai2_job_indexes`; `migrate()` lại lên 0005 (RT-03).
- [ ] `test_completion_replaces_edges_for_latest_success` — job 1 (2 cạnh) rồi job 2 (1 cạnh) ⇒ còn 1 dòng, `job_id` = job 2.
- [ ] `test_older_job_completion_does_not_overwrite_newer_edges` — cùng mẫu fence `tests/test_ai2_postgres_store.py:93`.
- [ ] `test_record_without_graph_run_leaves_edges_untouched` — `contract_graph_ran=False` ⇒ số dòng không đổi.
- [ ] `test_edge_write_failure_keeps_job_succeeded` — patch `replace_contract_edges` ném lỗi ⇒ job `SUCCEEDED`, snapshot mới được ghi, số dòng cạnh cũ không đổi (savepoint, RT-04).
- [ ] `test_worker_edge_write_failure_reports_succeeded_wire` — đi qua `_run_wire_job`/`_execute_wire_job` (`main.py:319-337`) với `replace_contract_edges` ném lỗi ⇒ wire `SUCCEEDED`, không `AI2_WORKER_FAILED` (RT-04 ở tầng worker).
- [ ] `test_check_constraint_rejects_unknown_op`.

### Implement

Theo Implementation Steps 3–9.

### Tests After

- [ ] `ai-service/tests/test_contract_graph_flag_off_regression.py` (của P3) xanh, sha256 file golden == giá trị ghi ở `verification-P3.json`.
- [ ] `ai-service/tests/test_ai2_postgres_store.py` toàn bộ xanh khi có Postgres (migration lặp, fence, snapshot).
- [ ] `ai-service/tests/test_processing_wire_contract.py` xanh (wire cũ không đổi).

### Regression Gate

- ai-service (từ `ai-service/`): `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q -p no:cacheprovider --basetemp=<writable>` — chỉ 13 lỗi môi trường đã nêu.
- Postgres (từ `ai-service/`, cần Docker hoặc `AI2_TEST_DATABASE_URL`): `AI2_REQUIRE_DOCKER=1 uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q -p no:cacheprovider tests/test_contract_graph_postgres_store.py tests/test_ai2_postgres_store.py` — PASS, **0 skipped**.
- Harness (từ repo root): lệnh ở `plan.md` §Acceptance.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Loại con lộ ra field BE `extra="forbid"` / ngoài coverage | `test_findings_carry_no_subtype_strings`, `test_flag_on_subtypes_only_inside_coverage` |
| Critical | Payload lệch schema wire | `test_flag_on_wire_validates_against_result_schema` |
| Critical | DB mới nổ `DuplicateTable` ở 0005 | `test_fresh_database_migrates_to_0005_with_contract_edges`, `test_contract_edges_table_not_in_initial_metadata` |
| Critical | Downgrade phá bảng khác / không chạy được | `test_0005_downgrade_entrypoint_then_upgrade` |
| Critical | Flag tắt mà có key/finding/SQL mới | golden P3, `test_flag_off_has_no_contract_graph_coverage_key`, `test_record_without_graph_run_leaves_edges_untouched` |
| High | Job cũ ghi đè cạnh của job mới | `test_older_job_completion_does_not_overwrite_newer_edges` |
| High | Ghi cạnh lỗi làm FAILED cả job | `test_edge_write_failure_keeps_job_succeeded`, `test_edge_row_strips_nul_from_text_columns` |
| High | Một thay đổi hiện 2 hàng review phía BE | `test_edge_duplicating_legacy_candidate_amendment_is_not_projected`, `test_flag_on_suppresses_legacy_amendment_signal` |
| High | Builder lỗi mà tín hiệu cũ cũng bị tắt ⇒ mất cảnh báo | `test_flag_on_builder_failure_keeps_legacy_amendment_signal` |
| High | Builder lỗi xoá cạnh cũ trong DB | `test_flag_on_builder_failure_sets_failed_coverage_and_keeps_ran_false` |
| High | Cạnh không tới được BE dù là thân↔phụ lục | `test_cross_document_edge_meets_be_context_finding_filter` |
| Medium | Migration và `tables.py` lệch cột | `test_edge_row_has_every_table_column`, `test_fresh_database_migrates_to_0005_with_contract_edges` |
| Medium | SQLite fallback nổ khi record có cạnh | `test_sqlite_job_store_ignores_contract_edges` |
| Medium | Op lạ lọt vào bảng | `test_check_constraint_rejects_unknown_op` |

## Success

- [ ] Mọi test P4 xanh; Postgres test chạy thật (0 skipped) — hoặc ghi `SKIPPED` có lý do trong `verification-P4.json`, khi đó tiêu chí migration chưa đạt.
- [ ] Suite ai-service chỉ 13 lỗi môi trường; golden P3 xanh với sha256 không đổi.
- [ ] Payload flag bật validate schema; loại con chỉ có trong `coverage.contract_graph`.
- [ ] `0005` upgrade → downgrade → upgrade sạch trên Postgres.
- [ ] `docs/ai2/AI2-19-contract-graph-operation-first.vi.md` có before/after coverage, bảng, rollback, link báo cáo; README có dòng chỉ mục.
- [ ] `review-decision.json` từ `hs:code-review` cho thay đổi P4.

## Risks

| Rủi ro | L × I | Xử lý |
|---|---|---|
| `DuplicateTable` trên DB mới (0001 `create_all`) | Cao nếu làm ngây thơ × Cao | D9 + 2 test khoá |
| Postgres test skip trên máy cook ⇒ tưởng xanh | Trung bình × Cao | `AI2_REQUIRE_DOCKER=1`; verification ghi SKIPPED |
| Ghi cạnh làm chậm/khoá transaction hoàn tất | Thấp × Trung bình | ≤500 dòng (`MAX_EDGES`), cùng lock sẵn có; DELETE theo PK prefix |
| Trùng review item với `AMENDMENT_SIGNAL` cũ | Cao × Trung bình | Flag bật ⇒ tắt `AMENDMENT_SIGNAL` cũ (giữ lại khi builder lỗi) + chống trùng với `CANDIDATE_AMENDMENT` theo cặp node (RT-07, Q3) |
| Cạnh nội tài liệu / cạnh PASS không tới BE | Chắc chắn × Thấp | Có trong coverage + bảng; ghi trong AI2-19; Q2 plan.md |
| Dòng cũ còn sau khi tắt flag | Trung bình × Thấp | Mỗi dòng có `job_id` + `source_snapshot_digest`; chưa có consumer đọc bảng đợt này |

## Rollback

1. **Thứ tự bắt buộc (RT-03):** trên mọi môi trường đã migrate, chạy **trước** `python -m app.db.migrate downgrade 0004_ai2_job_indexes` (từ `ai-service/`, có `AI2_DATABASE_URL`) — xoá `ai2.contract_edges`, `alembic_version` về 0004. Revert file `0005` khi DB còn ở 0005 làm `migrate()` (gọi qua `ensure_database`, `engine.py:43`) nổ `Can't locate revision` ⇒ hỏng mọi đường Postgres. Dữ liệu cạnh tái sinh được bằng cách chạy lại job khi bật flag.
2. Sau đó mới `git revert <commit P4>` (gỡ projection, store, field `DossierRecord`, 3 điểm trong `idp.py`, migration, doc).
3. Chạy lại suite ai-service + golden P3. Rollback nóng không cần deploy: tắt `AI2_CONTRACT_GRAPH_ENABLED`.
