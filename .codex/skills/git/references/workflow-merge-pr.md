# Workflow — merge an open PR

`merge-pr` merges an already-open Pull Request on the remote, distinct from `merge` (a local branch merge) and `pr` (which *creates* a PR). It wraps `gh pr merge`.

## Preconditions

- `gh` authenticated (`gh auth status`).
- The PR exists and is open. With no number, target the PR for the current branch.
- Required checks are green and required reviews approved — do not force a merge past a failing gate; if checks are red, STOP and report rather than overriding.

## Steps

1. Resolve the PR: `gh pr view [number] --json number,state,mergeable,reviewDecision,statusCheckRollup`.
2. Refuse to proceed when `state != OPEN`, `mergeable == CONFLICTING`, or checks are failing — report the blocker and let the user decide.
3. Merge with the requested strategy (default `--squash`):

   ```bash
   gh pr merge [number] --squash --delete-branch
   ```

   Use `--merge` or `--rebase` only when the user asks; keep `--delete-branch` unless told otherwise.
4. Confirm: `gh pr view [number] --json state,mergedAt` and report the merged SHA.

## Step 5 — Watch target-branch CI

After the merge, capture the base branch and the merge commit, then watch the CI/deploy workflows for that commit on the target branch:

```bash
gh pr view [number] --json baseRefName,mergeCommit
gh run list --branch "$BASE_BRANCH" --commit "$MERGE_SHA" --json databaseId,status,conclusion,name,url
gh run watch "$RUN_ID" --exit-status
```

If no workflow appears immediately, poll briefly before deciding there are no workflows for the merge commit.

## Step 6 — CI-failure convergence

If target-branch CI fails:

1. Inspect the failed run:
   ```bash
   gh run view "$RUN_ID" --json status,conclusion,jobs
   gh run view "$RUN_ID" --job "$JOB_ID" --log
   ```
2. Transient infrastructure failure → rerun failed jobs **once** (do NOT rerun to hide a deterministic failure):
   ```bash
   gh run rerun "$RUN_ID" --failed
   ```
3. Deterministic, repo-fixable failure → activate `/hs:fix --auto` with the exact evidence (workflow, run id, job id, command, error), ship the follow-up through PR review/merge, then re-watch.

Stop only when target-branch CI succeeds, an external blocker remains, or the same blocker survives 3 fix attempts.

## Boundaries

- This is a remote-state operation; it is gated like other ship-class stages (`harness/hooks/gate_stage.py`). Satisfy the gate honestly — never edit gate config to pass.
- No force-merge past failing required checks. Surface the failure; the human decides.
