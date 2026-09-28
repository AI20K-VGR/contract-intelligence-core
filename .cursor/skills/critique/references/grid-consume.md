# Grid coverage — advisory consume (on-demand)

Load during a critique when a coverage-grid artifact may exist. If
`plans/<active>/artifacts/coverage-grid.<yaml|json>` is present, read its `verdict`
(`pass | needs-detail | reject`) and evidence; if absent, do nothing — stay silent, never
nag.

## Read

- `verdict` — `pass | needs-detail | reject`.
- Evidence: `attestation.invariants_failed[]`, `attestation.confab_signals[]`,
  `coverage_ratio` vs the density_tier `coverage_floor`.

## A `reject` grid is ONE finding in consolidation

Package it in the existing critique finding contract (the normalised JSON array):

- `anchor` = the artifact path + the blocking-invariant / confab-signal name (real evidence,
  never fabricated).
- `severity` per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/scoring-rigor-contract.md` (`blocker | major | minor`).
- `status` = `proven` (the grid is deterministic).
- `needs-detail` grid → a `minor` finding. `pass` or absent → no finding.

## Mode-aware, advisory

Default report-only: the grid finding goes into the report. In gate mode (`--gate`) it enters
consolidation into `critique-consensus.json`, where `hs:critique-consolidator` decides the
final verdict by the existing taxonomy — the grid does NOT force the verdict. The critique
enforcement gate ships OFF; consuming the grid does not turn it on. Keep the critique voice
neutral — this is evidence, not a jab.
