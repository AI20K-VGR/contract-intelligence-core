# hs:plan --grid — when the flag earns its cost (read BEFORE declaring it)

Split out of `grid-mode.md` (which owns build/verdict/emit) because adoption is its own
decision: `grid-mode.md` answers *how the grid runs*, this file answers *whether it should*.
Read it before typing `--grid`, not after the first thin verdict.

Two dogfood failures are why this file exists. A `--grid` plan emitted an all-STUB grid
(coverage 0.0, the fill loop never ran) and still cleared a presence-only gate. Another built
straight from the canned axes into a project without those layers and landed ~97% N/A — a
coverage number with no signal in it. Both were flag-on-the-wrong-plan, not engine bugs.

## The four preconditions — ALL must hold

1. **The plan carries a real `§features` list, ≥3 independent features.** Not a preference:
   `build_planner_axes` RAISES on an empty feature set (`grid/axes.py`) because axis values
   must come from the plan. One feature dressed up as three to satisfy the engine is
   fabrication, and it buys a grid whose feature axis carries no information.
2. **The project genuinely has the axes being crossed.** The canned values are
   `layer[ui,api,data,infra] × lifecycle[5] × risk_class[4] × stakeholder[4]`. A stdlib
   terminal CLI has no `ui`/`api`/`infra` and no `ops`/`support` stakeholder, so most cells
   are N/A by construction. Prune with `@grid-axis-selector` first (required and gated
   anyway); if pruning leaves two axes, what remains is a checklist, not a grid — write the
   checklist and skip the flag. The post-build safety net (`na_ratio_refit`, 0.66 in
   `grid-strength.yaml`) catches this AFTER you have paid for the build.
3. **The risk is combinatorial.** The grid finds a missing *intersection*: a feature with no
   `ship`/`measure` cell, a risk class no stakeholder owns. It is the right instrument when
   failures come from interaction between concerns. For a linear, one-path change, red-team
   plus the testability triad catch the same gaps for a fraction of the cost.
4. **Somebody will resolve the thin cells.** The grid never auto-edits the plan and its
   verdict is advisory at every downstream consumer — `hs:test` may not let it flip
   `verification.yaml`, `hs:code-review` may not let it force BLOCKED. Its entire value is
   forcing the planner to look at an empty cell. Nobody looking → it is a receipt generator.

## The cost floor is FLAT — this is the counter-intuitive part

Exact t2 row counts over the canned shape, from `costing.count_rows` (deterministic, 0-token,
known before any fill):

| features | cells (t2) | full Cartesian |
|---|---|---|
| 1 | 24 | 320 |
| 3 | 24 | 960 |
| 8 | 42 | 2560 |

A one-feature plan costs the SAME as a three-feature plan. Cost is driven by the four
non-feature axes (`4×5×4×4 = 320` combinations), so the floor sits near 24 cells no matter
how small the plan is. `--grid` is therefore proportionally **worst** on small plans and only
amortizes on wide ones. Budget the fill against the density_tier `per_cell_token_cap`
(400 / 1200 / 2000 for LOW / MID / HIGH) plus the `@grid-axis-selector` and `@grid-filler`
spawns — not against the row count alone. `guardrail_rows` (200) bounds the build, not the
question of whether the build was worth doing.

## Declaring it is a commitment, not an experiment

Once `grid: true` is stamped, the flag gates the author's own work:

- `plan_approval` refuses APPROVED without the `coverage-grid` artifact, and refuses one that
  is present but never filled (every cell the no-invoker degradation STUB).
- `grid_emit_guard --require` exits 2 at cook's Phase-DAG preflight on the same two states,
  and also on a missing/invalid `axis_selection` receipt.
- Under a `--grid` cook, `--require-phase-grids` refuses plan-close until EVERY phase in
  `plan-graph.yaml`'s `subtasks:` has its own micro-grid artifact.

Nothing downstream gets stronger in exchange — the verdict stays advisory everywhere. So the
trade is real work up front against gap-finding, never against enforcement.

**The way back out is explicit `grid: false`** in plan.md frontmatter: it wins over grid files
left on disk from an earlier round, so a declaration you no longer want cannot trap the plan.
An absent key is NOT the same thing — it infers activation from engine-written evidence.

## Do not reach for it to get a number

The honest limits are recorded next to the mechanisms that provide them, and they bound what
the coverage ratio means: the axis-selection gate forces a receipt to exist, be
integrity-bound, and match the feature axis — it does not force real reasoning, and a
hand-written feature-matching receipt still clears it. The frozen ruleset proves WHICH rules
were used and that they sit in the signed plan body; it cannot verify a rule is TRUE. Coverage
credit for an N/A cell turns on a `rule:<id>` prefix match, so the same cells score 0.21 or
1.0 on twelve characters of formatting. A number built on that is a planning aid, never
evidence of coverage.
