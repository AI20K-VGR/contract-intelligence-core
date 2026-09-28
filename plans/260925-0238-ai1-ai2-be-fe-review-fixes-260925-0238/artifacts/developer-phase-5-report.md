# Developer report — phase-5-snapshot-recovery-legacy

## TDD

- RED: new snapshot recovery tests initially failed at collection because the durable hydration and canonical mode guard did not exist.
- GREEN: backend phase regression passed (`9 passed`); AI-service canonical/legacy regression passed (`26 passed`).

## Implementation

- Persist AI1 canonical snapshots in the durable `pipeline_run.config_snapshot` projection with per-document digests.
- Hydrate the working snapshot set from the durable projection before consulting `_snapshot_cache`; malformed or unscoped entries are ignored.
- Skip duplicate AI2 work after a durable AI2 result digest is present, including after worker restart.
- Set canonical service default to HTTP in Settings and Docker Compose. Stub remains an explicit compatibility client for tests/demo.
- Keep AI2 legacy OCR endpoint explicit and non-canonical (`501`); it cannot produce an AI2 result.

## Verification

- Backend targeted ruff: PASS.
- AI-service targeted regression: PASS with framework deprecation warnings only.
- Full AI-service lint remains a pre-existing baseline debt and is not claimed as PASS.

## Risks

- Durable snapshot projection uses the existing JSON config column; a dedicated snapshot table may be preferable if snapshot volume becomes large.
- In-flight crash exactly between external AI2 submission and durable result receipt still relies on AI2 idempotency; the worker request keeps a stable run-derived idempotency key.
