# Roles and File Ownership

> Load this file when you need detail on responsibility assignment, file boundaries, and git safety within an Agent Team.

## Roles

| Role | subagent_type | Responsibility |
|---|---|---|
| Lead | (originating session) | Create team, assign tasks, spawn teammates, monitor, synthesize, merge, shutdown |
| Researcher | `hs:researcher` | Investigate one angle; save report; notify lead when done |
| Developer | `hs:developer` | Implement in a dedicated worktree; owns the assigned glob patterns |
| Tester | `hs:tester` | Run full suite after dev; owns test files only; reads but does not edit implementation |
| Reviewer | `hs:code-reviewer` | Review one focus area; findings must have evidence; does not edit code |
| Debugger | `hs:debugger` | Verify one hypothesis; actively challenges other hypotheses |

A teammate does exactly the role assigned — no self-escalation (a tester does not spawn a developer to fix code).

## File Ownership (IMPORTANT)

- Each teammate MUST own a distinct set of files — no editing overlap.
- Lead defines ownership via glob patterns in the task description:
  ```
  File ownership: harness/scripts/*, harness/hooks/*
  ```
- Lead resolves conflicts by restructuring tasks or handling the shared file directly.
- Tester: owns only test files; reads implementation but does not edit it.
- Ownership violation detected → STOP immediately, notify lead.

## Git Safety

- Worktree isolation (default with cook): each dev has its own worktree + branch, eliminating conflicts even on shared files.
- No force-push from a teammate session.
- Commit frequently with descriptive messages.
- Pull before push to catch merge conflicts early.
- Inside a worktree: commit/push to the worktree branch, NOT to main/dev.

## Merge Sequence (after cook)

1. Discover branches: check the Agent result or `git worktree list`.
2. For each dev branch: `git merge <dev-branch> --no-ff` (sequentially, not in parallel).
3. Conflict: lead resolves manually → `git add . && git merge --continue`.
4. Clean up: `git worktree remove <path>` for each worktree.
5. Verify: `git log --oneline --graph` to confirm the merge topology.

## Conflict Resolution

- Two teammates need the same file → escalate to lead immediately.
- A plan is rejected twice → lead takes over that task.
- Contradictory findings between reviewers → lead synthesizes and records the disagreement explicitly.
- Blocked by another teammate → message them directly first; escalate to lead if no response.

## --delegate Mode

When the `--delegate` flag is set:
- Lead only: spawns teammates, manages tasks, sends messages, synthesizes reports.
- Lead NEVER: edits files, runs tests, or executes git commands directly.
- With cook: spawn a merge teammate instead of the lead merging directly.
