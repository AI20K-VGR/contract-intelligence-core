# P2 implementation notes

## Changes

- Added an append-only trace store using the selected SQLite/PostgreSQL job database, plus PostgreSQL migration `0008_ai2_processing_trace`.
- Added a signed internal trace read route. The projection exposes allowlisted stage status, timing, counts and safe reason codes only.
- Instrumented operation and pair graph stages on the signed HTTP worker lane. Explicitly disabled/skipped stages are represented as `SKIPPED`; non-HTTP call sites remain uninstrumented and therefore unavailable.
- Added execution-scoped worker token fencing. Stale workers cannot append after lease reclaim.
- The active `current_execution_id` is now persisted atomically with each lease claim/reclaim. Appends require both the active worker token and execution ID; reads select only the persisted active execution, so a retry before its first stage event cannot expose prior-attempt stages.
- Added stale-job finalization to `INTERRUPTED_UNKNOWN`; terminal jobs with a dangling start remain `INCOMPLETE_UNKNOWN` if finalization did not persist.
- Trace-store failures set separate telemetry status `UNAVAILABLE` and do not change the AI2 result wire.
- Updated migration head/downgrade expectations in existing P1 PostgreSQL tests for the additive P2 migration.

## Verification evidence

- Reclaim-before-first-stage regression was red before the fix and now passes for SQLite and PostgreSQL; `uv run pytest tests/test_contract_graph_trace_durability.py -q` — 13 passed.
- Combined trace, graph/PostgreSQL/API/job regressions after the retry-window fix — 66 passed.
- `uv run ruff check` over changed P2 implementation and integration test files — passed.
- Independent review of the retry-window fix — PASS; reviewer confirmed persisted active execution, dual fencing, and no stale stages before first new marker.
- Full AI2 regression after all P2 changes: `uv run pytest -q` — 1,599 passed, 9 skipped, 25 warnings, 0 failures (236.92s).
- Broad package Ruff gate reports seven import-order findings in existing files outside the P2 change set: `pipeline/__init__.py`, `adk_adapter.py`, `ai1_ocr_lab_adapter.py`, `execution.py`, `index.py`, `table.py`, and `tools/__init__.py`. Those files were not changed as part of P2.

## Gate status

P2 implementation and crash/retry behavior are verified by focused SQLite and real PostgreSQL tests; the full AI2 regression suite passes. Runtime flags remain unchanged. No commit was made.
