# P3 implementation notes

## Changes

- Added signed, bounded AI2 read adapters for graph pages and processing traces. Responses enforce strict field/status allowlists, per-edge tenant/dossier/job/snapshot identity, cursor consistency, safe reason codes, trace stage allowlists, timeouts and streaming byte ceilings (512 KB graph, 64 KB trace).
- Added Backend graph and trace routes guarded by `CITATION_READ` before and after each awaited AI2 call. The route re-fetches dossier scope and snapshot digest before serializing; ACL revocation returns 403 and snapshot changes return 409 without graph payload.
- Added an opaque HMAC cursor bound to tenant, dossier, job, snapshot digest and graph kind; each continued page repeats authorization and freshness checks.
- Added strict Backend response schema and frontend typed/runtime-validated client. The frontend client only calls Backend routes.
- Added scope identity fields to internal AI2 graph edge projections/schema so Backend can validate each returned row; Backend strips these internal fields from its public projection.
- Added streaming response-size and malformed `Content-Length` tests. Runtime feature flags remain unchanged/OFF.

## Verification evidence

- Backend focused tests: `uv run pytest tests/unit/test_ai2_contract_graph_adapter.py tests/unit/test_contract_graph_router.py -q` — 16 passed.
- Backend Ruff on the changed adapter, router and tests — passed.
- Frontend API client: `npm test -- --run src/api/contractGraph.test.ts` — 3 passed.
- AI2 graph-read/trace-focused tests — 22 passed, 2 warnings.
- Full AI2 suite: `uv run pytest -q` — 1,599 passed, 9 skipped, 25 warnings (247.03s).
- Full Backend suite: `uv run pytest -q` — 656 passed, 18 skipped, 32 warnings (336.69s). PostgreSQL integration cases skipped because `CI_TEST_POSTGRES_URL` was not set.
- Full Frontend suite — 118 passed across 34 files.
- Frontend lint — 0 errors, 13 existing warnings.
- Frontend production build — passed; existing bundle-size warning for chunks above 500 KB.

## Gate status

P3 implementation and regression gates pass. No public dossier DTO or AI2 processing wire v1 was changed. Runtime graph flags remain OFF. No deployment/live authenticated E2E was performed.
