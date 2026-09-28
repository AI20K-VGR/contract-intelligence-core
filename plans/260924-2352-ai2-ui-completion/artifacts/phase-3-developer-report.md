# Phase 3 developer report — HITL review workflow

## Implemented

- Added `frontend/src/api/review.ts` with typed queue, item, revision, action, dossier lock and approval contracts.
- Added runtime normalization for review items and append-only revisions.
- Added optimistic-lock action submission using `base_version` and `Idempotency-Key`.
- Extended `ApiError` to retain the structured error body and mapped HTTP 409 to `ReviewConflictError` with current state.
- Replaced dossier-scoped static activity output with a live HITL queue in `DossierReviewPage`.
- Added confirm, correct, reject and needs-more-evidence controls.
- Added correction draft input, revision timeline loading, conflict refresh and dossier lock/approve controls.
- Kept the legacy static audit view only for the global activity route where no dossier scope is available.

## Verification

- Frontend tests: `8 passed`.
- Frontend build: PASS.
- Frontend lint: PASS with 6 pre-existing warnings, 0 errors.
- Backend review/approval tests: `21 passed`, 1 pytest cache permission warning.
- `git diff --check`: no whitespace errors.

## Known limitation

- The live browser path still requires an authenticated reviewer/admin token and a dossier containing review items. The API client and backend contract tests are covered; a browser session probe was not counted as a passing check because the available session was not authenticated.
