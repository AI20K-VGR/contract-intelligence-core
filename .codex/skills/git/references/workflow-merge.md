# Workflow: merge

Delegates to `hs:git-manager` agent.

## Variables

- `TO_BRANCH`: target (default `main`)
- `FROM_BRANCH`: source (default current branch)

## Step 1 — Sync with remote

**Always merge main (or the default branch) into the current branch first.**

```bash
git fetch origin
git checkout {TO_BRANCH}
git pull origin {TO_BRANCH}
```

## Step 2 — Merge from REMOTE

```bash
git merge origin/{FROM_BRANCH} --no-ff -m "merge: {FROM_BRANCH} into {TO_BRANCH}"
```

Use `origin/{FROM_BRANCH}` (not local) — ensures only committed+pushed changes are merged, excluding local WIP.

## Step 3 — Resolve conflicts

If conflicts occur:
1. Resolve manually
2. `git add . && git commit`
3. If clarification is needed -> report to main agent, do not decide unilaterally

## Step 4 — Push

```bash
git push origin {TO_BRANCH}
```

Pre-push hook `harness/install/git-pre-push-hook.sh` activates automatically — do not bypass.

## Pre-merge checklist

- Fetch latest: `git fetch origin`
- Ensure FROM_BRANCH has been pushed to remote
- Check for conflicts first: `git merge --no-commit --no-ff origin/{FROM_BRANCH}` then `git merge --abort`

## Error handling

| Error | Action |
|-------|--------|
| Merge conflicts | Resolve manually, then commit |
| Branch not found | Verify branch name, ensure it has been pushed |
| Push rejected | `git pull --rebase`, retry |
