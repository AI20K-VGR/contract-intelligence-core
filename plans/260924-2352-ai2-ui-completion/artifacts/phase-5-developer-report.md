# Phase 5 developer report — release gate

## Implemented

- Added dossier-scoped CSV export containing dossier id, query, answer, review state, citation status, source file, line, page, bbox and quote.
- Kept the legacy static audit export only for the global activity route without dossier scope; dossier review export now uses live result/review state.
- Added `scripts/ai2_release_smoke.py`, a secret-safe smoke probe for backend health, AI2 health, frontend root and optional authenticated dossier detail.
- Added release checklist artifact with explicit PASS/NOT_RUN states and Docker service observations.
- No query-history persistence was claimed because no backend query-history endpoint/DTO exists in the current contract.

## Verification

- AI2 offline suite: `687 passed, 6 deselected` using `-m "not live"`.
- Frontend tests: `10 passed`.
- Frontend build: PASS.
- Frontend changed-file Prettier check: PASS.
- Frontend lint: PASS with 6 pre-existing warnings and 0 errors.
- Docker smoke: backend health PASS, AI2 health PASS with `llm=ready`, frontend root PASS.
- Authenticated end-to-end dossier smoke: `NOT_RUN` because no token/dossier was supplied.

## Release boundary

- The authenticated upload → OCR → AI1 → AI2 → click citation → HITL → approve path still needs one manual run with a valid Keycloak user and a real dossier. The release artifact records this as `NOT_RUN`, not PASS.
