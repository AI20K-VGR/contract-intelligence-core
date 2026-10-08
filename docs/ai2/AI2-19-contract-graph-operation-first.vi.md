# AI2-19 — Contract graph luồng 1 (operation-first): cạnh sửa đổi, wire và lưu trữ

> Trạng thái: đã triển khai sau flag `AI2_CONTRACT_GRAPH_ENABLED` (mặc định **tắt**). Plan: `plans/261007-1735-ai2-contract-graph-op-first/` (P1–P4). Tài liệu này mô tả đúng code hiện có; không phải bằng chứng production.

## 1. Mục tiêu

AI2 trước đây chỉ có `AMENDS` thô (`app/reasoning/relations.py`) và tín hiệu `AMENDMENT_SIGNAL` cấp phụ lục (`app/pipeline/contract_context.py`): biết "phụ lục có từ sửa đổi", không biết sửa **điểm/khoản/điều nào** và **thao tác gì**. Luồng 1 đọc câu thao tác tường minh ("Sửa đổi điểm c khoản 1 Điều 3 như sau:"), phân loại thành 5 loại cạnh, resolve địa chỉ đích tới node có thật trong cây cấu trúc của `DossierRecord`, và phát cạnh có citation hai phía. Deterministic, không LLM. AI2 **không** chọn bên thắng pháp lý: mọi cạnh là tín hiệu cần người duyệt.

## 2. Flag và giá trị mặc định

| Biến môi trường | Mặc định | Tác dụng |
|---|---|---|
| `AI2_CONTRACT_GRAPH_ENABLED` | tắt | Bật builder + projection + ghi bảng. Truthy: `1`, `true`, `yes`, `on` (không phân biệt hoa thường, bỏ khoảng trắng). |
| `AI2_CONTRACT_GRAPH_AUTO_PASS` | tắt | Cho phép cạnh lên `PASS` **nếu** calibration đạt cổng (mục 7). Hiện cổng đóng nên vô hiệu. |

Flag tắt: không import package `app.pipeline.contract_graph`, không key coverage mới, không finding mới, không câu SQL mới. Bảo đảm bằng golden `ai-service/fixtures/contract_graph/idp_flag_off_golden.json` (`tests/test_contract_graph_flag_off_regression.py`, so nội dung JSON từng case dưới `PYTHONHASHSEED` cố định).

Rollback nóng không cần deploy: đặt lại flag tắt.

## 3. Năm loại cạnh ↔ Akoma Ntoso

| `EdgeOp` | Câu nguồn điển hình | Akoma Ntoso |
|---|---|---|
| `INSERTION` | "Bổ sung khoản 4 vào sau khoản 3 Điều 7 như sau:" | `textualMod type="insertion"` |
| `SUBSTITUTION` | "Sửa đổi điểm c khoản 1 Điều 3 như sau:", "Điều chỉnh/Thay đổi …", "… được thay bằng …" | `textualMod type="substitution"` |
| `REPEAL` | "Bãi bỏ Điều 9." | `textualMod type="repeal"` |
| `REJECTION` | "Bên A có quyền từ chối … theo khoản 2 Điều 7" (chỉ trong phụ lục hoặc dưới đơn vị chứa thao tác) | gần `textualMod`/`meaningMod` — loại riêng của dự án |
| `SCOPE_LIMIT` | "Điều 5 không áp dụng đối với lô hàng 2." | `scopeMod` |

Model: `ai-service/app/contracts/contract_graph.py` (`EdgeOp`, `ContractEdge`), tách khỏi `RelationType` để loại con không thể lọt ra BE qua `relation_type.value` (D1). `edge_id = "cedge:" + sha256(...)[:24]`, ổn định khi retry cùng snapshot. Mọi cạnh mặc định `NEEDS_REVIEW`; thao tác ngầm qua `item_key` (phụ lục không ghi địa chỉ) luôn `NEEDS_REVIEW`.

## 4. Ánh xạ ra Backend (contract không đổi)

Mỗi cạnh → một `context_finding` (`app/pipeline/contract_graph/projection.py::edge_findings`):

| Field wire | Giá trị |
|---|---|
| `finding_id` | `contract-graph:<edge_id>` |
| `finding_type` | `AMENDMENT_SIGNAL` |
| `relation_type` | `AMENDS` cho **cả 5** loại |
| `subject_key` | địa chỉ đích chuẩn hoá, vd `diem c khoan 1 dieu 3` |
| `source_node_ids` | `[source_node_id, target_node_id]` |
| `reason` | một câu chung, không nêu loại con |
| `review_state` | của cạnh |
| `citation_ids` | citation nguồn + citation đích |
| `metadata` | `{}`; hoặc `{"candidate_id": …}` khi cặp node đã là một candidate (không phải `CANDIDATE_AMENDMENT`) |

