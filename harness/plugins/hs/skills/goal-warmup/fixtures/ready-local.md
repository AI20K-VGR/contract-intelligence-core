# Fixture: Ready — local task

## Input

Goal: "Add a pure helper `clamp(n, min, max)` in an existing utils module and unit tests."

Risk estimate: local-only, no external deps.

## Sample contract (approved)

- Intended result: `clamp` exported and tested
- In scope: helper + unit tests
- Out of scope: API routes, deploy
- Acceptance signals: unit tests pass for bounds
- Constraints: match existing code style
- Allowed substitutions: none
- Decision owner: user

## Expected review findings

- (none) or only `mitigation-within-contract` naming nits

## Expected preflight

| Phase | Requirement | Status | Blocking? |
|-------|-------------|--------|-----------|
| implement | language toolchain | available | no |
| test | test runner | available | no |

## Expected terminal state

**Ready** — handoff packet with the long-run opener; no blockers; never auto-starts the run.

## Assertions

- MUST include Outcome contract (LOCKED)
- MUST include Scope guard
- MUST NOT contain secret values
- MUST NOT start the long run automatically
