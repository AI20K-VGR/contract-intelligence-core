# Skill Pipelines

Chain skills around GitHub as handoff ledger.

## Intake To Plan

```text
ghpm -> hs:scout -> hs:research -> hs:plan
```

1. `ghpm`: create or update issue with outcome, constraints, labels, project fields.
2. `hs:scout`: locate repo files and risks; comment findings back to issue.
3. `hs:research`: research unstable APIs or external dependencies; attach report link.
4. `hs:plan`: create implementation plan; link plan path in issue.

## Plan To Code

```text
ghpm -> hs:cook -> hs:test -> hs:code-review -> hs:git
```

1. Move issue/project status to In Progress.
2. `hs:cook`: implement scoped work.
3. `hs:test`: run test suite; comment evidence.
4. `hs:code-review`: review changed code; create follow-up issues for non-blocking items.
5. `hs:git cp`: commit/push branch; link commit to issue.

## Bugfix

```text
ghpm -> hs:debug -> hs:fix -> hs:test -> review-pr --fix
```

Use when GitHub issue/CI/PR reports breakage; keep root cause, failing command, fixed verification in issue comments.

## Release

```text
ghpm -> hs:ship beta|official -> review-pr --fix --reply -> ghpm
```

1. Ensure issue has release scope and acceptance criteria.
2. Run ship mode requested by user.
3. Review PR and fix actionable findings.
4. Add final issue comment with PR URL, checks, remaining follow-ups.

## Human Handoff

```text
ghpm -> hs:watzup -> hs:project-management
```

Use when another human or session needs continuation:

- `hs:watzup`: summarize branch/worktree/unfinished work.
- `hs:project-management`: reconcile local plan status if plans exist.
- `ghpm`: write canonical handoff comment and update Project `Next Action`.

## Automation Ideas

- Auto-label new issues with `status:triage`.
- Move issue to Ready when required fields/checklist exist.
- Mark Blocked when label `agent:human-needed` appears.
- Comment on stale In Progress items with last PR/check evidence.
- Generate weekly status issue from project items and CI runs.
- Open follow-up issue when PR review marks deferred work.
