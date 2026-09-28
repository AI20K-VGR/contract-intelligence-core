# Progress tracking — on-demand

Used in `status` mode or any time completion percentage needs to be computed.

## Plan analysis workflow

1. **Read plan dir**: Glob `plans/*/plan.md` — discover all existing plans.
2. **Parse YAML frontmatter**: extract `status`, `priority`, `effort`, `branch`, `tags`.
3. **Scan phase files**: count `[x]` (done) and `[ ]` (remaining) in each phase file — look in BOTH `phase-XX-*.md` at the plan-dir root and `phases/phase-*.md` under the subdir.
4. **Reconcile**: ensure completed tasks have been mapped and backfilled into phase files — backfill earlier phases BEFORE counting later phases.
5. **Compute %**: `completed / total * 100` for each plan.
6. **Cross-reference**: compare completed tasks with actual implementation.

## Status update protocol

### Direct update (fallback)

If no CLI plan tool is available — edit `plan.md` directly: change only the Status cell in the table; preserve the rest of the structure.

### Plan-level status

Update frontmatter `status` of `plan.md`:

| Condition | Status |
|---|---|
| No phase has started | `pending` |
| At least one phase is running | `in-progress` |
| All phases complete | `completed` |

### Phase-level status

Each phase file (`phase-XX-*.md` at root or `phases/phase-*.md` in the subdir) is tracked with checkboxes:
- `[ ]` = pending
- `[x]` = completed
- Ratio forms the basis for progress %

### Task-level status (CLI only)

Claude Tasks are session-scoped: `pending` → `in_progress` → `completed`

## Verification checklist when marking completed

1. Acceptance criteria in the plan satisfied?
2. Code-review agent report confirming the result?
3. Tests passing — tester agent report?
4. Docs updated to reflect the changes?
5. No regressions — existing functionality intact?

## Status report template

```markdown
## Project status: [Date]

### Active plans
| Plan | Progress | Priority | Status | Branch |
|------|---------|----------|--------|--------|
| [name] | [X]% | P[N] | [status] | [branch] |

### Completed this session
- [x] [description]

### Blockers & risks
- [ ] [description] — [resolution path]

### Next steps
1. [Priority action]
2. [Follow-up]
```

## Metrics to track

- **Phase completion %** — how much of each phase is done
- **Blocker count** — tasks currently blocked
- **Dependency chain health** — circular or stale dependencies
- **Time since last update** — stale plans need attention
