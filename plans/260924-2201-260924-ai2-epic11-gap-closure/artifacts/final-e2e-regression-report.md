# Final E2E / regression report — EPIC-11 AI2

## Executed evidence

- AI2 targeted ST-047 and related index/wire/policy tests: `62 passed`, exit code `0`.
- AI2 full suite: `692 passed, 1 skipped, 27 warnings`, exit code `0`.
- Backend query adapter smoke: `PASS`; asserted `query_contract_version=ai2.query.v1`, `snapshot_digest`, and `ai2.query` service-envelope scope.
- Backend query/dossier/AI2 filtered suite: `78 passed, 184 deselected`, exit code `0`.
- Backend reviewer gate: `2 passed`, exit code `0`.
- Backend full suite: `264 passed, 28 warnings`, exit code `0`.
- Backend ruff: `All checks passed`, exit code `0`.

## Final state

- ST-044, ST-045 and ST-046 evidence is green in their phase artifacts.
- ST-047 AI2 proposal invariant is green: AI2 only emits `publish=propose` and does not move `active_pointer`.
- Backend reviewer gate now has an explicit scoped interface: reject leaves the active pointer unchanged; approve changes it; retries are idempotent and audit the tenant/dossier/digest/reviewer decision.
- Final E2E/regression status: `PASS`.
