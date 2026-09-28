# Branch management

## Naming convention

**Format:** `<type>/<descriptive-name>`

| Type | Purpose | Example |
|------|---------|---------|
| `feature/` | New features | `feature/oauth-login` |
| `fix/` | Bug fixes | `fix/db-timeout` |
| `refactor/` | Refactoring | `refactor/api-cleanup` |
| `docs/` | Documentation | `docs/api-reference` |
| `test/` | Tests | `test/integration-suite` |
| `chore/` | Maintenance | `chore/deps-update` |
| `hotfix/` | Production fixes | `hotfix/payment-crash` |

## Branch lifecycle

### Create branch

```bash
git checkout main
git pull origin main
git checkout -b feature/new-feature
```

### During development

```bash
# Commit frequently
git add <files> && git commit -m "feat(scope): description"

# Update from main
git fetch origin
git rebase origin/main
```

### Before merge

```bash
# Push final state
git push origin feature/new-feature

# After rebase on feature branch (requires -f)
git push -f origin feature/new-feature
```

### After merge

```bash
# Delete local
git branch -d feature/new-feature

# Delete remote
git push origin --delete feature/new-feature
```

## Branch strategies

### Simple (small teams)

```
main (production)
  └─ feature/* (development)
```

### Git Flow (with release cycle)

```
main (production)
develop (staging)
  ├─ feature/*
  ├─ bugfix/*
  ├─ hotfix/*
  └─ release/*
```

### Trunk-Based (continuous CI/CD)

```
main (always deployable)
  └─ short-lived feature branches
```

## Quick commands

| Task | Command |
|------|---------|
| List branches | `git branch -a` |
| Current branch | `git rev-parse --abbrev-ref HEAD` |
| Switch branch | `git checkout <branch>` |
| Create + switch | `git checkout -b <branch>` |
| Delete local | `git branch -d <branch>` |
| Delete remote | `git push origin --delete <branch>` |
| Rename | `git branch -m <old> <new>` |
