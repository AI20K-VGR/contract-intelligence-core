# Developer report — P1

## Scope

Implemented canonical AI2 domain projection, segmentation/evidence validation and dependency stale propagation. P2 was not started.

## Changes

- Added `ai-service/app/contracts/canonical.py` with canonical run, snapshot, logical document, boundary, party, clause, fact, relation, citation, generation and dependency models.
- Added `ai-service/app/pipeline/canonical.py` with deterministic mapping, source-reference validation, confidence/quality flags and stale dependency propagation.
- Added read-only `adapt_to_canonical_ai2_run` compatibility seam in `ai-service/app/pipeline/ai1_snapshot_adapter.py`.
- Added `ai-service/tests/test_p1_canonical_model.py`.
- Added `plans/260923-1023-ai2-long-running-architecture/artifacts/p1-domain-schema.json`.

## Developer verification

- Focused P1 tests: `9 passed`.
- P1 plus AI1 adapter/contract/P0/context regression: `49 passed, 1 warning`.
- `compileall`: PASS.
- Artifact JSON validation: PASS.

## Acceptance

- One JSON can map multiple logical documents while retaining raw source: PASS.
- Missing/low-confidence evidence remains non-confirmed and reviewable: PASS.
- Body/annex relation requires evidence or explicit reviewer decision: PASS.
- Generation is pinned to snapshot/segmentation/state versions: PASS.
- Annotation edits do not stale evidence; boundary/fact/relation edits stale derived generation: PASS.
- User context remains outside evidence-bearing objects: PASS.

## Known risk

Production persistence/replay and independent verification receipts remain owned by later phases. The `.pytest_cache` permission warning is environmental.
