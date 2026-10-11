# P5 implementation notes

## Changes

- Added a read-only, dependency-free SVG graph overview bounded to the current Backend page. Canvas and relation-list selection share a relation ID; the paged list remains the complete traversal and evidence fallback.
- Integrated graph, timeline, and list into the dossier structure view behind `VITE_AI2_GRAPH_UI_ENABLED`, default OFF. Requests are made only after the user opens the panel and use the Backend client.
- Added pair/operation selection and page summaries that show displayed versus total relations. Closing the panel preserves existing OCR view behavior.
- Mapped Backend `latest_job_id` and `metadata.ai2_snapshot_digest` into the dossier view without changing the public Backend DTO.
- Citation actions use the Backend citation endpoint. Legacy opaque handles fall back to OCR only when the referenced node ID exactly matches a loaded clause.
- Fixed completeness for inconsistent paging responses: a repeated cursor or any remaining `next_cursor` prevents the relation list from being marked complete, even if edge count equals `total_count`.
- Graph and trace reads are isolated. A failed trace renders `TRACE_UNAVAILABLE` while retaining a successful graph page; a failed graph read preserves the timeline and offers a graph retry.
- Citation loads use a request-version guard. A stale response/error cannot replace the latest citation selection; changing dossier, graph kind, or selected relation clears the previous evidence and invalidates outstanding requests.
- Graph edges now carry nullable endpoint `source_document_id`/`target_document_id` metadata projected from persisted citation records; both keys are required by the internal and public graph contracts. Citation text and spans stay private.
- Accessible relation rows and the inspector show the target document/node label together with `target_address`, so the address does not hide document provenance.
- Citation buttons pass endpoint document identity through to legacy OCR fallback. Fallback requires a `cite:` opaque handle, an explicit API 404, and a matching selected document; authorization and service failures remain visible errors rather than bypassing citation ACLs.
- Canvas node identity is `(document ID, node ID)`, so equal node IDs from separate dossier documents are rendered separately. Labels resolve OCR clause details only for the selected matching document; other documents show their own filename plus stable node ID. Operation target addresses remain visible; pair endpoints retain document identity even when no address is available.
- When persisted citations lack document identity, the canvas leaves endpoints unmerged per relation instead of combining same-named nodes from unknown files.
- Added a synthetic multi-annex renderer spike. No third-party renderer or dependency was added. Runtime AI2 flags remain OFF.

## Verification evidence

- Red regression: repeated cursor with `has_more=true` and a deduplicated count equal to `total_count` made `isRelationListComplete` return true. The new tests assert the list remains incomplete for repeated cursors and for a non-null cursor even when `has_more=false`.
- Cross-document regression covers source file identity in AI2 projection, Backend validation/forwarding, required frontend provenance, duplicate node IDs in canvas rendering, and retaining target document labels beside operation target addresses.
- P5 focused tests: `npm test -- --reporter=dot src/pages/DossierStructurePage.test.tsx` — 9 passed; the independent tester reran this focused file after the final endpoint-identity fix and also got 9/9.
- Full Frontend suite: `npm test -- --reporter=dot` — 139 passed across 36 files.
- Frontend lint: `npm run lint` — 0 errors and 13 existing warnings.
- Production build: `npm run build` — passed; Vite reports the existing >500 kB chunk warning. Final JavaScript bundle is 1,283.79 kB (367.99 kB gzip). Bundle delta and renderer fixture details are in `reports/renderer-spike.md`.
- Security follow-up: updated only the `source-map-js` lockfile resolution from 1.2.1 to 1.2.2 after the production audit identified GHSA-68fv-2mgg-jv7q; `npm audit --omit=dev --audit-level=high` now reports zero vulnerabilities. Full audit still reports development-only Vitest/Tinypool advisories whose available fix is a major Vitest upgrade; see `plans/reports/security-scan-2026-10-11-ai2-graph-ui.md`.
- Format check: Prettier passed on all changed frontend and P5 report files.
- Feature-gate test confirms the UI flag defaults OFF and graph/trace APIs are not called while disabled or closed.
- `curl.exe --noproxy "*" http://127.0.0.1:5173/` returned HTTP 200. Backend port 8000 and Keycloak port 8080 were not listening.
- AI2 projection tests: `ai-service/.venv/Scripts/python.exe -m pytest -q tests/test_contract_graph_read_api.py` — 9 passed.
- Backend adapter tests: `backend/.venv/Scripts/python.exe -m pytest -q tests/unit/test_ai2_contract_graph_adapter.py` — 13 passed, including rejection of missing/invalid endpoint document IDs.
- Local Compose startup was attempted for Backend, AI2, and Keycloak; it stopped because fixed-name `ci-kafka` already exists in the prior stack. Existing stopped containers were left untouched to avoid changing the original environment/database.

## Remaining verification

The in-app browser runtime reported no available browser. Therefore 320 CSS px overflow, actual browser keyboard/focus behavior, visual clarity, and live citation navigation remain unverified. Do not infer those checks from server-render tests. Compose maps Backend to 8000 and Keycloak to 8080; `frontend/src/api/client.ts` defaults to 8080, so local end-to-end use must set `VITE_API_BASE_URL=http://127.0.0.1:8000`.
