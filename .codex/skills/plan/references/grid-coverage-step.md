# hs:plan — grid coverage detail (`--grid`)

Routed at the three deterministic grid states — `grid_needs_build`, `grid_needs_expand`,
`grid_needs_emit` — which run between the design step and red-team. This file carries the
mechanics of these three rungs.

## Build → resolve → emit

Build the planner macro coverage-grid from the plan's own `§features`/`§risks`, run the
deterministic invariant + confab + verdict pass, and **resolve every thin/absent cell before
Red-team** — add the missing coverage to the plan or attest it `[JUSTIFIED-THIN]`. Then `emit`
the `coverage-grid` artifact into `artifacts/` (machine-readable sibling of `plan-graph.yaml`).
`emit` runs at this step while the plan is still `pending` — that is expected, not an error:
`--plan <plan.md>` (this plan) resolves directly, no `in_progress` requirement (see grid-mode.md
Consume). `preregister`/freezing a ruleset also belongs BEFORE approval — freeze first, fill
second, never mint a rule during fill.

**Actively look for a frozen checklist.** Before running `emit`, check whether
`artifacts/feature-risk-checklist.json` exists (written by an earlier `hs:discover` pass 1). When
it does, pass `--checklist artifacts/feature-risk-checklist.json` to `emit` so the drop-detection
diff (`diff_attest`) actually runs. When it does not, `emit` still succeeds (exit 0) but prints a
stderr warning that the drop-detection pass is inert for this grid — read it, do not silence it.

## Gate detail

`plan_approval` refuses APPROVED without the artifact, or a hand-built coverage-grid (parity
`plan-graph.yaml`; never auto-edits the plan). If `coverage_ratio < density_tier floor` or verdict
`reject`, do NOT pass silently — surface the thin cells + confab signals and **AskUserQuestion;
proceed only on explicit confirm**, else resolve first. Full mechanics (axis inputs, verdict
semantics, filler flow, guardrail doors): `references/grid-mode.md`.

## Two-pass independence + axis-selector timing

**Two-pass, independent**: pass-1 spawns `@independent-revalidator` sealed-room (never reads
`§features`), freezes via `feature_checklist.py`; pass-2 diff-attests — a drop rides below-floor
HITL, no new block. Also `@grid-axis-selector` pre-build (gated), `--revalidate` post-fill, echo
via render_decision.
