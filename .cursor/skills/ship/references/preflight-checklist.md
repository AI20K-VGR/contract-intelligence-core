# Preflight Checklist — hs:ship

Run full checklist before the ship pipeline continues. Any FAIL item → STOP, report the reason, do not proceed.

## 1. Branch

```bash
CURRENT=$(git branch --show-current)
```

| Check | Passes when |
|----------|----------|
| Not on target branch | `$CURRENT` ≠ main/master/dev/beta |
| Branch exists at remote | `git ls-remote --exit-code origin $CURRENT` |
| No uncommitted secrets | scan passes (see item 4) |

If currently on the target branch → **ABORT**: "Ship from a feature branch, not the target branch."

## 2. Mode detection

```
Argument "official" → target = main/master (auto-detect)
Argument "beta"     → target = dev/beta (auto-detect)
No argument         → infer from branch name:
  feature/* hotfix/* bugfix/* → official
  dev/* beta/* experiment/*  → beta
  Ambiguous → AskUserQuestion: ["Official (main)", "Beta (dev)"]
```

Auto-detect main branch:
```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
# fallback:
git rev-parse --verify origin/main 2>/dev/null && echo "main" || echo "master"
```

## 3. Diff summary

```bash
git fetch origin <target>
git diff origin/<target>...HEAD --stat
git log origin/<target>..HEAD --oneline
```

Output:
- Commit count
- Total +lines/-lines
- List of changed files

Use this output to compose PR body and infer version bump.

## 4. Secret scan (required)

```bash
git diff HEAD | grep -iE "(AKIA|api[_-]?key|token|password|secret|credential|private[_-]?key|mongodb://|postgres://|-----BEGIN)"
```

Match found → **STOP immediately**. Show file:line. Suggest `.gitignore` / environment variable.

## 5. Dry-run gate

If `--dry-run`: print a summary of all steps that would run → STOP, do not execute.

Example dry-run output:
```
[DRY-RUN] branch: feature/foo → official → target: main
[DRY-RUN] Step 1: fetch + merge origin/main
[DRY-RUN] Step 2: hs:test (runner: pytest)
[DRY-RUN] Step 3: hs:code-review → review-decision.json
[DRY-RUN] Step 4: check artifacts (verification, review-decision, plan-approval)
[DRY-RUN] Step 5: changelog + version bump (if present)
[DRY-RUN] Step 6: commit + push → pre-push hook will run
[DRY-RUN] Step 7: gh pr create
```

## 6. Artifact pre-check (early warning)

Before the heavy pipeline steps (test, review), do a quick artifact check:

```bash
python3 -c "import sys,pathlib; sys.path.insert(0,'harness/scripts'); import artifact_check; d=artifact_check.resolve_active_plan('.'); sys.exit(0 if d and artifact_check._artifact_path(pathlib.Path(d),'plan-approval').is_file() else 1)" || echo "plan-approval: MISSING"
```

Missing artifact → **early warning** (not a block here — gate blocks at push).
Suggestion: `hs:cook` generates `verification.json`, `hs:code-review` generates `review-decision.json`, approve the plan for `plan-approval.json`.
