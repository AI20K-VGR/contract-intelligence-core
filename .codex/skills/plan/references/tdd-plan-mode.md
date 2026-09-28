# TDD plan mode — --tdd flag for hs:plan (on-demand)

Orthogonal to all modes (`fast`, `hard`). Combine as: `--hard --tdd`, `--fast --tdd`.
Goal: each phase in the plan contains enough information for cook to run red->green in the correct order — cook should not have to infer which test to write first.

## Seed the test list from an edge-case sweep (code phases)

The planner free-hands "which behaviors to lock" below. For a phase that introduces real behavior or a contract change — not a doc-only, config, or trivial phase — first
**consider** `hs:scenario <target> --domain software` to decompose the code-path across the 13 edge dimensions (timing/race, authorization, data integrity, integration, error cascades, …), then feed the Critical/High rows into **Tests Before / Tests After** below. This enriches the existing lists; it does **not** add a parallel matrix (on `--deep` it replaces the free-hand "Test scenario
matrix"). Advisory, not a gate —
**skip it for doc-only / config / trivial phases** where a 13-dimension sweep yields nothing.

## Add to each phase file when --tdd

```
### Tests Before (regression coverage written BEFORE refactoring)
- [ ] test_<current-behavior>: lock existing correct behavior against breakage.
- [ ] Run -> intentional FAIL (behavior not yet present) or PASS (lock regression).

### Implement
- Specific steps (see Implementation Steps).

### Tests After (new behavior)
- [ ] test_<new-behavior>: assert the behavior this phase introduces.

### Regression Gate
`python3 -m pytest harness/tests/ -q` (or the target repo suite) — MUST PASS
before moving to the next phase.
```

## TDD rules in the plan

1. **Tests Before always have a reason**: each "Tests Before" item states clearly *what it is locking* — not a placeholder.
2. **Regression Gate is a real command**: do not write "run tests" generically; record the specific command so cook does not have to guess.
3. **No phase without a gate**: if a phase has no tests (e.g. doc-only), write "Regression Gate: N/A — reason" explicitly rather than leaving it blank.
4. **Cook reads the gate and runs it before committing**: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md` mandates "100% pass is the gate" — the plan only needs to state the correct command.

## Verification artifact

After each phase, cook writes `verification.json` (`harness/schemas/artifact-verification.json`) with verdict + checks[]. The stage gate (`harness/hooks/gate_stage.py`) reads this file before allowing push/pr/ship — TDD plan mode does not change the gate; it ensures cook has sufficient tests for verdict = PASS.

## Backing

- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md` — detailed red->green rules (cook reads directly).
- `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json` — verification.json schema.
- `"${HARNESS_BIN_ROOT:-.}"/harness/hooks/gate_stage.py` — reads verification.json, blocks ship on FAIL.
