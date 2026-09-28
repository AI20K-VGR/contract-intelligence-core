# Nghiên cứu current-state và contract map

## Kết luận xếp hạng

1. **P0 — authorization trước mọi mutation:** review/approve mock route đang đăng ký trước route có RBAC, và live probe không token đã đổi state. Đây là chặn bảo mật phải làm trước khi mở rộng read model/UI.
2. **P0 — result boundary phải complete:** `ai2.be.processing.result.v1` đã định nghĩa `context_findings`, `events`, `chunks`, `evidence_issues`, `annex_links` và `coverage`, nhưng Backend persistence chỉ đọc facts/findings. Nếu không sửa boundary này, FE/query chỉ có thể hiển thị dữ liệu giả hoặc rỗng.
3. **P1 — query/state contract phải đi cùng nhau:** AI2 tạo `state`, `retrieval_layer`, `reasoning_trace`, nhưng Backend DTO rút gọn và FE suy diễn `ANSWERED`. Fallback query chỉ an toàn khi mọi output giữ citation và review state.
4. **P1 — UI phải đọc source scope thật:** hai citation pages static và structure page từ chối citation khác document; dynamic viewer/finding queue cần dùng `dossier_id`, `document_id`, page/line/bbox và revision/version từ API.
5. **P1 — ACL là một policy dùng chung:** query dossier chỉ kiểm tra tenant trong khi search dùng `_require_readable`; same-tenant chưa đủ để chứng minh quyền trên dossier.
6. **P1 — process memory không phải durable source:** worker chỉ tìm `_snapshot_cache`, nên restart sau manifest confirmation làm run dừng ở `waiting_for_snapshots` dù DB còn snapshot.
7. **P1 — legacy phải explicit:** `AI_SERVICE_MODE: stub`, client gọi `/api/v1/jobs/ocr`, và `/process` compatibility lane tồn tại song song với AI2 canonical; cần guard production config và test phân luồng.

## Sources và evidence

- Review report: `plans/reports/ai1-ai2-be-fe-full-review-20260925.md:14-25,27-38,40-56,58-94,107-127`.
- Contract shape: `docs/contracts/ai2.be.processing.result.v1.schema.json:8-82`; `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md:83-122`.
- AI2 semantic constraints: `docs/code-standards.md` phần Contract và Error/Retry/Security; `docs/system-architecture.md` phần Backend job lane, P0–P9 boundary và Event/SSE/UI.
- Current tests available: `ai-service/tests/test_processing_wire_contract.py`, `test_contract_context.py`, `test_result_regressions.py`, `test_st046_query_grounding.py`, `test_legacy_compat.py`, `test_p3_persistence_events.py`; `backend/tests/unit/test_review_router.py`, `test_approval_router.py`, `test_contract_router.py`, `test_worker_pipeline_run.py`; `frontend/tests/ai2-contract.test.ts`, `dossier-search-results.test.tsx`, `review-actions.test.ts`.

## Scope implications

- Reuse current contracts and stores first; only add a new persistence/read-model seam where an existing table/service cannot represent the fields without dropping provenance.
- Treat zero facts/findings as a measurable result, not automatic failure: distinguish “contract has no eligible facts” from “records were dropped/unpersisted”, and route the latter to review/error metrics.
- Keep semantic fallback bounded and observable. A response must disclose retrieval layer and `used_llm`; LLM remains policy-gated and is not a hidden fix for missing evidence.
- Do not call the existing P2–P9 library primitives production-wired until the corresponding HTTP/worker/UI tests prove the wiring.
