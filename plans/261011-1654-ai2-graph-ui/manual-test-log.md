# Manual test log

## Charter

Explore the responsive AI2 graph view at 320 CSS px, focusing on horizontal overflow, keyboard focus and relation selection, and the mobile-readable text alternative. Done means the composed timeline/canvas/list/inspector renders, the relation list remains readable, keyboard selection works, and the viewport does not scroll horizontally. Use scrubbed fixture data only.

## Session

- Date: 2026-10-11
- Browser: Microsoft Edge 154.0.4258.62 headless; Playwright 1.64.0; Node v24.18.1.
- Fixture: the real `Ai2GraphDossierView` with mocked, schema-valid graph/trace HTTP responses; three synthetic cross-document relations; no real contract or citation data.
- Result: PASS for the viewport and interaction scope. At 320×900 CSS px, document and body widths were both 320 px. Tab reached the first graph relation with visible focus. A second Tab and Space selected `CONFLICT`; the inspector followed the selected relation. The source citation action callback ran. No browser page errors occurred.
- Screenshot: [320 CSS px capture](reports/ai2-graph-manual-320px.png).
- Limit: API responses were mocked, so Backend ACL, authenticated citation navigation, and real citation rendering were not exercised. The charter has no independent human co-sign; evidence is anchored but remains soft for any hard manual gate.
- Harness anchor: `7db7bcbf58edfd76`, command `node /c/Users/dungs/AppData/Local/Temp/ai2-graph-ui-manual/manual-check.mjs`, exit 0. The harness anchor was verified in `.harness/state/telemetry/manual-test-anchor.jsonl`.
- Charter co-sign: none.

## Authenticated live API smoke

- Date: 2026-10-11. Backend, Keycloak, AI2 and supporting services ran in the isolated Compose project `ai2-graph-ui-manual`, using cached development images with the current Backend/AI2 source mounted read-only. All app/data ports and named volumes are project-specific; the pre-existing database on 5434 was not reused.
- Data: two synthetic one-page PDFs were uploaded through the real Backend dossier upload route into the isolated MinIO bucket. A synthetic `REFERENCE` row, persistence receipt, AI2 job/query snapshot, and one allowed pair trace stage were inserted directly in the isolated PostgreSQL schema. No OCR/classifier or graph generation was run.
- Result: authenticated owner read through Backend ? signed AI2 graph route returned `READY`, one edge, and the matching contract/annex document IDs. Backend trace route returned `AVAILABLE`. Both linked document content routes returned HTTP 200 with valid PDF bytes. The graph DTO contained opaque citation refs and document IDs, with no citation text/span. Anonymous request returned 401; same-tenant OPERATOR without a dossier grant returned 403.
- Anchor: `684bfb5241be6620`, command `powershell.exe -NoProfile -ExecutionPolicy Bypass -File /c/Users/dungs/AppData/Local/Temp/ai2-graph-ui-live-citation/verify-live.ps1`, exit 0. Safe result receipt: [live citation E2E](reports/live-citation-e2e.json).
- Limitation: this proves live service signing, ACL, projection, trace read, and citation document retrieval against synthetic seeded graph/trace rows. It does not prove AI2 pipeline graph generation or human visual readability approval. The command was run by the assistant; the harness actor field is configured identity and is not a user co-sign.
## P5 post-fix independent verification — 2026-10-11

An independent tester re-ran the new Frontend trace-validator regression and the broader Frontend suite after the live trace rendering defect was fixed.

- `npm test -- --reporter=dot src/api/contractGraph.test.ts`: PASS, 1 file / 5 tests.
- `npm test -- --reporter=dot`: PASS, 36 files / 140 tests.
- `npm run lint`: PASS, 0 errors / 14 warnings (including one fast-refresh warning in the standalone manual entrypoint).
- `npm run build`: PASS; Vite continues to report chunks larger than 500 kB.
- Playwright against the isolated live stack: graph toggle present, graph shown, relation text visible, graph and processing trace HTTP 200, 0 browser errors. The trace timeline shows “Hoàn tất xử lý AI2” and its completed stage.
- Screenshot: `C:/Users/dungs/AppData/Local/Temp/ai2-graph-ui-live-citation/live-ui-graph-rerun.png` (temporary machine-local evidence).

This verifies the Frontend ↔ Backend read/display path for one synthetic REFERENCE edge. The graph and trace rows were seeded directly in the isolated database; this does not verify AI2 graph generation. Browser run was executed by the independent tester and is not a user co-sign of visual acceptance.

## Offline manual graph fixture regression — 2026-10-11

