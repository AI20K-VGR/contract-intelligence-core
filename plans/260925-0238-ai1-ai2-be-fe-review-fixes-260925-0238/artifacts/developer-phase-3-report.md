# Developer report — phase-3-query-grounding-state

## Delegated red phase

The delegated developer lane created the AI-service fallback and Backend state
passthrough tests and stopped safely before product implementation. The red run
reported `10 failed, 2 passed` in the new AI-service query tests, matching the
known gaps: no bounded lexical fallback, missing retrieval/trace/LLM metadata,
and API state loss.

## Main-thread completion

The main thread implemented dossier-scoped lexical fallback before optional
vector recall, policy-gated LLM/vector execution, and explicit retrieval layer,
reasoning trace and `used_llm` fields. It bypasses the old unscoped outline hint
until bounded lexical retrieval has been attempted. Backend search DTO mapping
now preserves server state and never infers semantic success from answer/hits.
Frontend normalization preserves `PASS`, review states, retrieval metadata and
trace and fails closed when the server omits state.

## Verification

- AI-service query/fallback/grounding/regression/context tests: `35 passed`
- Backend query passthrough + contract router tests: `29 passed`
- Frontend `ai2-query-state.test.ts` + `ai2-contract.test.ts`: `6 passed`
- Frontend build: PASS (existing chunk-size warning)
- Frontend lint: 0 errors, 7 existing warnings
- Targeted AI-service ruff for phase-3 files: PASS
- Targeted Backend ruff for phase-3 files: PASS

The full AI-service ruff command still reports unrelated baseline findings in
files outside phase 3; it is intentionally not used as a blocking PASS claim.
