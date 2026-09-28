# Grid coverage — advisory consume (on-demand)

Load when `hs:test` runs and a coverage-grid artifact may exist. If
`plans/<active>/artifacts/coverage-grid.<yaml|json>` is present, read its `verdict`
(`pass | needs-detail | reject`) and evidence; fold it into the QA report as an advisory
line. If the artifact is absent, do nothing — stay silent, never nag.

## Read

- `verdict` — `pass | needs-detail | reject`.
- Evidence for a non-pass: `attestation.invariants_failed[]`, `attestation.confab_signals[]`,
  `coverage_ratio` vs the density_tier `coverage_floor`.

## Fold into the QA report — never change the test verdict

- `reject` grid → add one line to the QA report: `grid-coverage: REJECT — <first reason>`.
- `needs-detail` grid → add one short note line.
- `pass` or absent → add nothing.

**HARD INVARIANT:** the grid verdict must NEVER flip `verification.yaml`'s verdict to
FAIL/BLOCKED. `hs:test`'s hard gate stays "100% tests pass"
(`"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md`). The grid is an advisory overlay — turning it into a
hard gate violates personal-first and inflates this skill's scope. It is a note in the QA
report, nothing more.
