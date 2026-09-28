# Scoring-rigor contract (on-demand)

Load when `hs:critique`'s consolidator ranks findings, or `hs:code-review`'s
truth-table adjudicates one. Pin every score to an EXISTING scale — never
invent a 4th, competing scale vocabulary anywhere a finding or verdict is
scored.

## Three scales, exactly

| Scale | Values | Owner |
|---|---|---|
| finding severity | `blocker \| major \| minor` | `hs:critique` finding contract (`critique/SKILL.md`) |
| plan red-team severity | `C/H/M/L` | `hs:plan`'s red-team reference (grep the scale, not a filename — the reference file has been renamed once already) |
| gate verdict | `PASS \| PASS_WITH_RISK \| BLOCKED` | `critique.yaml` / gate schemas |

### pinned example — finding severity

A lens reports `"severity": "major"` on a missing input-validation check: blast
radius is real but reachability needs an auth bypass first, so `major` (not
`blocker`) is the correct label — pin it to the finding contract's own enum, do
not paraphrase it ("high-ish", "pretty bad", "sev-2").

### pinned example — red-team severity

A plan red-teamer rates a missing rollback step `H` (High): the failure mode is
a stuck gate with no rescue path, not a crash — `H`, not a bespoke "critical"
label sitting outside the `C/H/M/L` set.

### pinned example — gate verdict

A critique consolidator proposes `PASS_WITH_RISK`, never a home-grown
"conditional pass": the gate schema's enum is exactly `PASS | PASS_WITH_RISK |
BLOCKED` — the enum member IS the value, not a synonym standing in for it.

## No-4th-scale rule

Do not add a 4th severity/verdict vocabulary anywhere findings are scored —
reuse the scale the consumer already reads. A new scale fragments existing
gates (a DoD-style consumer keys by canonical name; an unmapped label reads as
absent, not lenient) and forces every downstream reader to learn a second
mapping for the same judgment. Extending what an EXISTING value covers
(documenting the boundary of `major`) is fine; adding a competing scale beside
it is not.
