## Phase Implementation Report

### Executed Phase
- Phase: P4 — Integration Storage
- Plan: `plans/261008-1500-ai2-contract-graph-implicit`
- Status: completed (implementation); regression tổng và review độc lập do main chạy sau code freeze.
- Worktree: `C:\Users\dungs\OneDrive\Documents\VSF-ai2-contract-graph`.
- Base: `bffe37e3d0084b000d00ea6d3fbe26a56e23fa60`.

### Files Modified

Phạm vi P4, không sửa P3 hoặc `pair_candidates.py`; không commit/ghi receipt.
Số dòng dưới đây là tổng dòng sau sửa, không phải số dòng thêm.

| File | Dòng |
|---|---:|
| `ai-service/scripts/capture_idp_golden.py` | 294 |
| `ai-service/fixtures/contract_graph/idp_graph_on_golden.json` | 160687 |
| `ai-service/fixtures/contract_graph_pair_records.py` | 72 |
| `ai-service/app/pipeline/idp.py` | 686 |
| `ai-service/app/pipeline/ai1_snapshot_adapter.py` | 2661 |
| `ai-service/app/pipeline/contract_graph/pair_projection.py` | 140 |
| `ai-service/app/tools/store.py` | 110 |
| `ai-service/app/tools/jobs.py` | 656 |
| `ai-service/app/tools/pair_relation_store.py` | 51 |
| `ai-service/app/db/tables.py` | 84 |
| `ai-service/app/db/migrations/versions/0006_ai2_contract_pair_relations.py` | 37 |
| `ai-service/tests/test_contract_graph_pairs_flag_regression.py` | 79 |
| `ai-service/tests/test_contract_graph_pairs_idp_integration.py` | 172 |
| `ai-service/tests/test_contract_graph_pairs_consent.py` | 35 |
| `ai-service/tests/test_contract_graph_pair_projection.py` | 175 |
| `ai-service/tests/test_contract_graph_pairs_wire.py` | 59 |
| `ai-service/tests/test_contract_graph_pair_store.py` | 73 |
| `ai-service/tests/test_contract_graph_pairs_postgres_store.py` | 131 |
| `ai-service/tests/test_contract_graph_edge_store.py` | 205 |
| `ai-service/tests/test_contract_graph_postgres_store.py` | 272 |
| `docs/ai2/AI2-20-contract-graph-pairs.vi.md` | 189 |
| `docs/ai2/README.md` | 38 |
| `docs/system-architecture.md` | 96 |

### Tasks Completed

- [x] Capture graph-on 69 case trước sửa `idp.py`, `store.py`, adapter; capture flag-off temp khớp bytes bản commit.
- [x] Profile `graph_on` và `--strip-pairs`; test mọi case cùng seed, false flags, lazy import và rule-only parity.
- [x] Consent từ `policy_flags.egress_allowed`; field nội bộ không vào snapshot/wire, request schema giữ nguyên.
- [x] Projection chỉ tạo candidate từ quan hệ mâu thuẫn, cap 5, dedupe, whole-node citation VALID, scope và canonical item key.
- [x] Coverage cố định, issue LIMITED_COVERAGE theo sáu lý do, exception FAILED và graph-failure SKIPPED.
- [x] Chèn pairs sau context/issue luồng 1; fact candidates, graph edges/context và review ID cũ giữ nguyên.
- [x] `pair_relations_ran` chỉ true cho lô LLM hoàn tất hoặc NO_CONSENT; fallback trước lô đầu giữ false.
- [x] Migration 0006, table metadata riêng, digest/NUL filtering, replace trong transaction và savepoint riêng.
- [x] Fence latest SUCCEEDED: job cũ không ghi đè; lỗi pairs không undo cạnh luồng 1 hoặc làm FAILED job.
- [x] Sửa hai test hard-code head, không sửa test luồng 1 khác.
- [x] AI2-20: coverage thật fixture, ánh xạ Backend, consent/DEC, giới hạn và runbook rollback RT-11.

### Tests Status

- Type/lint check: PASS — `uv run --frozen --extra dev ruff check` toàn bộ Python mới/sửa P4. Repo không có typecheck riêng cho slice này.
- Unit/integration focused sau sửa F1/F2: **75 passed in 6.65s**. Lệnh từ `ai-service/`:

```text
uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q tests/test_contract_graph_pair_projection.py tests/test_contract_graph_pairs_idp_integration.py tests/test_contract_graph_pairs_consent.py tests/test_contract_graph_pairs_wire.py tests/test_contract_graph_pair_store.py tests/test_contract_graph_edge_store.py --tb=short
```

- Golden + projection/integration: **54 passed in 163.38s**, trước bổ sung bốn test gate runtime/fallback; mười test golden vẫn đạt. Lệnh:

```text
uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q tests/test_contract_graph_pair_projection.py tests/test_contract_graph_pairs_idp_integration.py tests/test_contract_graph_pairs_flag_regression.py --tb=short
```

- PostgreSQL 16 Docker thật: **40 passed, 3 skipped, 2 warnings in 25.50s** với `AI2_REQUIRE_DOCKER=1`:

