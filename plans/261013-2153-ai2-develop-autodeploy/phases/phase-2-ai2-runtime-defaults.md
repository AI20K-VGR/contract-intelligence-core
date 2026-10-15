# P2 — Default-on runtime AI2

## Overview

Đồng bộ default source + template AI service để graph, pair, processing LLM/egress, query LLM/vector và vector recall đều ON khi chạy stack đầy đủ; một env override `false` vẫn là operator kill switch. Đây chỉ bật khả năng runtime: provider credentials, egress, DB, consent từng hồ sơ, budgets và readiness vẫn quyết định kết quả thật (`docker-compose.yml:483-503`; source hiện default false ở các vị trí được dẫn dưới đây).

## Requirements

- **Functional:** mọi fallback production/runtime đang false thành true; direct service startup nhận cùng ý nghĩa như profile đầy đủ. Query request chỉ có thể thu hẹp quyền; AI2 tính consent theo hồ sơ AND global service cap. Payload query phải hợp lệ/chữ ký đúng; nếu consent field thiếu thì fail closed cho egress.
- **Non-functional:** auto-pass, discovery health và chữ ký là safeguards/diagnostic được phân loại riêng, không bật theo ma trận. Chẩn đoán thiếu provider báo rõ; không khẳng định inference từ env/health flag.
- **TDD:** trước đổi default, test từng biến absent→ON, explicit false→OFF, cap false hoặc consent false→0 external calls; red trước code, green sau.

## Related Code Files

**Create:** —

**Modify (ownership chỉ P2):**

- `ai-service/app/pipeline/idp.py`
- `ai-service/app/pipeline/contract_graph/pair_builder.py`
- `ai-service/app/pipeline/contract_graph/builder.py` (keep the public capability helper aligned with IDP's default)
- `ai-service/app/pipeline/ai1_snapshot_adapter.py`
- `ai-service/app/api/main.py`
- `ai-service/app/reasoning/vector_recall.py`
- `ai-service/app/db/engine.py`
- `ai-service/.env.example`
- `ai-service/tests/test_contract_graph_flag_off_regression.py`
- `ai-service/tests/test_contract_graph_idp_integration.py`
- `ai-service/tests/test_a8_env_flags.py`
- `ai-service/tests/test_ai2_postgres_store.py` (make the intentional no-database test profile explicit)
- `ai-service/scripts/capture_idp_golden.py` (keep flag-off goldens pinned OFF as production defaults turn ON)
- `ai-service/tests/test_contract_graph_pairs_flag_regression.py` (keep graph-only golden coverage explicit when pairs default ON)
- `ai-service/tests/test_contract_graph_wire.py` (pin its graph-off branch to explicit OFF)
- `ai-service/tests/test_st067_bounded_jobs.py` (set consent in signed vector-query cap tests)
- `ai-service/tests/unit/test_production_query.py` (exercise LLM policy with signed dossier consent)
- `.github/workflows/ai-service.yml` (set the isolated deterministic CI profile's database override explicitly)

**Delete:** —

## Implementation Steps

1. Bổ sung test matrix cho defaults `AI2_CONTRACT_GRAPH_ENABLED`/`AI2_CONTRACT_GRAPH_PAIRS_ENABLED` (source `idp.py:514-519`, builder `pair_builder.py:35-60`), `AI2_PROCESSING_EGRESS_ALLOWED` (`ai1_snapshot_adapter.py:45-51`), query LLM/vector/egress (`main.py:209-217`) và vector recall (`vector_recall.py:229-265`). Xác nhận mỗi biến có override false và egress call count bằng 0 khi bị chặn.
2. Tách rõ service cap với consent: processing `record.egress_approved = service_cap AND request consent`, giữ consent trên record riêng; pair classifier và vector runtime phải kiểm tra kết quả cap hiệu lực, không dùng consent để vượt server setting. Giữ request schema/version/chữ ký tương thích.
3. Đổi `/query` policy ở `main.py` để lấy `content_sharing_consent` từ payload đã được `verify_service_envelope` xác minh, AND nó với global `AI2_QUERY_EGRESS_ALLOWED`/LLM/vector flags. Thiếu field hoặc false chặn LLM/embedding/vector; local deterministic lookup vẫn chạy. Field do Backend ký ở P4; direct unsigned route không được mở quyền.
4. Đặt source fallback graph, pair, processing egress, query LLM/vector/egress, vector recall ON. Trong `.env.example:129-139`, đặt capability ON; giữ `AI2_EMBEDDING_DISCOVERY_ENABLED=false`, `AI2_CONTRACT_GRAPH_AUTO_PASS=false`, `AI2_QUERY_REQUIRE_SIGNATURE=true`. Đặt `AI2_REQUIRE_DATABASE=true` cho full profile/source startup; unit tests cô lập phải override false rõ ràng.
5. Chạy tests đỏ→xanh cho default matrix, signed/unsigned query policy, runtime egress disabled, pair skip, vector skip; chạy AI-service CI từ P1. Kiểm tra Compose đã render (`docker-compose.yml:483-503`) vẫn thể hiện cờ ON; Compose hiện là đường product chính.

## Success Criteria

- [x] Khi env không khai báo, graph/pairs/processing egress/query LLM/vector/vector recall đều ON trong service config; explicit `false` tắt đúng một capability.
- [x] Processing, pair, query LLM, query embedding/vector có test call count 0 cho consent false hoặc server cap false; consent true không thể vượt server cap.
- [x] Product/direct full-stack profile buộc persistence DB; unit harness chỉ có thể dùng kho cô lập qua override tường minh.
- [x] Health embedding discovery vẫn `NOT_RUN` mặc định và không được dùng làm acceptance cho vector retrieval; auto-pass/signature giữ trạng thái đã chốt.

## Verification (2026-10-14)

- AI-service deterministic profile (Python 3.12.13, keys empty, explicit isolated-test DB override): `1606 passed, 3 skipped, 17 deselected, 25 warnings` in 301.84s. PDF-only goldens remain excluded because their fixtures are gitignored; live/integration tests are excluded by the profile.
- Targeted consent/query/graph regressions: `67 passed, 1 warning` in 7.55s; DB isolation, graph flag-off golden, and pair-off module-load regression also passed in focused runs.
- Ruff check passed and Ruff format check passed for all 16 modified Python files.
- `docker compose config --quiet` passed; rendered `ai2-service` values were `true` for graph, pairs, processing/query egress, query LLM/vector, vector recall, and `AI2_REQUIRE_DATABASE`.
- Deterministic runs had `AI2_LLM_API_KEY` and `AI2_EMBEDDING_API_KEY` empty. No live provider inference was requested or claimed.

## Risk Assessment

**Cao × Rất cao:** source defaults ON làm gọi provider/chi phí/egress nếu runtime cap hoặc consent xử lý nhầm. **Mitigation:** test AND ở boundary thực, operator override false, consent fail-closed nếu thiếu, budgets/timeouts giữ nguyên, secret không in log.

**Trung bình × Cao:** `AI2_REQUIRE_DATABASE=true` làm developer direct run fail khi chưa cấu hình DB. **Mitigation:** README P6 sẽ cung cấp Compose DB setup và check `.env`; lỗi phải fail fast, không chuyển âm thầm sang in-memory.

**Rollback:** tắt feature/egress vars server-side; revert default module nếu fallback regression. Không hạ chữ ký hoặc bật auto-pass như rollback.
