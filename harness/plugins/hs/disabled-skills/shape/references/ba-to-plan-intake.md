# BA → hs:plan intake — the closed-loop handoff

`hs:shape` decomposes an approved story into dev-task sidecar records
(`references/task-model.md`), but a task list sitting in `docs/product/shape/tasks/` is
not yet work someone can execute — a human still has to drive it into `hs:plan`.
`loop_handoff.py` renders that seam as one artifact: a **plan-intake brief**, markdown,
not a machine plan graph.

## What the brief is, and what it deliberately is not

The brief is a human-readable list — one section per BA task (id, title, `serves`,
`depends_on`, `acceptance`) — that a human reads and then drives `hs:plan`'s own intake
with. It is **not** a `plan-graph.yaml`: this skill does not reinvent `hs:plan`'s
phase-planning machinery, and it never authors the file only `hs:plan` is allowed to
produce. `harness/tests/test_shape_poc_gate_loop.py`'s
`test_write_brief_output_is_markdown_never_plan_graph_yaml` asserts the written file has
a `.md` suffix and that no `plan-graph.yaml` ever appears anywhere under the BA sidecar —
a hard guard on that boundary, not just documentation.

## Carrying the POC id closes the loop

When the brief's work exists because a technical POC just gated closed
(`poc_gate.gate()`, see `poc-gate-loop.md`), `write_brief`/`write_brief_from_dir` accept
that POC's id and stamp it into the brief's frontmatter as `poc: POC-<n>`. This is the
second half of the two-way link between a POC and the plan that verifies it:

- `POC-<n>.md`'s `plan_id` field points **forward**, from the POC to the plan that
  verified it (written by `poc_gate.gate(..., plan_id=...)` once that plan exists).
- the plan-intake brief's `poc:` field points **backward**, from a fresh task list to the
  POC whose closure is what unblocked it — so whoever reads the brief next can trace
  straight back to the review/verification pair that already closed it, instead of
  re-litigating feasibility that is already settled.

A brief authored with no POC in play simply omits the `poc:` key — carrying a POC id is
optional, not a hard requirement on every brief.

## Storage and containment

`docs/product/shape/plan-intake-<ts>.md`, one file per handoff (timestamped, since a
workspace may hand off several times as tasks accumulate). Every write resolves through
`shape_paths.shape_path()` — the same containment invariant every other hs:shape script
uses; a brief can never land outside the BA sidecar.

## CLI

```
python3 loop_handoff.py --root <ws> --poc POC-1
```

Reads every task currently committed to `docs/product/shape/tasks/`
(`task_model.list_tasks()`) and writes one brief. `--poc` is optional. Raises a clear
`error: no tasks to hand off ...` (exit 1) rather than writing an empty brief when the
task sidecar has nothing in it yet.
