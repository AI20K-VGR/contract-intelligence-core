# Roadmap + effort rollup — milestones, sizing, and the technical-POC precondition

`--roadmap` turns the BA task sidecar into milestones with an effort figure, entirely inside
`docs/product/shape/` — it never mutates a PO story, and it never adds a story-points field to
the PO schema (`references/task-model.md`'s boundary holds here too). Effort estimation
(`scripts/effort_map.py`) and milestone assembly (`scripts/roadmap_rollup.py`) are two
independent modules; the flag wires them together, not a hard import between them beyond the
handful of pure helper functions `roadmap_rollup.py` calls directly.

## Effort sources — one field wins, one field falls back

Two effort sources can reach a rollup:

1. **A BA task's own explicit `estimate`** (`task_model.py`'s `--estimate`), already free-form
   text on the task record (`"2d"`, `"1w"`, ...).
2. **A PO story's `size: S|M|L`**, read-only from the story spec, mapped through a table into a
   day range.

The explicit task estimate always wins: `effort_map.estimate_for_task(task, story_size=...)`
returns the task's own `estimate` unchanged whenever it is non-blank, and only falls back to a
size-derived range when the task carries no estimate of its own. A BA who typed `"2d"` meant two
days, not whatever the linked story's size would map to.

## Size → range table (config, not code)

```yaml
S: "1-2d"
M: "3-5d"
L: "1-2w"
```

`effort_map.default_size_range_table()` parses this from an embedded YAML block — one place, not
an if/elif ladder repeated at call sites. `effort_map.load_size_range_table(path)` loads an
override YAML file instead; a missing or malformed override falls back to the default silently,
the same fail-open posture the sidecar's other readers use for a missing/unreadable artifact. A
week converts to working days via `WORK_DAYS_PER_WEEK = 5` (documented once, here and in an
inline comment above the constant in `effort_map.py`) so a `"1-2w"` figure sums against a `"2d"`
figure without a second unit system.

## Summing an estimate batch

`effort_map.sum_estimates([...])` parses every estimate string into a `(min_days, max_days)`
pair, sums each side independently, and formats back to `"Nd"` (single value) or `"N-Md"`
(range). An unparsable entry in the batch is skipped, not raised on — one bad hand-typed string
narrows the sum, it does not crash the rollup. An empty or all-unparsable batch sums to `"0d"`: a
milestone with no estimated tasks yet is a normal, valid state.

## Milestone shape

```
{id: MS-<n>, title, target_window, contains:[task_ids], excluded:[{task_id, poc_id?, reason}],
 effort_rollup, poc_gated, poc_gate_status: advisory|unsatisfied|satisfied,
 dropped_estimates:[task_ids], unmapped_sizes:[{task_id, size}], depends_on:[MS ids], cycle}
```

`poc_gate_status` is the 3-way resolution of `poc_gated` (advisory when no POC is
attached, unsatisfied/satisfied once one is). `dropped_estimates` lists task ids whose
`estimate` did not parse (excluded from `effort_rollup`); `unmapped_sizes` lists
`{task_id, size}` pairs for tasks that fell back to a story size with no day-range
mapping. The JSON schema (`schemas/roadmap.schema.json`) is the SSOT.

`roadmap_rollup.build_milestone()` reads each `task_id` via `task_model.read_task()`, sums its
`effort_rollup` from the included tasks' `estimate` fields (falling back to a caller-supplied
story size only when a task carries none), and writes the whole batch through
`roadmap_rollup.write_roadmap()` into the single sidecar document `docs/product/shape/roadmap.md`
— unlike the one-file-per-record task/POC/experiment sidecars, the roadmap is one small aggregate
document, rewritten whole on every rollup rather than appended to.

