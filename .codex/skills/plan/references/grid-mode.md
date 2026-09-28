# hs:plan --grid — macro coverage grid (on-demand; first-class when set)

Routed at `grid_unresolved`, the state a `--grid` run lands on when the grid exists but no cell
carries real content. The whole leg is six peer states — `grid_needs_axes` → `needs_fill` →
`needs_build` → `needs_expand` → `needs_emit`, with `grid_unresolved` cutting in whenever the
content is thin. They run after phase decomposition and before red-team. Build a planner macro-grid from the plan's own content, run
the deterministic invariant + confab +
verdict pass, and **resolve the verdict before the plan is ready** — a required coverage pass,
not an optional footnote. Two things it deliberately will NOT do for you: it never auto-edits
the plan and never locally hard-blocks (personal-first: local generates, the remote
receipts-gate enforces). **Whether `--grid` should have been declared at all is a separate,
earlier question — `references/grid-when.md` owns it.** "First-class, not advisory" means the planner MUST act on the verdict
(fill the thin cells or justify them); it does NOT mean the grid rewrites the plan or fails the
build on its own. The engine is the tầng-1 package `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/grid/` driven through
`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/grid_engine.py`, independent of the tầng-2 `orchestrator/grid`.

## Axis inputs come FROM the plan (never hand-typed)

- `§features` → the `feature` axis; `§risks` → the `risk_class` axis. The planner axes are
  `feature × layer × lifecycle × risk_class × stakeholder`.
- `build_planner_axes` RAISES if `features` is empty — axis values must come from the plan,
  not be invented. **Empty features = the grid cannot run; do NOT fabricate axis values to
  force it.** If the plan has no feature list, skip the grid and say so.
- **DensityTier** is the intake-sophistication density_tier `LOW | MID | HIGH` (coverage floors
  0.60 / 0.85 / 0.95, from the density_tier-density SSOT). Pick it from the plan's own intake density_tier.

## Flow (mirrors the CLI)

1. `grid_engine.py build --agent planner --plan-id <plan> --density-tier <LOW|MID|HIGH> --feature ...`
   → an all-SKELETON macro-grid. The expander seam is injectable and defaults to None →
   deterministic STUB, so the macro-grid builds and reviews **without any model**.
2. `grid_engine.py review --grid <grid.json>` → a `GridReviewVerdict`.
3. **Mandatory when grid mode:** after review, run `grid_engine.py emit --grid <grid.json>` →
   writes the `coverage-grid` artifact into `plans/<active>/artifacts/` for downstream
   consumers (test / code-review / critique) — not optional once grid mode is on. Extend with
   `--axes-src <grid-axis-src.json>` (stamps `axis_selection`) + `--checklist
   <feature-risk-checklist.json>` (records `diff_attest`, see Two-pass macro below). This is a
   **hard PRESENCE gate**, parity with `plan-graph.yaml`: when the plan stamps `grid: true`,
   `plan_approval.py` REFUSES APPROVED until the `coverage-grid` artifact exists, and `cook`
   re-checks it at its Phase-DAG preflight via `grid_emit_guard.py --plan <plan-dir> --require`
   (exit 2 → STOP). **Presence AND provenance:** `emit` stamps a `grid_engine` provenance mark
   (`emitted_by` + a content digest); both gates REJECT a coverage-grid lacking a valid mark — a
   hand-written / non-engine artifact does NOT clear it. **No hand-built shortcut** — run the
   engine (`build → review → emit`), whose invariant/confab/verdict pass IS the point. The
   VERDICT stays advisory (`reject` never blocks). Outside grid mode the artifact stays absent,
   every consumer reads it advisory, absent → silent.

## Filler flow — REQUIRED once --grid is on (gate-1 before gate-2)

The fill itself is NOT optional once `--grid` is declared — the presence+fill-ran gate
above rejects an all-degradation (never-filled) grid at both `plan_approval` and cook
preflight. What IS a free choice is the MECHANISM: the `@grid-filler` relay below (the
default), a `preregister` N/A-credit ruleset for combination-banned cells, or a direct
per-cell `[JUSTIFIED-THIN]` attestation. Pick any, but the emitted grid must show the fill
ran — writing the justification only into chat/the approval rationale no longer counts.

