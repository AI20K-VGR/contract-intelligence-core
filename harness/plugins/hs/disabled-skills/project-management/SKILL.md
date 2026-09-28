---
name: hs:project-management
injectable: false
description: Track plan progress, update task status, manage tasks, generate reports, coordinate docs updates. Use for project oversight, status checks, task hydration, and session handoffs.
argument-hint: "[status | hydrate | sync | report]"
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, Task, TodoWrite]
metadata:
  compliance-tier: workflow
---

# hs:project-management — project progress management

Track plans, sync tasks, generate progress reports via the `@project-manager` agent (`"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/agents/project-manager.md`). Does not implement code; never merges plans without human confirmation.

**Documentation rule**: when and which docs to update — read `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md` before triggering any doc update.

## When to use

- Check status or completion percentage of an active plan
- Update a plan after completing a feature or phase
- Hydrate / sync tasks from plan files into a new session
- Generate session or multi-plan overview reports
- Coordinate docs updates after a milestone
- Resume work across sessions (cross-session resume)

## Modes / Arguments

| Argument | Behavior |
|---|---|
| `status` | Scan `plans/*/plan.md`, compute completion %, print status table |
| `hydrate` | Read `[ ]` items in phase files and create tasks for this session |
| `sync` | Sync completed tasks back and update `[x]` + YAML frontmatter |
| `report` | Generate report: session / plan-completion / multi-plan |
| (empty) | `AskUserQuestion` to let user choose |

## Workflow

```
[Scan plan files] → [Hydrate tasks] → [Track progress] → [Sync-back] → [Report] → [Trigger doc update]
```

1. **Check current tasks** — `TaskList()` first; if empty, hydrate from `[ ]` items in phase files. `TaskCreate/TaskList/TaskUpdate/TaskGet` tools work only in CLI; VSCode fallback: use `TodoWrite` for tracking.
2. **While working** — `TaskUpdate(status: "in_progress")` when picking up a task; `TaskUpdate(status: "completed")` immediately after finishing.
3. **Sync-back (required at end of session)** — see the Sync-Back Guard section below for the full 5-step procedure (scan all phase files, backfill stale checkboxes, update frontmatter, report unresolved mappings).
4. **Generate report** — load `references/reporting-patterns.md` for exact format.
   Naming: `plans/reports/pm-{date}-{time}-{slug}.md`.
5. **Trigger doc update** — load `references/doc-triggers.md` to identify which docs need changes; delegate to `@docs-manager` agent.

Detail on hydration and task operations: `references/hydration-workflow.md`.

## Sync-Back Guard (required)

NEVER mark only the active phase. When updating plan status:

1. Scan all phase files in the plan dir — `phase-XX-*.md` at root AND `phases/phase-*.md`.
2. Map each `TaskUpdate(status: "completed")` to `phase` + `phaseFile` metadata.
3. Backfill stale checkboxes in older phases BEFORE marking newer phases done.
4. Compute `plan.md` status from actual checkbox counts (do not guess).
5. If a task cannot be mapped, report it as unresolved; do not claim full completion.

## Plan YAML Frontmatter

Every `plan.md` must have:

```yaml
---
title: Feature name
status: in_progress  # pending | approved | in_progress | completed | cancelled (canonical set — plan_status.py)
priority: P1
effort: medium
branch: feature-branch
tags: [auth, api]
created: 2026-01-15
---
```

Update `status` when the plan state changes.

## HARD-GATE (real wiring)

No dedicated gate for this skill, but:
- Task state lives in local files: `plan.md` frontmatter for status, claim files for ownership.

## Boundaries

- DO NOT implement code or edit files outside `plans/`.
- DO NOT mark a plan completed when unresolved tasks or unverified criteria remain.
- DO NOT update docs directly — delegate to `@docs-manager`.
- On exit: return the absolute path of the synced plan and the generated report.
- Task tools (`TaskCreate` etc.) = CLI only; fall back to `TodoWrite` when unavailable.

## Related skills

- `hs:plans-kanban`: read-only board snapshot of the plans this skill mutates.
- `hs:watzup`: end-of-session handoff report (branch/worktree status) — sibling status view.
