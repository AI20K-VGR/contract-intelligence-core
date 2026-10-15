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
- Security follow-up: upgraded Vitest to 5.0.3 and aligned the declared Node engine and frontend CI to Node 24, resolving the previous development dependency advisories. Full `npm audit --audit-level=high` and production-only audit report zero vulnerabilities. Python runtime dependency exports for AI service and Backend both report no known vulnerabilities with pip-audit. A clean `npm ci` passed in an isolated temporary directory; a local in-place attempt could not replace native files held open by active dev-server processes. See `plans/reports/security-scan-2026-10-11-ai2-graph-ui.md`.
- Format check: Prettier passed on all changed frontend and P5 report files.
- Feature-gate test confirms the UI flag defaults OFF and graph/trace APIs are not called while disabled or closed.
- `curl.exe --noproxy "*" http://127.0.0.1:5173/` returned HTTP 200. Backend port 8000 and Keycloak port 8080 were not listening.
- AI2 projection tests: `ai-service/.venv/Scripts/python.exe -m pytest -q tests/test_contract_graph_read_api.py` — 9 passed.
- Backend adapter tests: `backend/.venv/Scripts/python.exe -m pytest -q tests/unit/test_ai2_contract_graph_adapter.py` — 13 passed, including rejection of missing/invalid endpoint document IDs.
- Local Compose startup was attempted for Backend, AI2, and Keycloak; it stopped because fixed-name `ci-kafka` already exists in the prior stack. Existing stopped containers were left untouched to avoid changing the original environment/database.

## Final browser verification

- The initial in-app browser attempt was unavailable, but this was superseded by an Edge/Playwright run against the composed P5 view and an isolated authenticated Backend/Keycloak/AI2 stack; see `../manual-test-log.md` and `../reports/live-citation-e2e.json`.
- Re-ran the 320 CSS px browser session with a realistic synthetic trace timestamp. Viewport, document, and body widths are 320 px; visible keyboard focus, Space selection, inspector update, and citation callback pass; no page errors or 1970 timestamp. Refreshed screenshot: `../reports/ai2-graph-manual-320px.png`.
- Reviewed the refreshed screenshot and the no-login offline preview. The canvas may scale down on mobile, while the relation list and inspector remain readable and operable as the full alternative.
- Live citation validation remains against synthetic uploaded PDFs and seeded graph/trace rows. It verifies authenticated route/ACL and document retrieval, not AI2 graph generation from OCR input.
- A separate authenticated composed-app check now covers the responsive application shell at 320 CSS px, mobile menu focus/Escape behavior, evidence controls, and graph/trace HTTP 200. The receipt and screenshot are `../reports/live-ui-320-verification.json` and `../reports/ai2-graph-live-320px.png`; data remains synthetic and seeded.
- Final terminal-state regressions: builder failure persists as a `FAILED` receipt instead of `SKIPPED`; queued/running graph jobs alone return `PENDING`; failed/cancelled jobs return terminal failure; trace/job outcomes remain distinct: trace status reports event completeness; a failed stage is `FAILED`, and the separate job status reports `FAILED`, `CANCELLED`, or `SUCCEEDED`; Frontend retains `job_status` and labels failed/cancelled jobs accurately.
- Final package suites after terminal-state regressions: AI service 1612 passed / 9 skipped; Backend 661 passed / 18 skipped (PostgreSQL-only tests requiring `CI_TEST_POSTGRES_URL` skipped); Frontend 145 passed / 37 files, lint 0 errors / 13 warnings, and production build passed with existing chunk-size advisory. Earlier P5 runs reported AI service 1606/9 and Backend 659/18 before the final regression tests; current verification totals include those later tests.


## Final responsive/security follow-up ? 2026-10-12

- Browser receipt `reports/live-ui-320-verification.json` now also records focus-trap wrap in both directions, NavLink close with focus restoration, Escape close, and automatic dialog/focus-trap teardown when resizing to desktop. At 320 CSS px the main/document/body widths remain 320 px; graph and trace requests return 200 and the browser reports zero errors.
- Terminal outcome fixes now preserve graph `FAILED`, reject malformed non-string `job_status` values as adapter errors, and retain a known job outcome if trace retrieval fails after job lookup. Focused backend adapter tests: 17 passed; focused AI-service trace/read tests: 36 passed; independent reviewer reran the job-status fallback regression: 1 passed.
- Full Frontend suite is 37 files / 145 tests; lint 0 errors / 13 warnings; build passes with the existing chunk advisory. `npm audit --audit-level=high` reports zero known vulnerabilities. Vitest 5 requires Node 24, now aligned in package metadata and CI. A clean isolated `npm ci` passed.
- `pip-audit` on exported runtime dependency sets for AI service and Backend reports no known vulnerabilities.
- Synthetic seeded data limitation remains: live checks verify the graph/trace read, ACL, UI and citation document retrieval path, not graph generation from OCR. Runtime flags stay OFF.
