# Rà soát độc lập P4 — integration và storage

## Phạm vi và kết luận

**PASS cho code P4 tại snapshot sau sửa F1/F2. Không còn blocker.** Base `bffe37e3d0084b000d00ea6d3fbe26a56e23fa60`; thay đổi P4 đang nằm trong worktree. Chỉ ghi báo cáo này; không sửa implementation, phase state, receipt hoặc commit. Không rà soát code P5.

Đã đọc plan, phase 4, standards và các thay đổi trong `idp.py`, `ai1_snapshot_adapter.py`, `store.py`, `jobs.py`, `db/tables.py`, migration `0006`, `pair_projection.py`, `pair_relation_store.py`, capture script, fixture và tests P4. Đã đối chiếu docs AI2-20/runbook với đường thực thi.

Scouting trước review: đọc caller `run_idp`, projection/citation helper và transaction completion; tìm ranh giới consent, env flags, vị trí context/review IDs, shared mutable state, quota và nhánh ghi storage. Checklist 2 lượt `base.md` + `api.md`; ưu tiên correctness, confidentiality và error boundary. Ngôn ngữ `vi`, `code_style=3` theo cấu hình đã resolve trong review P3.

## Findings tại snapshot đầu, đã sửa

### F1 — Critical, confirmed → resolved: traceback khi ghi pairs làm lộ văn bản hợp đồng

Code evidence trước sửa, `ai-service/app/tools/jobs.py:608`:

```python
job_id, record.tenant_id, record.dossier_id, type(exc).__name__, exc_info=True)
```

`IntegrityError` của SQLAlchemy mang statement, INSERT parameters và exception DB. Parameters của pairs chứa `span_a`, `span_b`, citation JSON. Probe synthetic qua chính `_replace_pair_relations` và logging handler cho `raw_span_logged=true`, `sql_parameters_logged=true`; lỗi ghi DB có thể đưa nội dung hợp đồng vào log.

**Sửa và recheck:** `jobs.py:608` chỉ ghi ID và `type(exc).__name__`, không traceback hoặc exception string. Chạy lại cùng probe: `raw_span_logged=false`, `sql_parameters_logged=false`, `warning_logged=true`, `error_type_logged=true`. Test `test_pair_write_failure_logs_metadata_without_source_payload` kiểm sentinel và statement không có trong caplog; xanh.

Đây là deviation cần thiết khỏi phase 4 Requirements 6, vốn ghi `exc_info=True`: instruction đó tạo data exposure. Sửa không thay semantics savepoint hoặc trạng thái job. Wrapper edge luồng 1 có logging tương tự từ base; không dùng lỗi có trước đó để chặn P4.

### F2 — Important, confirmed → resolved: citation mặc định cắt 240 ký tự, mất phần khác biệt

Code evidence trước sửa, `ai-service/app/pipeline/contract_graph/pair_projection.py:80`:

```python
raw = citation_for_node(nodes, record.pages, node_id, text_span=None)
```

Helper có trước tại `outline.py:94`:

```python
requested_span = text_span or ((node.text if node else "") or location.get("text_span") or "")[:240]
```

Probe chạy cả `build_pair_relations → pair_conflict_candidates` trên 2 khoản synthetic dài 523 ký tự, phần 30/15 ngày ở cuối: tạo 1 relation và 1 finding nhưng cả 2 citation chỉ dài 240, thiếu phần khác biệt, vẫn `VALID`. Test ban đầu chỉ dùng khoản ngắn nên không chứng minh được whole-node requirement D8/RT-10.

**Sửa và recheck:** `pair_projection.py:85` truyền `text_span=node.text`; `pair_projection.py:86` yêu cầu raw span đúng toàn bộ text node rồi verify. Không sửa helper outline dùng chung. Probe mới với khoản 610 ký tự: 1 relation/1 finding, citation lengths `[610,610]`, `full_node_equality=[true,true]`, `tail_correspondence=[true,true]`, cả 2 `VALID`.

`test_long_multiline_conflict_keeps_entire_node_and_differing_tail` giữ đầy đủ khoản nhiều dòng và giá trị ở đuôi; `test_full_node_split_across_pages_is_rejected_without_partial_fallback` từ chối fallback bị rút ngắn và tăng `conflict_citation_invalid`. Cả hai xanh.

## Bằng chứng reviewer tự chạy

| Kiểm tra | Kết quả sau sửa |
| --- | --- |
| Projection/store/consent/IDP/wire + edge-store focused | **75 passed**, exit 0 |
| Pairs flag regression + golden flag-off regression | **19 passed**, exit 0, 248.79 s |
| Pairs Postgres + edge Postgres, `AI2_REQUIRE_DOCKER=1` | **15 passed**, exit 0, 19.38 s |
| Ruff các file Python P4 theo cwd/config ai-service | **All checks passed**, exit 0 |
| Synthetic SQLAlchemy log error | Source span/SQL parameters không vào log |
| Synthetic builder→projection với khoản dài | Full text từng node và phần khác biệt được giữ, citations VALID |

Lệnh focused từ `ai-service/`:

