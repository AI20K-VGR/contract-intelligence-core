# Dev-task model — `serves` and the 3 cardinalities

The BA decomposes an approved PO story (from `hs:spec`'s graph) into concrete developer
tasks. The mapping between story and task must support all three shapes without a schema
special-case:

| Mapping | Meaning | How the model expresses it | Example |
|---|---|---|---|
| **1 – 1** | one story → one task | one task, `serves:[S1]` | "Story: user can log out" → "Task: add logout endpoint" |
| **1 – n** | one story → many tasks | many tasks, each `serves:[S1]` | "Story: checkout" → tasks {FE form, BE charge, integration test} |
| **n – 1** | many stories → one task | one task, `serves:[S1,S2,S3]` | Stories {S1 login, S2 signup, S3 reset} all need → "Task: shared auth-session migration" |

`serves` is a plain list field. All three shapes fall out of how it is populated — 1-1 is the
degenerate one-element case, 1-n is many task records pointing at the same story id, n-1 is one
task record listing several ids. There is no `mapping_type` enum, no separate n-1 artifact —
adding one would be a second source of truth for something the list already expresses.

## Task frontmatter

```
{id, serves:[story_ids], title, estimate, depends_on:[task_ids], acceptance, status, actor, ts}
```

| Field | Type | Notes |
|---|---|---|
| `id` | `TASK-<n>` | parent-free, monotonic — max existing `TASK-<n>.md` filename + 1, never reused. A story-scoped id (`TASK-<story>-<n>`) cannot express n-1: one task serving several stories has no single parent to scope under. |
| `serves` | `[id]` | non-empty; story ids from the PO graph. Stored verbatim at author time — resolving against the graph (and flagging a dangling id) is `serves_resolver.py`'s job, not `task_model.py`'s. |
| `title` | string | |
| `estimate` | string | free-form BA effort figure. Never the PO story's own `size:S\|M\|L` field — that boundary stays in the PO layer; a BA estimate lives ONLY in the sidecar. |
| `depends_on` | `[TASK-<n>]` | other tasks this one depends on. |
| `acceptance` | `[string]` | dev-facing acceptance lines (distinct from the PO story's `acceptance_criteria`). |
| `status` | `open \| in_progress \| done` | `open` at author time. |
| `actor` | string | attribution — who authored the record. |
| `ts` | ISO 8601 | write timestamp. |

Schema backing: `schemas/task.schema.json` (draft-07, validated in tests via `jsonschema` —
skipped with `pytest.importorskip` if the library is unavailable).

## Resolving `serves` — `serves_resolver.py`

`serves_resolver.resolve_serves(root, tasks)` walks a list of `{id, serves}` records (the shape
`task_model.author()`/`list_tasks()` return) once and produces:

- `story_to_tasks` — `{story_id: [task_id, ...]}` (covers 1-1 and 1-n)
- `task_to_stories` — `{task_id: [story_id, ...]}` (covers n-1)
- `dangling` — `{task_id: [story_id, ...]}`, the subset of `serves` that did not resolve to a
  story node in the PO graph (`spec_graph.build_graph`)

A dangling id is **flagged, not rejected**: a BA can record task intent before the referenced
story lands, the same tolerant posture the sibling `experiment_spec.py` takes for `linked_to`.
Story resolution reads hs:spec's `spec_graph` under an isolated module load (mirroring
`experiment_spec._load_spec_graph()`) — see the module docstring for why a naive top-level
import is unsafe here.

## Containment

Every write goes through `shape_paths.shape_path(root, rel)`: it resolves
`root/docs/product/shape/<rel>`, asserts the result is still *under* that directory, and raises
`ShapeContainmentError` (a `PermissionError` subclass) on escape — a `..` traversal, an absolute
override, or a symlink pointing outside. `docs/product/stories/` (the PO-owned story tree) sits
outside `docs/product/shape/` by construction, so any attempt to write there fails the same
containment check; there is no separate "stories" special-case to get wrong. This is real guard
code exercised by `harness/tests/test_shape_task_serves.py`, not a byte-unchanged assertion
standing in for enforcement.
