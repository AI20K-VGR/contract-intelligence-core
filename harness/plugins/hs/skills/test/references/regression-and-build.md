# Regression and build (on-demand)

Load when: regression-testing a bug fix, or verifying a build after a change.

## Regression scope by change type

| Type | Minimum suite |
|---|---|
| Bug fix | test targeting the exact bug (written BEFORE fix, intentional failure) + full module suite |
| Refactor | existing full suite — no new tests unless a gap is found |
| Public contract change | full suite + integration if contract is used cross-module |
| Dependency bump | full unit suite + smoke integration |

## Fix loop: hs:test → hs:cook

When failures occur (handoff #7 in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md`):

1. QA report lists ALL failures — do not summarize away names
2. Hand back to hs:cook (or hs:fix for a single bug) with the failure list + root cause
3. hs:cook fixes → hs:test re-runs — repeat until suite is green
4. Deleting / skipping / weakening tests to exit the loop is forbidden — fix the actual code

If the failure is due to a **genuinely wrong test** (assertion contradicts the spec): fix the test + document the reason in the commit message.

## Build verification (Python harness)

```bash
# Preflight — if dep is missing, stop here
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/preflight_deps.py

# Quick import check on the recently modified module
python3 -c "import harness.recently_modified_module"

# Full suite
python3 -m pytest harness/tests/ -q

# E2e (before a hard stage)
python3 "${HARNESS_BIN_ROOT:-.}"/harness/e2e/run_vertical_slice.py

# Full install verification
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/verify_install.py --strict
```

Build warnings do not block but should be recorded in `PASS_WITH_RISK` if they relate to a dependency or deprecation that affects correctness.

## Pre-verification close checklist

- [ ] Full unit suite: 0 failures
- [ ] Import check of recently modified module: OK
- [ ] Coverage has not dropped below threshold (80% line, 70% branch)
- [ ] No skips hiding a failure
- [ ] E2e (if integration stage): block-then-pass OK
- [ ] `verification.json` has been written (`references/verification-artifact.md`)
