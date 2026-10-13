# P3 implementation record

## Implemented

- Added a dry-run-first consent rollout command with a reviewed candidate digest, explicit `--apply`, idempotent audit event IDs, deleted/purged exclusions, and append-only compensating rollback. Rollback preview is non-mutating; rollback apply requires the same explicit apply and digest gates.
- Added a dossier-scoped consent endpoint with tenant/owner-or-administrator checks, row locking, strict boolean input, response effective on the next request, and an audit event in the request transaction.
- Added the consent checkbox beside the AI2 graph controls. It fails closed on missing metadata, confirms enabling, reports pending/error state, and only changes displayed state after a successful response.
- Added SQLite integration coverage for legacy states, malformed consent, deleted/purged exclusions, repeat execution, future opt-out protection, rollback restoration/skip, endpoint ACL, and audit failure atomicity; added a PostgreSQL row-lock race test for CI.

## Red/green and verification

- TDD red: initial test collection failed because the rollout module did not exist. After implementation, focused rollout/API tests passed.
- `uv run ruff check ...` — PASS for the P3 Python files.
- `uv run pytest tests/integration/test_ai2_consent_rollout.py tests/integration/test_tenant_isolation.py -q` — 6 passed, 1 skipped. The skipped case is the real PostgreSQL opt-out/rollback race because this machine has no `CI_TEST_POSTGRES_URL` and its Docker daemon is unavailable.
- Frontend: full Vitest suite 146 passed; production build passed; ESLint passed with 13 existing warnings and no errors.
- No operational backfill was run. The command is only exercised against isolated SQLite fixtures; applying to deployed data still requires reviewing the candidate count/digest.

## Follow-up gate

The PostgreSQL race test must pass in backend CI before P3 is marked PASS. The deploy workflow currently triggers on pushes to `develop` (after PR merge); P5 will verify fail-closed deployment configuration and that all requested runtime AI2 capabilities remain enabled by default.
