# Workflow: push (cp)

Delegates to `hs:git-manager` agent.

## Tool 1 — Check status

```bash
git status && \
git log origin/$(git rev-parse --abbrev-ref HEAD)..HEAD --oneline 2>/dev/null || echo "NO_UPSTREAM"
```

- Uncommitted changes remaining -> warn, suggest committing first
- `NO_UPSTREAM` -> use `git push -u origin HEAD`

## Tool 2 — Push

```bash
git push origin HEAD
```

Pre-push hook `harness/install/git-pre-push-hook.sh` activates automatically:
- Scrubs `HARNESS_*` env
- Runs `artifact_check.check_stage("push")` — missing artifact -> exit 2, blocked

## Error handling

| Error | Cause | Solution |
|-------|-------|----------|
| `rejected - non-fast-forward` | Remote has newer commits | `git pull --rebase`, resolve, push again |
| `no upstream branch` | Branch not tracked | `git push -u origin HEAD` |
| `Authentication failed` | Wrong credentials | Check `gh auth status` or SSH keys |
| `Repository not found` | Wrong remote URL | Verify `git remote -v` |
| `Permission denied` | No write access | Check repo permissions |
| `pre-push BLOCKED` | Gate missing artifact | Read the message — create `verification.json` as instructed |

## Force push (DANGEROUS)

**Never** force push `main`/`master`/`production`.

Feature branch (only if user has explicitly agreed):
```bash
git push -f origin HEAD
```

## Output format

```
✓ pushed: N commits to origin/{branch}
  - abc123 feat(auth): add login
  - def456 fix(api): resolve timeout
```