Loại con **chỉ** xuất hiện trong `index_contribution.coverage.contract_graph` (schema `coverage` là `{"type": "object"}`). Test: `tests/test_contract_graph_wire.py::test_flag_on_subtypes_only_inside_coverage` (xoá coverage khỏi bản sao payload ⇒ không còn chuỗi `INSERTION|SUBSTITUTION|REPEAL|REJECTION|SCOPE_LIMIT`). Vì lý do này mã issue P3 cho thao tác thêm đơn vị mới là `NEW_UNIT_ADDITION` (không chứa `INSERTION`).

Hệ quả lọc phía BE (`backend/src/contract_intelligence/shared/ai/persistence.py`):

- `:811` — chỉ nhận `review_state ∈ {None, NEEDS_REVIEW, INSUFFICIENT_EVIDENCE}` ⇒ cạnh `PASS` (khi cổng mở) sẽ **không** hiện ở BE (câu hỏi mở Q2).
- `:815` — bỏ finding có `metadata.candidate_id` ⇒ cặp thân↔phụ lục đã có candidate chỉ còn **một** hàng review.
- `:825` — cần citation có `text_span` từ ≥ 2 tài liệu ⇒ cạnh nội một tài liệu (phụ lục nhúng trong thân) không tới BE; vẫn có trong coverage + bảng.
- `:834` — `AMENDMENT_SIGNAL`/`AMENDS` → `candidate_amendment`.

Chống trùng (Q3, RT-07): flag bật **và** builder chạy thành công ⇒ `build_contract_context(..., suppress_amendment_signal=True)` bỏ `AMENDMENT_SIGNAL` cấp phụ lục cũ; cạnh trùng cặp node với candidate `CANDIDATE_AMENDMENT` cũ không được chiếu thành finding (đếm `deduped_with_legacy`, vẫn ghi bảng). Builder lỗi ⇒ giữ `AMENDMENT_SIGNAL` cũ. Hệ quả: khi flag bật, id review theo vị trí của các issue **sau** `AMENDMENT_SIGNAL` cũ có thể dịch (các issue trước nó giữ nguyên id).

## 5. `coverage.contract_graph` (before / after)

Before (flag tắt, hoặc trước P4): không có key `contract_graph`.

After (flag bật; giá trị từ fixture `graph_record()` của test):

```json
"contract_graph": {
  "graph_mode": "operation_first",
  "status": "OK",
  "edges_total": 8,
  "edges_by_op": {"INSERTION": 2, "SUBSTITUTION": 4, "REPEAL": 0, "REJECTION": 1, "SCOPE_LIMIT": 1},
  "unresolved_targets": 1,
  "ambiguous_targets": 0,
  "implicit_edges": 0,
  "auto_pass_enabled": false,
  "truncated": 0,
  "deduped_with_legacy": 1
}
```

Key đứng ngay sau `runtime` (`IndexStore.propose` còn thêm `n_candidates_suppressed` sau đó). Builder lỗi ⇒ `status: "FAILED"`, mọi số đếm 0, issue `CONTRACT_GRAPH_FAILED` (`NEEDS_REVIEW`); job vẫn `SUCCEEDED`. BE đọc `coverage` như dict và chỉ dùng key `input` nên không va key mới.

## 6. Bảng `ai2.contract_edges`

Migration `ai-service/app/db/migrations/versions/0005_ai2_contract_edges.py` (`down_revision = 0004_ai2_job_indexes`). Khai báo song song ở `app/db/tables.py` trên `graph_metadata` **riêng** (D9: `0001` gọi `metadata.create_all`, dùng chung sẽ làm DB mới nổ `DuplicateTable` ở 0005).

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `tenant_id`, `dossier_id`, `edge_id` | text | PK |
| `job_id`, `source_snapshot_digest` | text | job SUCCEEDED đã ghi + snapshot nguồn, để consumer tự phát hiện dòng cũ |
| `op` | text | `CHECK op IN ('INSERTION','SUBSTITUTION','REPEAL','REJECTION','SCOPE_LIMIT')` |
| `source_node_id`, `target_node_id`, `anchor_node_id?`, `target_address` | text | |
| `method`, `support`, `review_state` | text | |
| `standard`, `implicit` | int 0/1 | |
| `source_citation_json`, `target_citation_json` | text | JSON chuẩn |
| `new_text?`, `scope_text?` | text | |
| `digest` | text | sha256 JSON chuẩn của cạnh |
| `created_ms` | bigint | |

