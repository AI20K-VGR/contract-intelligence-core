---
phase: 3
title: "Backend secure paged API"
status: completed
plan: 261011-1654-ai2-graph-ui
created: 2026-10-11
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 3 — Backend secure paged API

## Overview

Bổ sung Backend facade GET cho graph và processing trace. Frontend chỉ gọi Backend; mỗi request/page kiểm tra CITATION_READ, đúng tenant/dossier/current snapshot/job, và kiểm tra lại quyền sau mỗi lời gọi AI2 có await.

## Requirements

- Graph, node address/relationship metadata cần CITATION_READ; không trả citation excerpts/spans/text dù caller được phép. Click evidence dùng flow citation Backend hiện tại có ACL.
- Trước adapter call: _require_readable(..., action=AclAction.CITATION_READ). Sau khi adapter trả: fetch dossier mới, lặp ACL, so sánh digest với digest lúc bắt đầu và phản hồi AI2. Pattern recheck hiện có tại contract_router.py:1427-1441; digest helper tại :1305-1307.
- Revoked grant → 403; dossier/snapshot đổi → 409; ACL store/AI2 unavailable → fail closed, không body graph.
- Cursor opaque và ràng buộc dossier/tenant/job/digest/stable sort key. Stale/tampered cursor bị từ chối; không cho cursor đổi scope.
- Mọi continuation request lặp lại ACL trước/sau adapter và current digest check.
- Không đổi dossier detail DTO hay AI2 wire v1.

## Related Code Files

**Create**
- docs/contracts/be.ai2.contract-graph.v1.schema.json
- backend/tests/unit/test_ai2_contract_graph_adapter.py
- backend/tests/unit/test_contract_graph_router.py
- frontend/src/api/contractGraph.ts
- frontend/src/api/contractGraph.test.ts

**Modify**
- backend/src/contract_intelligence/infrastructure/ai_adapters.py — read-only service adapters for graph pages and processing trace.
- backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py — new route with pre/post ACL + digest check. Existing dossier route is :1474-1481.
- docs/contracts/ only for new versioned response schemas.

## Implementation Steps

1. Add failing tests where adapter awaits a barrier; remove share grant while blocked; response must be 403 and contain no graph data.
2. Add query-only grant actions=["query"]; assert graph route denied and AI2 calls zero times.
3. Add changed-snapshot race; fresh digest differs after AI2, response 409 and no payload.
4. Define response schema with job_id, snapshot_digest, per-kind graph status, stable ordered edge page, total_count, has_more, next_cursor, trace status/summary.
5. Make AI2 cursor bound to requested job+digest; Backend verifies cursor claims and every returned row identity; do not accept client-supplied tenant/dossier identity as authoritative.
6. Fetch graph and trace through signed service calls; enforce timeout/size caps and sanitize all returned fields.
7. Add frontend typed client only for Backend public routes; runtime validator rejects unknown status, missing scope identity and malformed cursor response.
8. Verify prior dossier/search/citation endpoints keep existing access behavior.

## Tests Before (RED)

- [ ] ACL denied before adapter call.
- [ ] Share revoked during awaited adapter call yields 403/no response body.
- [ ] Snapshot changes during call yields 409/no response body.
- [ ] Query-only share denied by CITATION_READ; owner/authorized shared reader pass.
- [ ] Cursor binds job/digest, tampering/stale snapshot rejected; every page rechecks ACL.
- [ ] Adapter tests reject cross-tenant/job/digest, timeout, malformed signature and raw text fields.

## Tests After (GREEN)

- [ ] cd backend; uv run pytest tests/unit/test_ai2_contract_graph_adapter.py tests/unit/test_contract_graph_router.py -q
- [ ] cd backend; uv run ruff check src/contract_intelligence/infrastructure/ai_adapters.py src/contract_intelligence/contract/interfaces/api/routers/contract_router.py tests/unit/test_ai2_contract_graph_adapter.py tests/unit/test_contract_graph_router.py
- [ ] cd frontend; npm test -- --run src/api/contractGraph.test.ts

## Regression Gate

cd backend; uv run pytest and cd frontend; npm test before P4.

## Success Criteria

- [ ] No graph/trace response returned unless CITATION_READ is valid after upstream call and snapshot/job/digest match.
- [ ] Query-only shares cannot retrieve graph/citation metadata.
- [ ] Every page is scope-checked, stable, and bound to an immutable job/digest.
- [ ] Existing dossier, citation, search and wire contracts remain compatible.

## Risk Assessment

- **High (M×H), ACL revocation race:** mandatory post-await re-fetch and action-specific decision; barrier test.
- **High (M×H), cursor mixes old/new graph:** cursor carries exact job/digest; stale cursor 409.
- **Medium (M×M), opaque cursor implementation differs between AI2/Backend:** schema contract fixture shared by adapter/client tests.
- **Medium (L×H), raw evidence leaks through unexpected nested field:** field allowlist + response-schema test; fail closed on unknown structure.

## Rollback

Disable both new Backend routes and typed client exposure. Keep existing dossier and citation endpoints; no stale-cache fallback.

