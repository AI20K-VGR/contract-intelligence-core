# Hydration workflow — on-demand

Tasks (session-scoped) vanish at session end; plan files are the persistent layer — hydration connects both across sessions.

## Flow

```
┌──────────────────┐  Hydrate   ┌───────────────────┐
│ Plan files       │ ─────────► │ Claude Tasks      │
│ (persistent)     │            │ (session-scoped)  │
│ [ ] Phase 1      │            │ ◼ pending         │
│ [ ] Phase 2      │            │ ◼ pending         │
└──────────────────┘            └───────────────────┘
                                        │ Work
                                        ▼
┌──────────────────┐  Sync-back ┌───────────────────┐
│ Plan files       │ ◄───────── │ Task Updates      │
│ (updated)        │            │ (completed)       │
│ [x] Phase 1      │            │ ✓ completed       │
│ [ ] Phase 2      │            │ ◼ in_progress     │
└──────────────────┘            └───────────────────┘
```

## Tool availability

`TaskCreate / TaskUpdate / TaskGet / TaskList` — CLI only; disabled in the VSCode extension. If a tool errors, fall back to `TodoWrite` for progress tracking. Plan files stay source of truth; sync-back updates checkboxes regardless of Task-tool availability.

## Session start: Hydration

1. Read `plan.md` + phase files: `phase-XX-*.md` at the plan-dir root (flat layout) AND `phases/phase-*.md` (current scaffold layout). Read both — a phases/-layout plan keeps every phase in the subdir.
2. Identify remaining `[ ]` items — work not yet done.
3. `TaskCreate` each item with metadata:
   `{ phase, priority, effort, planDir, phaseFile }` — or use `TodoWrite` if Task tools are unavailable.
4. Use `addBlockedBy` to set up dependency chains between phases (skip if using `TodoWrite` fallback).
5. `[x]` items = already done; skip them.

**Pre-check**: `TaskList()` — if tasks already exist (same session), do not recreate them.

## While working

- `TaskUpdate(status: "in_progress")` when picking up a task.
- `TaskUpdate(status: "completed")` immediately after finishing.
- Parallel agents coordinate through the shared task list.
- Blocked tasks unblock automatically when their dependency completes.

## Session end: Sync-back

1. Collect completed tasks along with their metadata (`phase`, `phaseFile`, `planDir`).
2. Scan ALL phase files in the target plan dir — both `phase-XX-*.md` at the root AND `phases/phase-*.md` under the subdir.
3. Reconcile and backfill: update `[ ]` to `[x]` in every phase file (including older phases that have become stale).
4. Update YAML frontmatter `plan.md`: `status` field.
5. Update progress % in `plan.md` overview from actual checkbox counts.
6. Report unresolved mappings if a task cannot be mapped to any phase file.
7. Git commit to finalize the state transition for the next session.

## Cross-session resume

When the user runs `/hs:cook path/to/plan.md` in a new session:
1. `TaskList()` — empty (tasks were lost with the old session).
2. Read plan files — re-hydrate from remaining `[ ]` items.
3. `[x]` = done — create tasks only for unfinished work.
4. Dependency chain rebuilds automatically.

## YAML frontmatter to sync

See SKILL.md's "Plan YAML Frontmatter" section for the canonical example — update the `status` field during sync-back when the plan state changes.
