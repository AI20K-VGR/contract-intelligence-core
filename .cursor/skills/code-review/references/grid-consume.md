# Grid coverage — advisory consume (on-demand)

Load during a review when a coverage-grid artifact may exist. If
`plans/<active>/artifacts/coverage-grid.<yaml|json>` is present, read its `verdict`
(`pass | needs-detail | reject`) and evidence; if absent, do nothing — stay silent, never
nag.

## Read

- `verdict` — `pass | needs-detail | reject`.
- Evidence: `attestation.invariants_failed[]`, `attestation.confab_signals[]` — the axis/cell
  hit by a blocking invariant or a confab signal.

## A `reject` grid is ONE finding — not an auto-verdict

- `reject` → add it to the review's finding set. Score its severity with
  `"${HARNESS_BIN_ROOT:-.}"/harness/rules/scoring-rigor-contract.md` and this skill's `references/severity-taxonomy.md`;
  the evidence is the blocking-invariant / confab cell the grid names.
- `pass` or absent → add no finding.

**Advisory-first — never auto-BLOCKED.** A `reject` grid does NOT force
`review-decision.verdict = BLOCKED`. The final verdict still follows
`references/verdict-truth-table.md` plus the reviewer's judgement — the grid is an input, not
a conclusion. The reviewer MAY promote it to a Critical finding when the code evidence
confirms it, but that is a reviewer decision, not an auto-wire.
