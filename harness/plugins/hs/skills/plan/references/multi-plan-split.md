# Multi-plan split (scope-sizing gate)

Advisory reference for a single question: does this mission fit in **one** plan, or does
it need to be split into **multiple linked sub-plans** under a manifest? Ask it before
decomposing phases — a split decided after the phases are written costs N rewrites
instead of one.

## What decides it

`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/scope_split.py` ports FrankCode's `scopeSizer.ts` +
`scope-sizing-gate.md` cell-count estimator — a pure function, 0-token, no LLM call:

```
projected_cells = |feature| x |layer| x |lifecycle| x |risk_class| x |stakeholder|
pruned_cells    = projected_cells after density_tier-conditional axis pruning
mode            = 'multi' when pruned_cells > threshold, else 'single'
```

Default axes when not supplied: `layers = [ui, api, data, infra]`,
`lifecycle = [discover, design, build, ship, measure]`,
`risk_classes = [spec-drift, capacity, regression, compliance]`,
`stakeholders = [dev, ops, security, support]`. `features` has no default — at least
one must be supplied (empty `features` raises).

## DensityTier pruning

Same rule as `scope-sizing-gate.md:26-28`, re-implemented inline in `scope_split.py`
(intentionally **not** imported from `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/grid/` — this gate is
grid-independent by design):

| DensityTier | Pruning |
|---|---|
| `LOW` | lifecycle capped at 2, stakeholder capped at 2 |
| `MID` | stakeholder capped at 3 |
| `HIGH` | none |

Pruning only ever lowers a count that is already above its cap — it never raises one.

## Threshold

`CELL_COUNT_THRESHOLD = 60` — the last pruned-cell count where DEEP-density coverage
(40k tokens / 95% coverage floor -> ~700 tokens/cell) stays viable. Override per-run via
the `SCOPE_SIZE_THRESHOLD` env var (`scope-sizing-gate.md:107`); a missing/unset env
falls back to 60.

- `pruned_cells > threshold` -> mode `multi`.
- `pruned_cells <= threshold` -> mode `single`, and `sub_plan_count` is always `1`.

## Split strategy

`recommend_split_strategy(features, layers)` picks by relative dominance
(`scopeSizer.ts:80-90`):

| Strategy | Trigger |
|---|---|
| `feature` | `len(features) > len(layers) * 2` |
| `layer` | `len(layers) > len(features) * 2` |
| `hybrid` | neither — balanced |

`estimate_sub_plan_count(...)` then sizes the split:

- `feature` -> `ceil(len(features) / 3)` (`MAX_FEATURES_PER_SUBPLAN = 3`)
- `layer` -> `ceil(len(layers) / 2)` (`MAX_LAYERS_PER_SUBPLAN = 2`)
- `hybrid` -> searches the feature-chunk x layer-chunk grid for the fewest sub-plans
  whose per-sub-plan cell count (chunk sizes x pruned lifecycle x risk_class x
  stakeholder) still fits under the threshold; falls back to independent
  `ceil(F/3) x ceil(L/2)` chunking when nothing in the grid fits.

## Manifest skeleton

`build_manifest_skeleton(input, result)` emits the 5-part skeleton
(`scope-sizing-gate.md:70-79`) once mode is `multi`:

1. **`subPlans[]`** — `id`, `scope` (`features` + `layers` for that chunk),
   `estimatedCells`.
2. **`dependencies[]`** — `from`/`to` sub-plan ids + `sharedLayers` linking
   consecutive chunks.
3. **`sharedContracts[]`** — placeholder; the planner fills API surfaces / data
   models / event schemas shared across sub-plans.
4. **`masterRisk`** — placeholder; the planner fills pre-mortem risks spanning
   sub-plans.
5. **`intakeInheritance`** — `{density_tier, threshold}` inherited from the parent brief.

The script only produces the **skeleton** shape — it does not author `sharedContracts`
or `masterRisk` content, and it never auto-splits or auto-executes anything. A human
(or the planner persona) reads the sizing result and decides.

## Multi-plan execution rules (advisory, unenforced by the script)

From `scope-sizing-gate.md:60-68` — the script does not enforce these; they are guidance
for whoever acts on a `multi` verdict:

| Rule | Value | Rationale |
|---|---|---|
| Max plans per turn | 1 | Preserves DEEP density; each plan needs full elaboration |
| Max sub-plans per session | 3 | Prevents user fatigue and context decay |
| Remainder handling | Queued as linked tasks | Each task links `blocks`/`blockedBy` to the manifest |
| Manifest density | SKELETON | Cheap to update; changes trigger a selective replan |
| Sub-plan density | Same density_tier as parent | Each sub-plan gets an independent budget |

## CLI

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/scope_split.py --features a,b,c,d,e,f,g,h,i
# -> {"sizing": {...}, "manifest": {...}}   # multi mode: 9 features > 4 layers*2

python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/scope_split.py --features f1 --layers ui --lifecycle discover \
  --risk-classes spec-drift --stakeholders dev
# -> {"sizing": {...}}                      # single mode: no "manifest" key

SCOPE_SIZE_THRESHOLD=10 python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/scope_split.py --features f1,f2,f3 --layers ui \
  --lifecycle discover --risk-classes spec-drift --stakeholders dev
# -> threshold honored from env, not the 60 default
```

`--density-tier` defaults to `HIGH` (no pruning); pass `LOW` or `MID` to exercise pruning.

## Scope of this phase (what it deliberately does NOT do)

- **Does not auto-split a plan.** The script only reports a sizing recommendation +
  skeleton manifest; no plan file is created or divided by this code.
- **Does not depend on `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/grid/`** — density_tier pruning is a small,
  self-contained inline rule, not the grid package's `defaultAxisPruner`. This is a
  deliberate divergence from the FrankCode source (`scopeSizer.ts:14`), kept so this
  gate has zero dependency on grid-package phases landing first.

## Anchors

- `docs/product/_refs/frankcode-src/planner-executor/methodology/planner/scope-sizing-gate.md`
  — decision logic `:20-30`, split strategies `:42-46`, manifest contents `:70-79`,
  multi-plan rules `:60-68`, env override `:107`.
- `docs/product/_refs/frankcode-src/planner-executor/engines/utils/planner/scopeSizer.ts`
  — `CELL_COUNT_THRESHOLD` `:21`, `MAX_FEATURES_PER_SUBPLAN`/`MAX_LAYERS_PER_SUBPLAN`
  `:22-23`, `calculateCellCount` `:69-74`, `recommendSplitStrategy` `:80-90`,
  `estimateSubPlanCount` `:96-146`, `estimateScope` `:151-181`.
