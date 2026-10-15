# Renderer spike: inline SVG and accessible list

Date: 2026-10-11  
Plan: `261011-1654-ai2-graph-ui`  
Decision: keep a dependency-free, read-only SVG overview beside the paged relation list and processing timeline. No third-party renderer or layout dependency was added. The SVG shows only the current Backend page; the list remains the full traversal and evidence-action fallback.

## Fixture

- Synthetic and scrubbed; no contract wording, personal information, or real citation data.
- 30 pair edges; 40 unique node IDs: 10 body clauses and 30 clauses distributed across four annex IDs.
- Labels rotate through `REFERENCE`, `CONFLICT`, and `GENERAL_SPECIFIC`; edges include directed and undirected cases and review states.
- Canonical JSON SHA-256: `ffc9639c8305ea1fd2cdb77672a44954508d1f1f4099e0849741e5aaabba76bb`.
- Page scope: 30 displayed of 250 total, `has_more=true`; checks that both views state the page is incomplete.

## Measurements

Environment: Windows, Node v24.18.1, Vitest 3.2.7, React static server rendering. Each reported batch includes one warmup followed by eight renders.

| View                      | Static output | Eight-render batch (latest full-suite run) |
| ------------------------- | ------------: | -----------------------------------------: |
| Inline SVG                |  28,879 bytes |                                  117.65 ms |
| Relation list + inspector |  18,381 bytes |                                  121.19 ms |

The static output is deterministic; timings vary substantially with test-run load and do not establish browser layout or interaction performance. The SVG output is 10,498 bytes larger for this fixture. It adds keyboard-selectable edge controls and a visual overview; the list carries the complete accessible interaction path.

Production bundle comparison against the P4 build: JavaScript grew from 1,261.61 kB (361.68 kB gzip) to 1,283.79 kB (367.99 kB gzip), a +22.18 kB / +6.31 kB gzip delta. CSS grew by 0.44 kB (0.07 kB gzip). No renderer dependency was added. `package.json` is unchanged; `package-lock.json` separately updates `source-map-js` from 1.2.1 to 1.2.2 to clear a production dependency advisory.

## Browser and limits

Manual browser session: Microsoft Edge 154.0.4258.62 headless, driven by Playwright 1.64.0, Node v24.18.1. The actual `Ai2GraphDossierView` rendered a scrubbed three-edge fixture while its graph and trace HTTP responses were intercepted with schema-valid fixture payloads. At a 320×900 CSS px viewport, `documentElement.scrollWidth=320` and `body.scrollWidth=320`; there was no horizontal overflow. Tab focused the first SVG relation with a visible focus outline; a second Tab plus Space selected the `CONFLICT` relation. The inspector updated to that relation and its source-evidence action callback fired. No browser page errors occurred. Screenshot: [320 CSS px manual view](ai2-graph-manual-320px.png).

This browser session checks the composed timeline/canvas/list/inspector rendering and local interactions using mocked API data; it does not itself verify Backend ACL or real citation navigation. The separate authenticated API smoke below verifies the live Backend/AI2 read, ACL, trace, and document-content paths against synthetic seeded graph/trace rows. Human sign-off of visual readability remains outstanding.

The normal Frontend dev server remains at `http://127.0.0.1:5173/`. The isolated UI fixture is served at `http://127.0.0.1:5174/manual-ai2-graph.html` with mocked graph/trace responses. For a live Backend/AI2 check, a separate Compose project used cached development images and mounted the current Backend/AI2 source. It ran Backend at `http://127.0.0.1:18000`, AI2 at `http://127.0.0.1:18002`, Keycloak at `http://localhost:8080`, and project-scoped Postgres/MinIO volumes. Its network and host ports were isolated; the existing database on 5434 and its volume were not reused.

Authenticated live smoke: Backend returned the seeded synthetic `REFERENCE` graph as `READY`, AI2 trace as `AVAILABLE`, and both linked PDF documents as HTTP 200 through Backend. Anonymous access returned 401; an unshared same-tenant operator returned 403. The graph response excluded citation text/span. The relation, receipt, and trace were seeded directly in the isolated AI2 PostgreSQL schema, so this validates real Backend/AI2 signed read, ACL, provenance projection, and citation retrieval; it does not validate graph generation by the AI2 pipeline. Full receipt: [live citation E2E](live-citation-e2e.json).

`frontend/src/api/client.ts` defaults to `http://127.0.0.1:8080`; for the isolated live Backend, a local Frontend must use `VITE_API_BASE_URL=http://127.0.0.1:18000` and `VITE_KEYCLOAK_URL=http://localhost:8080`.