- The standalone preview at `http://127.0.0.1:5174/manual-ai2-graph.html` now renders a self-contained synthetic fixture. It does not call Backend APIs and explicitly says the data is synthetic and is not AI2 output from a user's documents.
- Browser result: timeline, graph canvas, `REFERENCE`, `CONFLICT`, and `GENERAL_SPECIFIC` all visible; zero `/api/v1/` requests; zero page errors.
- Visual follow-up: widened the edge label box so `GENERAL_SPECIFIC · cần review` fits; replaced the epoch test timestamp so the timeline no longer renders 1970.
- Evidence: [offline preview screenshot](reports/manual-ai2-graph-offline.png); automated browser receipt: `reports/manual-ai2-graph-offline-verification.json`.
- Validation after changes: Frontend 36 files / 141 tests PASS; lint 0 errors / 13 warnings; production build PASS (existing large-chunk warning).
- Scope limit: the fixture is intentionally synthetic and does not exercise AI2 generation or Backend ACL. It makes visual inspection convenient; visual acceptance remains for the user to co-sign.

## Final P5 acceptance review — 2026-10-11

- Re-ran the 320 CSS px Edge/Playwright charter on the composed AI2 graph view after correcting the synthetic trace timestamp. Result: viewport/document/body widths 320 px; visible keyboard focus; Space selected `CONFLICT`; inspector followed selection; citation callback displayed `demo:body-4-2`; no page errors; no 1970 timestamp.
- Refreshed screenshot: [320 CSS px capture](reports/ai2-graph-manual-320px.png). The relation canvas is a compact overview at this width; list and inspector provide the readable full text path. Reviewed the refreshed screenshot and found the layout readable and non-clipping.
- The standalone no-login preview also passed: all relation labels and timeline visible, no `/api/v1/` requests, no browser errors. See [offline demo capture](reports/manual-ai2-graph-offline.png) and `reports/manual-ai2-graph-offline-verification.json`.
- The authenticated live citation smoke remains valid for the synthetic isolated stack described above; it proves Backend ACL, graph/trace reads, and linked document retrieval, not actual graph generation.
- Decision: the plan's P5 manual UI acceptance is satisfied by the recorded browser checks and visual review. No separate user co-sign was captured; the co-sign was not part of the phase acceptance criteria. Runtime AI2 graph flags remain default OFF.

## Live application mobile shell and terminal failure states — 2026-10-11

- Repeated Edge/Playwright against the authenticated composed app route at 320 CSS px after making the application shell responsive. The actual `main` content width is 320 px; document/body also remain 320 px. The mobile menu opens, focuses its first item, closes with Escape, and restores focus to its trigger. Graph selection, evidence action, graph/trace API responses (200/200), and zero page errors pass.
- Screenshot: [actual application at 320 CSS px](reports/ai2-graph-live-320px.png). Machine-readable receipt: [live 320px verification](reports/live-ui-320-verification.json).
- Data limitation: graph/trace rows are synthetic and seeded in the isolated local stack. The screenshot verifies the composed UI and responsive shell; it does not prove that AI2 generated the graph from OCR input.
- Fixed terminal state propagation found during final review: operation/pair builder failures now survive in-memory pipeline records and persist as `FAILED` stage receipts; graph reads report terminal failure instead of `PENDING`; trace projection preserves its completeness status while recording the stage as `FAILED`; job outcome is carried separately in `job_status`; Backend and Frontend preserve `job_status`, allowing the timeline to distinguish failed and cancelled jobs from success.
- Regression evidence: AI service full suite 1606 passed / 9 skipped; Backend full suite 659 passed / 18 skipped (PostgreSQL-only tests require `CI_TEST_POSTGRES_URL`); Frontend 145 passed across 37 files, lint 0 errors / 13 warnings, production build passed. Build reports the existing large-chunk advisory.
- Runtime graph and UI flags remain OFF by default.

## Mobile drawer keyboard boundary regression — 2026-10-11

- Repeated authenticated Edge/Playwright at 320 CSS px after the focus-trap update.
- `Tab` from the last drawer control wrapped to the first; `Shift+Tab` from the first wrapped to the last. Choosing a navigation link closed the drawer and restored focus to its trigger; Escape did the same.
- Graph toggle and relation were visible, selected relation retained its evidence button, graph/trace reads returned HTTP 200, viewport/body/document/main widths were all 320 px, and there were zero browser errors.
- Receipt: `reports/live-ui-320-verification.json`; screenshot: `reports/ai2-graph-live-320px.png`.
- The API fixture remains synthetic and seeded. This proves behavior of the application UI and read path only, not AI2 graph generation.

## Final responsive shell breakpoint follow-up ? 2026-10-12

- At 320 CSS px, verified both Tab directions wrap within the mobile drawer; selecting a link closes it and restores trigger focus; Escape does the same.
- Resizing an open drawer to 800 px closes the mobile dialog and removes modal semantics/focus trap; keyboard navigation proceeds through the desktop sidebar normally. Returning to 320 px and pressing Escape again restores focus correctly.
- Receipt: `reports/live-ui-320-verification.json`; screenshot: `reports/ai2-graph-live-320px.png`. API data remains synthetic and seeded.