When a `@grid-filler` subagent has read the skeleton and written
`grid-fill-src.json`, run gate-1 BEFORE the replay expand step:
`grid_fill_replay.py --validate --grid <grid.json> --src
<grid-fill-src.json>`. It loud-fails (non-zero exit, reason on stderr) on a
structurally BROKEN file — malformed JSON, a top level that is not a JSON
array, or the file missing — and otherwise exits 0 with a one-line
`entries=/matched=/orphan=/unfilled=/will_degrade=` coverage summary.
Two-gate design, deliberate defense-in-depth: gate-1 here checks the
file's STRUCTURE before anything is relayed; gate-2 is the anti-confab
validation inside `grid/expander.py`'s `expand_cell`, applied to each
relayed cell's RAW content. Only after gate-1 passes does `grid_engine.py
expand --invoker grid_fill_replay:invoke` run gate-2.

**Point the invoker at the fill file — `HARNESS_GRID_FILL_SRC`.** `expand` takes no
`--src`; the replay invoker resolves the fill file itself, and the env var wins outright
over its fallback (the ACTIVE plan's own `artifacts/grid-fill-src.json`, resolved through
`resolve_active_plan`). At plan Step 6 the plan is still `pending`, so that fallback has no
active plan to resolve against — set the env var explicitly:

```
HARNESS_GRID_FILL_SRC=<abs>/artifacts/grid-fill-src.json \
  grid_engine.py expand --grid <grid.json> --invoker grid_fill_replay:invoke --root . --out <path>
