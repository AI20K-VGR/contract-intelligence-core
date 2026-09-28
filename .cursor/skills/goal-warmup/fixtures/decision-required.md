# Fixture: Decision required

## Input

Goal: "Ship feature X to production this week."

During review/preflight: production publish needs explicit human approval that
was not granted; contract listed production ship as in-scope without approval path.

## Expected classification

At least one `outcome-change-request` or decision gate:

Options example:

1. Keep production ship — user grants approval now
2. Reduce to staging only — requires contract re-approval
3. Abort warmup

## Expected terminal state

**Decision required** — wait for user; do not silently shrink to staging.

## Assertions

- MUST present options + consequences
- MUST NOT mutate locked contract without re-approval
- MUST NOT start the long run
