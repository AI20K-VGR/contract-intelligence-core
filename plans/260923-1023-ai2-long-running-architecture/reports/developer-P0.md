# Developer report — P0

## Scope

Implemented P0 contract baseline only. P1 was not started.

## Changes

- Added `ai-service/tests/test_p0_contract_baseline.py` with executable cases for:
  - canonical AI1 snapshot vs legacy `ocr.json` compatibility lanes;
  - unknown fields and unsupported snapshot version;
  - missing document/evidence references;
  - multiple logical documents and explicit relation;
  - idempotent duplicate submission and conflicting payload rejection;
  - missing citation not being a successful/publishable result.
- Added `plans/260923-1023-ai2-long-running-architecture/artifacts/p0-contract-baseline.json`.
- Cook receipts were generated: `verification.json`, `verification-P0.json`, `phase-latest-P0.json`.

## Developer verification

- Developer test run: `68 passed, 1 deselected, 2 warnings`.
- `compileall`: PASS.
- JSON validation: PASS.
- `git diff --check`: PASS.

## Acceptance

- AI1→AI2 contract and legacy `ocr.json` remain separate: PASS.
- Unknown/missing/no-evidence behavior is executable: PASS.
- Multi-document and idempotency cases are covered: PASS.
- No AI1 producer or public schema change: PASS.

## Known risk

Production TTL and retention remain deployment policy. Full repository suite was not used as the developer's long-running command; main verification reran the focused P0 test independently.