```

Get this wrong and nothing shouts: an unresolved source relays no cells, every cell degrades
to a STUB, and the run looks like an honest all-STUB grid. That silent collapse is the whole
reason gate-1 exists — so run `--validate` first and read its `matched=/will_degrade=` counts
rather than trusting a zero exit code.

## Verdict semantics — resolve before the plan is ready

- `reject` — a critical finding, a blocking-invariant fail, or a blocking finding → "the
  plan's coverage is badly thin".
- `needs-detail` — only advisory findings → "some cells are still thin".
- `pass` — clean.

Resolve the verdict before moving to Red-team: for every `reject`/`needs-detail` cell, add the
missing coverage to the plan or attest it `[JUSTIFIED-THIN]` (the machine form is an attested
STUB with a reason — a resolved cell, NOT an empty SKELETON one). Two tiers of enforcement:

- **Presence + fill-ran (hard, deterministic):** once `grid: true`, the `coverage-grid` artifact
  must EXIST **and** must not be a never-filled grid. `plan_approval` refuses APPROVED and cook's
  Phase-DAG preflight (`grid_emit_guard.py --require`) exits 2 in TWO cases: the artifact is
  MISSING, **or** it is present but EVERY cell is the no-invoker degradation STUB (the fill loop
  never ran with a model → coverage 0.0). Using `--grid` is opt-in — but once declared, the grid
  must run FULL: an all-degradation emit is not a completed grid, and hand-waving `[JUSTIFIED-THIN]`
  in chat instead of writing it into the artifact no longer passes. Fail-closed. A thin grid whose
  STUB cells carry real `[JUSTIFIED-THIN]` / `N/A` reasons is a RESOLVED grid and passes (the guard
  reads the cell attestations, not the verdict). It still does NOT judge content quality or catch a
  partially-thin FILLED grid — that stays the advisory verdict + the below-floor HITL below.
- **Below-threshold (HITL confirm):** if `coverage_ratio < density_tier coverage_floor` (cells still
  SKELETON) or verdict `reject` (confabulated cells — see signals below), do NOT pass silently
  and do NOT blind-block: surface WHICH cells are thin/hollow + the failing signals, then
  **AskUserQuestion — proceed only on an explicit human confirm**, else resolve first. Same
  tier: a checklist feature DROPPED unjustified — add it back or justify. NOT a new block: the
  drop is already recorded in the digest-covered `diff_attest` (below) either way.

The grid still never auto-edits the plan (the planner/human do the resolving) and never judges
content quality to hard-block — the below-threshold call is the human's, made with eyes open.

## Two-pass macro + ruleset pre-registration

Checklist independence (`hs:discover` pass-1 → `emit --checklist` diff-attest) and the
freeze-before-fill ruleset contract (`preregister` produce/consume, and the `rule:<id>`
attestation prefix an N/A cell needs to earn coverage) live in
`references/grid-preregistration.md`. Load it before freezing rules or writing an N/A
attestation — a prose justification earns zero credit.

**Auto-freeze is ON by default** (`plan.grid.autoPreregister`): Step 6 authors the rules-in file from the plan's own architecture, never from which cells came out thin. Contract + the Goodhart limit: `references/grid-preregistration.md`.

## Guardrail breach — the 4-door decision (engine/skill split)

`build` (the macro-grid at plan Step 6) is non-prompting: it ALWAYS counts the skeleton's exact row cost via `costing.build_receipt` (never only when over)
and embeds the receipt (shape/strength/count/guardrail_rows/`over`/cost-table) into its output — the "prints cost-table / writes receipt" contract holds on
every run, in-guardrail or not. It NEVER calls AskUserQuestion and NEVER auto-degrades strength or drops rows to fit. An over-guardrail `build` REFUSES
(non-zero exit, the receipt only — no grid emitted) unless `--allow-oversize` is passed, in which case it proceeds and still reports `over: true` (honest,
never hidden). `--auto`'s fill loop only ever runs after this guardrail check passes.

Only the SKILL prompts. On an interactive over-guardrail breach, echo the cost-table to chat FIRST (via grid-decisions render), then AskUserQuestion with four doors:
(a) split the plan/phase   (b) run and pay (accept the fill cost)
(c) raise guardrail_rows durably (grid-strength.yaml)   (d) lower strength this round.
The machine chooses NONE of these — the user is supreme. `--allow-oversize` pre-answers (b) on any path (still prints the table + records the receipt). Record the chosen door
via append_grid_decision (never silent).

**`append_grid_decision` keys on a CLOSED vocab in a field named `event`** (not `kind`/`type`);
out-of-vocab raises and writes nothing. The eight (`decisions.py::EVENT_VOCAB`): `axis-selection`
· `cost-table` · `user-answer` · `allow-oversize` · `escalate` · `auto-escalate` ·
`below-floor-hitl` · `keyword-lint`. Free wording goes in `summary`.

## Escalate — climb the strength ladder (t→t+1, seeded)

Three fill-path flags climb ONE rung on an already-filled grid, reusing every old row and
its filled content: `--escalate`, `--auto-escalate`, `--allow-oversize`. Read
`grid_engine.py expand --help` for what each one does and refuses — it states the exact
climb, refusal, and guardrail conditions, and it cannot drift from the code the way a
copy here would. What the help text does NOT tell you is when a climb is the wrong move:

Escalate vs amendment (the honesty rule): escalate changes only DIFFICULTY (strength
up; axes + frozen rules unchanged) → old row-identity stays valid → SEED (keep the done
fill). Changing an axis / value / rule is an AMENDMENT, not an escalate → old rows may
be invalid in the new universe → FRESH-REGEN the whole grid (no seed) + re-approve. One
line: amendment changes the QUESTION → redo; escalate changes the DIFFICULTY → keep the
done work. Engine counts + emits; only the SKILL prompts (user-supremacy).

## Evidence to read when verdict ≠ pass

- `attestation.invariants_failed[]` — which structural check failed.
- `attestation.confab_signals[]` — which cells look plausible-but-hollow.
- `coverage_ratio` vs the density_tier `coverage_floor` — how far under coverage the grid is.

Use these to see which axis/cell is thin and add depth to the plan there. The `--auto`
fill mode (opt-in, default OFF, iteration-capped) is documented in the CLI help; a bare
`--grid` never implies `--auto`.

## Axis-selection + revalidate + grid-decisions echo

Axis-selection is a TWO-ENDED contract once `--grid` is declared — propose+check before
the build, re-select after it.

Before build (REQUIRED, not optional): spawn @grid-axis-selector (subagent_type
"hs:grid-axis-selector") — it reads plan/phase prose and PROPOSES the axis subset + per-value
reasons, replacing the canned layer/lifecycle/stakeholder defaults with values that fit THIS
project (a stdlib terminal CLI has no ui/api/infra layer; use cli/validate/core/store or drop
the layer axis). It writes ONE grid-axis-src.json = {axes:[subset], reasons:{axis|value: why}}.
It is an AGENT spawn, not a skill route. Do NOT build straight from the canned defaults — that
ships a grid whose axis values don't exist in the project and lands mostly-N/A (coverage near
zero, a useless signal). `build` consumes the axis subset via --axes-json; `review` consumes
the reasons-dict via --axes-src (provenance flows into the verdict + grid-decisions). "REQUIRED"
is now GATED, not bare: once `grid: true`, `plan_approval.write_approval` + `grid_emit_guard.py
--require` REFUSE approval/proceed without a valid `axis_selection` receipt covering the feature
axis — stamp via `emit --axes-src <grid-axis-src.json>`.

**HONEST LIMIT (never write "gated" bare):** the gate forces the receipt to EXIST, be
integrity-bound (digest, per `grid/provenance.py`), and match the feature axis — it does NOT
force real reasoning. A hand-written, feature-matching receipt still clears it (may be
confabulated). Blocked: lazy skip, post-emit hand-edit, wrong-axis receipt. NOT blocked:
confabulated reasons.

After build (safety net): when the built grid comes back with an N/A wall (na_ratio past the
SSOT `na_ratio_refit`) and NO axis-selection receipt was threaded in, `review` emits an advisory
AXIS_FITNESS finding that names @grid-axis-selector — re-run the selector to prune/replace the
axes, then rebuild. The two ends compose: proposed+checked before, forced to re-select after.

Revalidate (after fill): `review --revalidate` re-derives HIGH cells through the
gemini/partner relay lane — a SEPARATE, post-fill pass, never part of the selector.
Skip gracefully when the lane is absent.

Grid-decisions echo: before ANY AskUserQuestion (the 4-door guardrail breach, the
below-floor HITL), echo the record to chat via render_decision, then append it with
append_grid_decision (append-only, never a gate input). No silent decisions.
