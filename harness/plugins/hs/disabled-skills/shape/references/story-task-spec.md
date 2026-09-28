# Story → task decomposition flow (BA)

How `hs:shape --task` turns an approved PO story into one or more dev-task sidecar records,
and how that BA output later feeds `hs:plan`'s intake.

## Flow

1. **Read the PO story graph.** `hs:shape` reads (never writes) `hs:spec`'s
   `spec_graph.build_graph(root)` output — the same traceability graph hs:spec builds from
   `docs/product/{vision,brd,prds,epics,stories}`. This is how a BA sees which story ids exist
   to `serves` against.
2. **Decide the decomposition.** The BA (human-in-the-loop) looks at one story — or a small
   related cluster — and decides how many tasks it needs, and whether any task also covers
   other stories (the n-1 shape: e.g. a shared auth-session migration several login/signup/reset
   stories all depend on).
3. **Author each task.** `task_model.author(root, serves=[...], title=..., estimate=...,
   depends_on=[...], acceptance=[...])` allocates the next `TASK-<n>` and writes it under
   `docs/product/shape/tasks/TASK-<n>.md` via `shape_path()` (write containment — never touches
   `docs/product/stories/`).
4. **Resolve + flag.** `serves_resolver.resolve_serves(root, tasks)` (or
   `resolve_serves_from_dir(root)` to pick up everything already on disk) builds the
   story<->task map and flags any `serves` id that does not resolve to a real story node —
   dangling, not rejected, so recording intent ahead of the story landing is allowed.
5. **Hand off to Dev.** The resulting task list (with its `serves` map) is BA→Dev plan intake —
   `hs:plan` consumes it the same way it consumes any other pre-decomposed work list; `hs:shape`
   does not reinvent phase planning — it produces the task list `hs:plan` consumes, not a second
   decomposition engine. Once a plan is approved,
   `hs:cook` → `hs:test` → `hs:code-review` close the Dev/Test half of the loop — that half is
   already closed by the harness's existing gates; this flow only closes the PO→BA→Dev seam.

## Epic/prd selector fan-out (`--task` with a container id)

`--task` accepts an epic or prd id, not only a story id. The container is a **selector**: it
picks which descendant stories get a task. It is NOT a serve target — every authored task's
`serves` still names a STORY id. The task model (1-1/1-n/n-1 over `serves:[story_ids]`) is
unchanged; the selector only decides which stories feed into it.

The kind comes from the graph node's `type` (`spec_graph`), never guessed from the id shape:

1. **Story target → old path.** Author the story directly (`task_model.author`), no scope
   filter, no `from_draft` mark. Nothing below changes for a single-story `--task`.
2. **Epic/prd target → scope-preflight (read-only).** `descendant_resolver.resolve_descendant_
   stories(root, target_id)` returns `{target_kind, stories:[{id,status,has_task}],
   empty_branch}`. Only `type == "story"` nodes count as descendants — a non-story node
   hand-edited to carry `epic: <target>` never leaks in, so `serves` can never point at a
   non-story. `empty_branch` is defined by the STORY count: a prd with child epics but zero
   stories is still empty.
3. **Empty branch → HARD STOP + route.** No descendant story means there is nothing to serve.
   Do NOT author, do NOT touch the PO tree. Route the user to `hs:spec --story <id>`: `hs:shape`
   is read-only on the PO graph and cannot create a story.
4. **Otherwise → interview, then author.** Ask how far to go (AskUserQuestion, kept in the MAIN
   session — a subagent has no TTY): approved-only, include-draft, or cancel.
   `task_selector.author_tasks_for_selector(root, target_id, include_draft)` then authors one
   task per chosen story. A task authored off a not-yet-approved story is marked
   `from_draft: true` — a warning marker only, the `serves` field is unchanged. Approved-only
   mode reports the draft stories it skipped; cancel authors nothing.

This fan-out only chooses stories and authors tasks; it never mutates a PO artifact, never
resolves `serves` against the graph at author time (that stays `serves_resolver`'s job), and
never invents a second planning engine — the resulting task list is the same BA→Dev intake
`hs:plan` reads.

## What this flow deliberately does NOT do

- It never mutates a PO story file — `docs/product/stories/` is read-only from `hs:shape`'s
  side, enforced by `shape_path()`, not just by convention.
- It never assigns story points or hours to the PO story itself — a BA `estimate` lives only in
  the sidecar task record, respecting `hs:spec`'s deliberate "no story points in the story"
  boundary (`guardrails-and-boundaries.md`).
- It never invents a second decomposition/planning engine — the task list is the seam
  `hs:plan` intake reads; the phase-graph machinery stays `hs:plan`'s job.

## Independence from `strict_gate.py`

`hs:spec`'s `strict_gate.py` can read shape task frontmatter as DATA (e.g. to flag an orphaned
`serves` at PO validate time), but it does not import `serves_resolver.py` or `task_model.py` —
that would couple the PO validate gate's code to the BA layer's implementation, which the
PO/BA layering forbids. If `strict_gate.py` needs the same dangling-detection logic, it
re-reads the task files and the graph itself rather than calling into this skill's scripts.
