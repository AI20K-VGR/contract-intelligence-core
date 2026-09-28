# Workflow: PR (pr)

Delegates to `hs:git-manager` agent.

## Variables

- `TO_BRANCH`: target (default `main`)
- `FROM_BRANCH`: source (default current branch)

## Important: use remote diff

PRs are based on remote branches. Local diff includes uncommitted changes — incorrect.

## Tool 1 — Sync + analyze

**Always merge main (or the default branch) into the current branch first.**

```bash
git fetch origin && \
git push -u origin HEAD 2>/dev/null || true && \
BASE=${BASE_BRANCH:-main} && \
HEAD=$(git rev-parse --abbrev-ref HEAD) && \
echo "=== PR: $HEAD → $BASE ===" && \
echo "=== COMMITS ===" && \
git log origin/$BASE...origin/$HEAD --oneline && \
echo "=== FILES ===" && \
git diff origin/$BASE...origin/$HEAD --stat
```

Branch not yet on remote -> push first, then retry.

## Tool 2 — Compose PR content

- **Title**: conventional commit format, < 72 chars, no version numbers
- **Body**: summary bullets + test plan checklist

## Tool 3 — Create PR

```bash
gh pr create --base $BASE --head $HEAD --title "..." --body "$(cat <<'EOF'
## Summary
- Bullet points

## Test plan
- [ ] Test item
EOF
)"
```

## Do not use (local comparison — incorrect)

```bash
# WRONG
git diff main...HEAD
git diff --cached
git status
```

## Error handling

| Error | Action |
|-------|--------|
| Branch not on remote | `git push -u origin HEAD`, retry |
| Empty diff | Warn: "No changes for PR" |
| Push rejected | `git pull --rebase`, resolve, push |
| No upstream | `git push -u origin HEAD` |