```text
uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q tests/test_contract_graph_pair_store.py tests/test_contract_graph_pairs_postgres_store.py tests/test_contract_graph_postgres_store.py tests/test_ai2_postgres_store.py --tb=short
```

  Bảy test pairs PostgreSQL đạt, gồm migrate up → downgrade entrypoint 0005 → up,
  đủ cột/nullable/PK/index/CHECK, replace latest, clear list rỗng, giữ dòng khi ran false,
  stale job và lỗi CHECK sau DELETE rollback savepoint. Ba skip thuộc pgvector vì image
  `postgres:16-alpine` không có extension; không có test pairs PostgreSQL bị skip.
  Warnings là deprecation của testcontainers và AnyIO portal.

#### TDD evidence

- Consent: RED **4 failed, 2 passed**, `AttributeError: content_sharing_consent`; sau field/adapter GREEN.
- Projection: RED collection vì module `pair_projection` chưa có; sau triển khai projection+consent **29 passed**.
- IDP: RED **12 failed, 9 passed**, thiếu coverage pairs, relation/finding/runs semantics; sau tích hợp và sửa fixture topic GREEN.
- Storage: RED collection vì table `CONTRACT_PAIR_LABELS`/`contract_pair_relations` chưa có; sau table/migration/store/savepoint GREEN unit và PG thật.
- Bổ sung gate runtime thật MODEL_UNSET/BUDGET_EXHAUSTED/DEADLINE và provider fallback trước lô đầu, không dựa riêng vào patch kết quả builder.
- Review F1: RED **1 failed** chứng minh traceback `IntegrityError` ghi SQL parameters/span sentinel; bỏ `exc_info=True` riêng wrapper pairs. GREEN **35 passed in 3.79s** (store6 + IDP25 + wire4), ruff sạch. Sau sửa, pairs PostgreSQL **7 passed in 8.93s**; focused **73 passed in 4.92s**.
- Review F2: RED **2 failed** chứng minh mặc định helper chỉ lấy 240 ký tự và chấp nhận đoạn đầu của khoản trải hai trang. Projection pairs dùng explicit `node.text`, reject khi helper fallback trả span khác full text. GREEN projection25 + IDP25 + wire4: **54 passed in 3.46s**, ruff sạch. `outline.py` legacy/golden không đổi.

#### Golden

| Artifact | SHA256 |
|---|---|
| Graph-on 69 case | `64ea9e599f9c8f5c1b1fd1ea376287ec772315c08f3bc46f5a17488a631eba74` |
| Flag-off committed và capture temp | `091421c523715af741bfaca7cad7125a381d6063e0471a7e58d063bd7f64cac2` |

Capture ban đầu chạy `PYTHONHASHSEED=0`, interpreter Python 3.12, trên code P3 `bffe37e3`.
Main đã kiểm chéo detached worktree P3 và khớp bytes: `reports/p4-golden-crosscheck.json`.
SHA golden sau triển khai vẫn giống ban đầu. Graph-on lưu full của mọi case để đối chiếu
normalization rule-only; fixture 4,626,914 bytes. Các variant `test_pairs=True` thêm keyword
topic dùng integration; default embedded record trong golden giữ nguyên nội dung đã capture.

### Issues Encountered

- Worktree không có `CLAUDE.md`; đã đọc `C:\Users\dungs\OneDrive\Documents\VSF\CLAUDE.md`. `docs/codebase-summary.md` cũng không có; đã đọc standards và system architecture có thật.
- Fixture mặc định không có lexicon topic cho nghiệm thu và khoản injection, nên cặp cần đo không được sinh. Đã bổ sung variant có keyword topic cho test, giữ default fixture embedded của golden nguyên vẹn; không sửa bộ ứng viên P3 đã freeze.
- `rg asdict(` cho thấy chỉ dùng ở event/vector/readiness, không dùng cho `DossierRecord`; các field P4 không lọt vào persist.
- Clarification theo review F1: phase §6 yêu cầu `exc_info=True`, nhưng SQLAlchemy exception chứa INSERT parameters và nội dung hợp đồng, xung đột trực tiếp `docs/code-standards.md` §Error, retry, logging và security. Main chỉ định bỏ traceback, giữ metadata/type lỗi; wrapper cạnh luồng 1 cũ không sửa trong P4.
- Clarification theo review F2: lời gọi `citation_for_node(...text_span=None)` trong phase trả tối đa 240 ký tự ở helper legacy; để thực hiện D8/RT-10 **whole-node**, projection truyền full `node.text` và fail closed nếu source chỉ verify được đoạn ngắn. Khoản trải nhiều trang chưa có citation đầy đủ bị loại finding; quan hệ grounded span trong bảng vẫn giữ.
- Chưa có kết quả regression tổng/independent review ở thời điểm viết báo cáo; main chịu trách nhiệm ghi artifact/gate sau các lượt đó. Không suy ra PASS phase gate từ self-report này.

### Next Steps

- Main chạy suite tổng/harness + reviewer/simplifier độc lập; xử lý finding thật trước đóng P4.
- P5 chạy bake-off B/C/E trên dữ liệu gold đã duyệt và điền §Số đo AI2-20.
- DEC Q1 phải được ghi theo plan trước merge/bật cờ; mặc định cờ pairs vẫn tắt.

Status: DONE_WITH_CONCERNS
Summary: Hoàn tất implementation P4 và focused/golden/PostgreSQL thật; chưa commit hoặc ghi gate receipt.
Concerns/Blockers: Regression tổng và review độc lập đang do main thực hiện; pgvector extension không có trong image PG dùng ở lượt này.
