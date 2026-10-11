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
