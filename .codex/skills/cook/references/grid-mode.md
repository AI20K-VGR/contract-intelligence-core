# hs:cook --grid — executor micro-grid (on-demand; first-class when set)

Load when `hs:cook` runs with `--grid`. Before implementing a phase, build an executor
micro-grid for that phase as a completeness pass, run the deterministic invariant + confab +
verdict pass, and **resolve every thin corner before red→green so the tests cover it** — a
first-class step that FEEDS TDD, not a footnote. It never auto-edits the phase file and never
hard-blocks cook; the executor does the resolving. Engine: `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/grid_engine.py`
over the tầng-1 `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/grid/` package (independent of tầng-2 `orchestrator/grid`).

## The six executor axes

`step × precondition × side_effect × failure_mode × rollback × verification`. The `step`
axis values come FROM the phase file's `## Implementation Steps` — do not hand-type them. A
micro-grid makes it visible when a phase names a `step` but has no `rollback` or
`verification` cell for it.

## Flow (mirrors the CLI)

1. `grid_engine.py build --agent executor --task-id <phase> --density-tier <LOW|MID|HIGH> ...`
   (executor axes + density_tier → skeleton). The expander seam defaults to None → deterministic
   STUB, so the micro-grid runs **without any model**.
2. `grid_engine.py review --grid <grid.json>` → verdict.
3. **Mandatory when grid mode:** after review, run `grid_engine.py emit --phase <id>` → writes
   the `coverage-grid-<id>.<fmt>` artifact for THIS phase into `plans/<active>/artifacts/`
   (`<id>` matches `plan-graph.yaml`'s own `subtasks:` key for the phase, e.g. the same id
   `verification-<id>.json` already uses). **Never omit `--phase`** for this per-phase emit —
   the bare `emit` (no `--phase`) writes the MACRO plan-level `coverage-grid.<fmt>`, the ONE
   artifact plan approval reads; writing a phase's micro-grid there would silently overwrite it.
   A `--grid` cook run always produces this per-phase artifact — emit is not optional once grid
   mode is on.

   **Two separate gates read two separate paths — do not conflate them.** Cook's Phase-DAG
   preflight (`grid_emit_guard.py --plan <plan-dir> --require`) is the MACRO grid's presence
   gate (unaffected by per-phase emits — it never looks at `coverage-grid-<id>.<fmt>`). The
   **per-phase COUNTING gate** is a separate check, run at cook's **plan-close** step (never at
   plan approval — no per-phase grid can exist yet when a plan is approved, so gating approval
   on them would recreate the exact deadlock a prior fix removed):
   `grid_emit_guard.py --plan <plan-dir> --require-phase-grids` reads the declared phase list
   from `plan-graph.yaml`'s `subtasks:` keys and exit-2s naming every phase with no
   `coverage-grid-<id>.<fmt>` artifact yet. It respects the same `grid: false` opt-out as
   `--require` (both route through `resolve_grid_mode`).

   **Presence AND provenance:** `emit` stamps a `grid_engine` provenance mark; `--require`
   REJECTS a coverage-grid lacking it — a hand-written / non-engine artifact does NOT clear
   the gate. No hand-built shortcut: run the engine (`build → review → emit`), never hand-author
   the YAML. The VERDICT itself stays advisory (a `reject` never blocks). Outside grid mode the
   artifact stays absent, and every consumer (review/test) reads it advisory.

   **The executor micro-grid is exempt from the axis-selection receipt, by STRUCTURE and by
   PATH — never by a self-declared field.** The axis-selection requirement (see
   `plan/references/grid-mode.md`'s Axis-selection section) applies only to a MACRO
   (`coverage-grid.<fmt>`) grid that structurally carries a `feature` axis — the signal a
   planner-family grid actually chose among feature candidates. A per-phase micro-grid never
   needs it, because it is never at the macro path: cook's executor micro-grid never runs
   @grid-axis-selector, so its `emit --phase <id>` does not need `--axes-src`, and
   `--require`/`--require-phase-grids` never demand a receipt for a `coverage-grid-<id>.<fmt>`
   artifact. (The gate does not trust the record's own `agent` field for this decision — a
   relabelled or deleted `agent` cannot spoof either the macro-vs-phase file path or the grid's
   own `axes` shape.)

## Default filler flow (opt-in): gate-1 before gate-2

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

## Pre-implement completeness pass (feeds TDD, first-class)

A `reject` / `needs-detail` verdict names a phase corner you haven't thought through — e.g. a
`step` cell with no matching `rollback` / `verification`. Resolve it: fold the missing
consideration into the phase's test plan so red→green actually covers it. Required once
`--grid` is carried, not an optional read. The grid still does **not** auto-edit the phase file
— the executor does the resolving.

Two tiers, same as plan's macro grid:

- **Presence (hard):** the `coverage-grid` artifact must EXIST once `grid: true` — cook's
  Phase-DAG preflight runs `grid_emit_guard.py --require` (exit 2 → STOP). Catches "declared
  grid but emitted nothing"; does NOT catch a hollow all-SKELETON grid.
- **Below-threshold (HITL confirm):** if `coverage_ratio < density_tier coverage_floor` or verdict
  `reject`, do NOT skip silently and do NOT blind-block the phase — surface the thin cells +
  confab signals and **AskUserQuestion; proceed to red→green only on an explicit confirm**.

## Micro one-pass at cook preflight (freeze + HITL)

The executor micro-grid runs ONE pass, not two: 1 phase = 1 moment, so there is no
earlier moment to diff against — **no diff-attest at micro**, in contrast to the plan
macro-grid's two-pass (discover → plan). It only needs a receipt (universe → subset of
rows actually filled), a freeze of the micro-grid BEFORE fill (same freeze-before-fill
timeline as the macro pass — build → freeze → fill, minting a rule during fill is
fraud), and HITL (`AskUserQuestion`) when the fill lands below floor. Single pass,
single moment, no cross-moment signal to compare — that is the whole contrast with the
plan side's two-pass macro.

