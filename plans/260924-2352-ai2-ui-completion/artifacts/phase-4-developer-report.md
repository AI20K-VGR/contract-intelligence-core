# Phase 4 developer report — structured contract analysis

## Implemented

- Added `frontend/src/api/analysis.ts` for the real extraction facts and conflict findings endpoints.
- Added runtime normalization for fact values, review state, confidence, current version, finding scope, severity, sides and evidence status.
- Added safe evidence states: `LOCATABLE`, `PARTIAL`, `UNRESOLVED`; only locatable evidence exposes an “Mở nguồn” navigation action.
- Replaced the dossier-scoped risk placeholder with structured facts/fields and findings/risk cards.
- Connected source navigation from locatable fact/finding evidence to the existing structure viewer.
- Kept table and clause views on their existing real APIs; no mock relation/comparison payload was introduced.

## Verification

- Frontend tests: `10 passed`.
- Frontend build: PASS.
- Frontend lint: PASS with 6 pre-existing warnings, 0 errors.
- Backend extraction/conflict tests: `19 passed`, 1 pytest cache permission warning.
- AI2 structured/grounding tests: `23 passed`, 7 pre-existing unknown-mark warnings.
- `git diff --check`: no whitespace errors.

## Contract boundary

- A dedicated relation-graph/risk endpoint is not exposed by the Backend API contract used by the frontend. Findings are shown from the real conflict endpoint and remain explicitly scoped/disclaimed. No fabricated relation or risk result is rendered.