Reading a linked story's `size` (for the estimate fallback only) is left to the caller: this
module accepts an optional `story_sizes: {story_id: size}` mapping instead of importing the PO's
own graph builder directly, the same independent-testability split `serves_resolver.py` draws
around its own read of the PO story graph — `roadmap_rollup.py` stays testable without seeding a
full PO spec tree, and the skill-level flag orchestration is the one place that actually wires
the PO graph read in.

## The technical-POC precondition (one-direction data flow)

A technical proof-of-concept (`scripts/poc_gate.py`) closes independently, entirely through the
harness's own already-closed dev loop — `hs:plan` → `hs:cook` → `hs:test` → `hs:code-review`. A
roadmap rollup treats a closed POC as a **precondition**, never the reverse: this module reads a
POC's `closed` field to decide whether a task may count as committed work; it never reopens,
reorders, or writes back into a POC record. The data only ever flows technical-POC → roadmap,
never roadmap → technical-POC — there is no code path here that mutates `docs/product/shape/poc/`.

Gating is opt-in per task. A caller passes `task_poc_map: {task_id: poc_id}` naming only the
tasks that actually need a technical-feasibility precondition before committing; every other task
in `task_ids` rolls up unconditionally. For a gated task:

- the referenced POC reads back **closed** → the task lands in `contains`, effort counted.
- the referenced POC reads back **open**, or the record is missing/unreadable → the task lands in
  `excluded` (with a `reason`) instead, and is simply picked up by the next rollup once it closes.
  Neither case raises — a milestone with a still-open POC is a normal in-flight state, not an
  error.

`poc_gated` on the resulting milestone is `True` only when at least one gate was declared **and**
every declared one resolved to closed; it is `False` both when nothing was gated at all (nothing
to verify — advisory, not blocking) and when a declared gate is still unsatisfied. A workspace
with no `docs/product/shape/poc/` directory at all (the technical-POC sidecar never used) rolls up
exactly the same way as a milestone with no gates declared: every task included, `poc_gated:
false`, no crash — the precondition mechanism is opt-in, its total absence is not a failure mode.

## `depends_on` — cycle-safe, never hangs

`roadmap_rollup.detect_cycles()` runs an iterative Tarjan SCC pass over each milestone's
`depends_on` list and returns the set of ids participating in a cycle (a direct self-loop counts).
A `depends_on` id that does not resolve to a known milestone is skipped, not raised on.
`write_roadmap()` annotates every milestone with `cycle: true|false` before writing — a cyclic
`depends_on` chain is flagged in the sidecar for a human to resolve, it never blocks the write or
hangs the rollup.

## Containment

Every write resolves through `shape_paths.shape_path(root, "roadmap.md")`: it resolves
`root/docs/product/shape/roadmap.md`, asserts the result stays under the BA sidecar root, and
raises on escape (`..`, an absolute override, a symlink pointing outside) — the same containment
invariant every other hs:shape writer uses. `docs/product/stories/` and the rest of the PO spec
tree sit outside `docs/product/shape/` by construction, so a rollup can never land a byte there.

## View reuse — no second renderer

The existing `roadmap`/`time` graph views (`hs:spec`'s own `--viz` dispatcher) already group
PRDs/epics/stories by horizon and depends-on order from the PO spec graph directly; this sidecar
does not replace or duplicate that rendering path — it adds a richer BA-side document alongside
it. Nothing in `roadmap_rollup.py` imports or reimplements those renderers.

## CLI

```
python3 roadmap_rollup.py --root <ws> --add-milestone --id MS-1 --title "Sign-in" \
    --target-window "2026-Q3" --task-ids TASK-1,TASK-2 --depends-on MS-0 \
    --task-poc-map TASK-1:POC-1

python3 roadmap_rollup.py --root <ws> --list
```

`effort_map.py` exposes the same two levers standalone:

```
python3 effort_map.py --map-size M
python3 effort_map.py --sum 2d,3d,5d
```

Both CLIs exit non-zero with a one-line `error: ...` message on a malformed input — never a raw
Python traceback.
