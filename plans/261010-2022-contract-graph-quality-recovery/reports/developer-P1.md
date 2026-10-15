# Developer report — P1

- Status: DONE_WITH_CONCERNS; historical replay is explicitly incomplete.
- HEAD at start: `681ff4ca300b1d03c131453d5290f8bba1d9bc8f`.
- Owned source/test files were clean at start; unrelated worktree changes were left intact.
- TDD red: `5 failed, 137 passed`; failures matched the new event callback, predictor collection, and pair-level attribution contracts.
- Focused green: `143 passed in 1.55s`.
- Consent/flag-off regression: `16 passed in 143.92s`.
- `git diff --check`: PASS. No provider requests and no commit.
- Artifacts: `evals/contract_graph/reports/quality-recovery-p1-evidence.json`, `evals/contract_graph/reports/quality-recovery-p1-evidence.md`, and `artifacts/verification-P1.json`.
- Historical replay: `INCOMPLETE_HISTORICAL_REPLAY`; hashes for `pair_classifier.py`, `predictor.py`, `bakeoff.py`, and `score.py` do not match the diagnostic commit. Historical pair-level causes remain unknown where snapshots contain aggregate counters only.
- Implementation adds opt-in content-safe pair/batch telemetry, default off; diagnostic consumes exact events when present and does not infer pair causes from aggregate counters.