```text
.venv/Scripts/python.exe -m pytest -q tests/test_contract_graph_pair_projection.py tests/test_contract_graph_pair_store.py tests/test_contract_graph_pairs_consent.py tests/test_contract_graph_pairs_idp_integration.py tests/test_contract_graph_pairs_wire.py tests/test_contract_graph_edge_store.py
.venv/Scripts/python.exe -m pytest -q tests/test_contract_graph_pairs_flag_regression.py tests/test_contract_graph_flag_off_regression.py
AI2_REQUIRE_DOCKER=1 .venv/Scripts/python.exe -m pytest -q tests/test_contract_graph_pairs_postgres_store.py tests/test_contract_graph_postgres_store.py
```

Dòng env ở trên ghi dạng command notation; reviewer thực thi bằng PowerShell `$env:AI2_REQUIRE_DOCKER='1'` trong child command. Không đọc secret hoặc gọi provider thật. PostgreSQL là container thật do fixture tạo; mỗi test fresh DB riêng.

Không đo coverage hoặc typecheck trong lượt này; không có tỷ lệ coverage để báo. Main chạy full regression riêng; báo cáo này không dùng kết quả full chưa hoàn tất làm evidence.

## Kết quả kiểm tra contract và production

- **Consent/egress:** adapter chỉ lấy `policy_flags.egress_allowed`; record mặc định false và không serialize consent/pairs vào query snapshot. Cổng runtime tiếp tục AND với egress vận hành, quota và deadline. HTTP/Kafka dùng chung adapter; chưa thêm field wire.
- **Cờ:** pairs là cờ con của graph, đọc một lần; cờ graph tắt hoặc pairs tắt không import module pair pipeline. Golden kiểm tắt/unset/false values, pairs flag đơn lẻ và rule-only sau stripping; không đổi output cũ ngoài tập trường đã xác định.
- **Context/review IDs:** pairs nối sau `build_contract_context`, context issues và graph issues. Test riêng file và annex nhúng giữ nguyên prefix review IDs, context, cạnh luồng 1 và candidates cũ. Pairs không vào `relation_pairs`, không mở khóa fact comparison.
- **Projection:** chỉ CONFLICT ra candidate COMPARABLE_DIFFERENCE, UNCLEAR, NEEDS_REVIEW; nhãn khác chỉ storage/coverage. Dedup theo node pair, tối đa 5 finding; source citation do code chọn full node và verify. Wire schema xanh, không nhãn mới lọt vào findings/context reason hoặc field wire mới.
- **RT-14:** `pair_relations_ran=True` chỉ khi đã hoàn tất ít nhất 1 lô hoặc NO_CONSENT. Lỗi provider trước lô đầu và egress/model/budget/deadline/cờ tắt giữ false; NO_CONSENT + list rỗng cho phép xoá đề xuất cũ. Đã đọc biểu thức thực ở `idp.py:429` và chạy matrix cũng như actual provider fallback.
- **Storage/concurrency:** migration 0006 nằm sau 0005; PK tenant/dossier/relation, CHECK 4 labels, index tenant/dossier/job. Metadata riêng không đưa bảng pairs vào SQLite. DELETE/INSERT dùng bind parameters trong transaction caller; NUL được lọc. Không có vòng DB N+1.
- **Fence/savepoints:** `complete_with_snapshot` xác minh owner/digest, worker token và RUNNING; advisory transaction lock theo tenant/dossier, latest SUCCEEDED theo created_ms/job_id. Pair replace chạy sau edge replace với savepoint riêng; CHECK failure rollback DELETE/INSERT pairs, giữ dòng pairs cũ, vẫn commit edge mới và job SUCCEEDED. Older completion không ghi đè latest; `ran=False` giữ dòng cũ; list rỗng của latest chạy thành công xoá dòng cũ. Các nhánh này đã chạy trên Postgres thật.
- **Error boundary:** lỗi pair builder/projection thành issue sanitised và coverage FAILED; không làm FAILED job hoặc thay output luồng 1. Lỗi storage ghi metadata-only sau F1, giữ transaction completion.

## Golden và rollback

Hash file golden graph-on reviewer tự tính:

`64ea9e599f9c8f5c1b1fd1ea376287ec772315c08f3bc46f5a17488a631eba74`.

Khớp `reports/p4-golden-crosscheck.json`, artifact lead tạo trên detached worktree P3 `bffe37e3`: 69 case, byte match true. Reviewer đọc artifact và chạy golden regression trên worktree hiện tại; không tự tái tạo lần detached capture đó. `git diff bffe37e3 -- ai-service/app/pipeline/outline.py` rỗng sau F2.

Runbook yêu cầu dừng mọi process trước downgrade về 0005 để tránh auto-migrate nâng lại schema; chỉ drop bảng pairs rồi revert/deploy và khởi động lại. Migration up/down/up đã chạy trong bộ Postgres reviewer. Tắt cờ hoặc lỗi vận hành giữ dòng cũ là semantics đã duyệt, không được diễn giải là xoá dữ liệu consent.

## Độ phức tạp và follow-up

Không có ghi chú complexity cần chặn hoặc bắt buộc xử lý trong P4. Reuse citation helpers, transaction fence và savepoint pattern có domain cụ thể; helper flag cục bộ tránh import pairs khi tắt.

Có thể chốt P4 sau full regression/receipt của lead. Chưa kết luận chất lượng classifier hoặc quyết định bật cờ; P5 còn cần HG-1 import/freeze, preconditions và bake-off. Khoản spanning nhiều trang bị từ chối projection khi không thể có 1 citation toàn node VALID; relation đã grounded vẫn lưu riêng, coverage đếm citation invalid để giữ giới hạn rõ ràng.