Index `idx_ai2_contract_edges_job (tenant_id, dossier_id, job_id)`.

Ghi: `PostgresJobStore.complete_with_snapshot` (`app/tools/jobs.py`), trong cùng transaction + advisory lock theo dossier, **chỉ** khi job là SUCCEEDED mới nhất **và** `record.contract_graph_ran` — `DELETE` theo `(tenant_id, dossier_id)` rồi `INSERT` (`app/tools/contract_edge_store.py::replace_contract_edges`). Ghi nằm trong savepoint `cx.begin_nested()`: lỗi ghi cạnh chỉ rollback savepoint, log `ai2.contract_edges_write_failed`, job vẫn `SUCCEEDED` với snapshot mới và cạnh cũ giữ nguyên. Mọi cột text bị lọc `\x00` (Postgres từ chối NUL).

Không có bảng SQLite (D7): `SQLiteJobStore.complete_with_snapshot` bỏ qua cạnh.

Phạm vi ghi: chỉ đường `POST /jobs/idp` → `_execute_wire_job` (`app/api/main.py`). Kafka worker và `ai2_batch.py` gọi `run_idp` (có cạnh in-memory khi flag bật) nhưng **không** ghi bảng. Chưa có consumer nào đọc bảng.

## 7. Cổng PASS và vì sao đang đóng

Cạnh chỉ `PASS` khi: `AI2_CONTRACT_GRAPH_AUTO_PASS` bật, câu thao tác chuẩn, đích resolve `EXACT` duy nhất, citation hai phía `VALID`, **và** loại cạnh có ≥ `MIN_N = 60` bản ghi calibration `approved=true` với cận dưới Wilson 95% ≥ `MIN_WILSON_LOWER = 0.85` (`app/pipeline/contract_graph/review_policy.py`, hằng số trong code). `calibration.json` commit với `n = 0` mọi loại vì gold tự trích từ chú thích VBHN mang `approved=false` (D13) ⇒ cổng đóng kể cả khi bật env.

## 8. Migration và rollback

Thứ tự **bắt buộc** (RT-03) trên môi trường đã migrate:

1. Từ `ai-service/`, có `AI2_DATABASE_URL`: `python -m app.db.migrate downgrade 0004_ai2_job_indexes` — drop index + bảng `ai2.contract_edges`, `alembic_version` về 0004; bảng khác không đổi. CLI `alembic` không dùng được (`migrations/env.py` cần connection truyền vào).
2. Sau đó mới `git revert` commit P4.

Revert code khi DB còn ở 0005 làm `migrate()` (gọi qua `ensure_database` ở lần dùng DB đầu tiên) nổ `Can't locate revision '0005_ai2_contract_edges'` ⇒ hỏng mọi đường Postgres. Dữ liệu cạnh tái sinh được bằng cách chạy lại job khi bật flag.

Test: `tests/test_contract_graph_postgres_store.py` (upgrade → downgrade qua entrypoint → upgrade trên DB mới tạo; replace/fence/savepoint; CHECK). Cần Postgres (`AI2_TEST_DATABASE_URL` hoặc Docker); chạy với `AI2_REQUIRE_DOCKER=1` để thiếu Postgres là fail chứ không skip.

## 9. Báo cáo đo

- [P1 baseline](../../evals/contract_graph/reports/p1-baseline.md)
- [P2 resolver](../../evals/contract_graph/reports/p2-resolver.md)
- [P3 operation parser](../../evals/contract_graph/reports/p3-operation-parser.md) ([chế độ gập về Điều](../../evals/contract_graph/reports/p3-operation-parser-article-only.md))

Gold là `vbhn-note auto-gold (approved=false)`: số đo không phải độ chính xác nghiệp vụ.

## 10. Giới hạn

- Bộ đo là văn bản quy phạm pháp luật (VBHN), không phải phụ lục hợp đồng; văn phong phụ lục hợp đồng khác (mới có fixture tổng hợp), nên mọi cạnh giữ `NEEDS_REVIEW`.
- Cạnh nội một tài liệu và cạnh `PASS` không tới BE (mục 4).
- Bảng chỉ phản ánh job SUCCEEDED mới nhất có chạy graph; tắt flag sau khi từng bật ⇒ dòng cũ còn, mang `job_id` cũ.
- Kafka/batch không ghi bảng.
- Không có cạnh `GENERAL_SPECIFIC`, `CONFLICT`, `REPLACEMENT`, `RENUMBERING`.
