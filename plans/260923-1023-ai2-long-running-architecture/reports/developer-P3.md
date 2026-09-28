# Developer report — P3

## Scope

Implemented durable-friendly local persistence primitives for run snapshots, checkpoints, events, audit, outbox and lease fencing. P4 was not started.

## Changes

- Added `ai-service/app/tools/durable.py` with SQLite transactions, snapshot/checkpoint digest validation, contiguous event append, event/outbox atomicity, replay/snapshot fallback, append-only audit triggers, lease reclaim and worker fencing.
- Updated `ai-service/app/tools/jobs.py` with durable store/error exports.
- Added `ai-service/tests/test_p3_persistence_events.py`.
- Added `artifacts/p3-replay-convergence.json`.

## Independent verification

- P3 plus job/persistence/P2/P1/P0 regression: `41 passed, 1 warning`.
- `compileall`: PASS.
- `git diff --check`: PASS.

## Acceptance

- Snapshot/checkpoint round-trip after reopening SQLite: PASS.
- Duplicate/conflicting event and sequence gap detection: PASS.
- Transactional outbox retry/dedup: PASS.
- Replay convergence and snapshot fallback: PASS.
- Snapshot corruption fail-closed: PASS.
- Lease reclaim fences stale worker; audit is append-only: PASS.

## Known limitation

This phase proves local durable primitives only. It does not claim production HA, queue delivery, external exactly-once side effects, scheduler integration, retention policy or RTO/RPO.
