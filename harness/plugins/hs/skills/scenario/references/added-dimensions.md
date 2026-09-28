# Added scenario dimensions (14-15) — stakeholder & lifecycle (on-demand)

A `hs:scenario` reference that adds two orthogonal decomposition dimensions to the
existing 13: **(14) Stakeholder Perspectives** and **(15) Lifecycle Stage**. They surface
edge cases by *who is affected* and *which lifecycle stage* — angles the current 13
dimensions do not cover systematically. The machine-readable values live in the SSOT at
[`../data/added-dimensions.yaml`](../data/added-dimensions.yaml).

## Orthogonal with the coverage grid

These are **scenario dimensions**, not grid cells. A scenario dimension drives
LLM-generated edge cases along an axis; the deterministic coverage grid
(`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/grid/`) enumerates a Cartesian lattice with anti-confabulation
invariants. They are different mechanisms with different guarantees — do not confuse a
scenario dimension for a grid cell, and this reference never imports the grid engine.

## The two dimensions

| # | Dimension | Values | What to look for |
|---|---|---|---|
| 14 | **Stakeholder Perspectives** | dev, ops, security, support, end-user, admin | An edge case that only bites one stakeholder class — noisy alerts for ops, an audit gap for security, a confusing error for the end-user — that a feature-first pass misses. |
| 15 | **Lifecycle Stage** | discover, design, build, ship, measure, deprecate, migrate | A failure that lives in a specific lifecycle stage — a bad rollback at ship, a missing signal at measure, stranded data at deprecate/migrate — that a build-time-only view misses. |

## Applicability (filter first)

Like the 13 base dimensions, filter before generating — not every dimension applies:

- **Stakeholder Perspectives** applies when there is more than one class of user or
  operator; skip a pure internal library with a single caller.
- **Lifecycle Stage** applies when the feature outlives one release, changes shape over
  time, or will eventually be retired/migrated; skip a throwaway one-off.

## Compose with the 13 base dimensions

Run these two after the base 13, as an additional pass: for each applicable value, generate
3–5 scenarios and classify severity on the same scale the skill already uses — Critical
(data loss, auth bypass, silent corruption) / High (broken for a segment, data
inconsistency) / Medium (degraded UX, unsurfaced recoverable error) / Low (minor glitch,
non-blocking warning). A stakeholder or lifecycle scenario can compose with a base
dimension (e.g. dimension 7 Error Cascades × stakeholder ops = "DB down, ops gets 400
duplicate pages").

## Boundary

This reference and its data file are additive only. Routing them into `scenario/SKILL.md`
and bumping the visible dimension count from 13 to 15 is the scenario-skill integration
phase's job — this reference does not modify `scenario/SKILL.md`.

Values seed from
`docs/product/_refs/frankcode-src/planner-executor/engines/utils/planner/scopeSizer.ts`
(default lifecycle/stakeholder axes), extended for QA edge-case generation.