**Produce** the sidecar before that freeze with `grid_engine.py preregister --rules-in
<rules-in.yaml> --plan <plan.md>` — same producer the plan macro-grid uses, reused
as-is for the phase's local rules; it freezes the rules-in file, writes the sidecar
(default `<plan-dir>/artifacts/grid-preregistration.json`), and appends the rendered
`## Grid constraint rules (frozen)` section + hash line into plan.md (idempotent — a
re-run replaces the section, never duplicates it). **Consume** at fill/review: invoke
the engine with `--rules artifacts/grid-preregistration.json --root <repo-root>` so a
verified `rule:<id>` N/A attestation credits coverage end-to-end. The sidecar hash is
verified against the **approved active plan** (`resolve_active_plan` — needs an
`in_progress` plan under `<root>/plans`), never an arbitrary `--plan`; a `--plan`
pointer, if passed, MUST resolve to that same plan or the run dies closed, and a forged
`rule:<id>` N/A is a hard reject. Without `--rules`, `frozen_rules` stays None (0 credit,
fail-closed).

**The attestation must literally START `rule:<id>` — prose earns ZERO credit.** An N/A cell
counts toward coverage only when its `attestation` matches `^rule:([A-Za-z0-9_-]+)` and that id
is in the frozen ruleset. A true sentence like `N/A by the docs-x-cli rule` is worth nothing:
it is a prefix match, not a reading. Same cells, `coverage 0.21` (below floor → `reject`) versus
`coverage 1.0`, on a 12-character prefix. Write `rule:docs-x-cli — <why, for the human>`; no
space after the colon (`rule: docs-x-cli` fails like prose).

## Guardrail breach — the 4-door decision (engine/skill split)

The executor micro-grid's `build` step is non-prompting: it ALWAYS counts the skeleton's
exact row cost via `costing.build_receipt` (never only when over) and embeds the receipt
(shape/strength/count/guardrail_rows/`over`/cost-table) into its output — the "prints
cost-table / writes receipt" contract holds on every run, in-guardrail or not. It NEVER
calls AskUserQuestion and NEVER auto-degrades strength or drops rows to fit. An
over-guardrail `build` REFUSES (non-zero exit, the receipt only — no grid emitted) unless
`--allow-oversize` is passed, in which case it proceeds and still reports `over: true`
(honest, never hidden). A later `--escalate` climb during fill is a separate guardrail
compare (`costing.escalation_verdict`, delta-scoped) with the same non-prompting contract.

Only the SKILL prompts. On an interactive over-guardrail breach, echo the cost-table to chat FIRST (via grid-decisions render), then AskUserQuestion with four doors:
(a) split the plan/phase   (b) run and pay (accept the fill cost)
(c) raise guardrail_rows durably (grid-strength.yaml)   (d) lower strength this round.
The machine chooses NONE of these — the user is supreme. `--allow-oversize` pre-answers (b) on any path (still prints the table + records the receipt). Record the chosen door
via append_grid_decision (never silent).

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

## Relationship to TDD (does not replace or weaken it)

The micro-grid runs BEFORE the phase's red→green as a "think broadly enough before you write
the test" step. It does NOT replace a test and does NOT relax the 100%-pass regression gate
(`"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md`). It is a completeness overlay, not a gate.

## Evidence to read when verdict ≠ pass

`attestation.invariants_failed[]` (especially `STUB_REASON_REQUIRED` and
`HIGH_NEEDS_EVIDENCE`) plus `attestation.confab_signals[]` — they name the cell that is thin
or hollow. The `--auto` fill mode is opt-in, default OFF, iteration-capped, and is never
implied by a bare `--grid` and never wired into cook autopilot.

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
the reasons-dict via --axes-src (provenance flows into the verdict + grid-decisions).

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
