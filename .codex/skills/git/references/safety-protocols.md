# Safety protocols — secret scan + branch protection

## Secret scan

### Scan command

```bash
git diff --cached | grep -iE "(AKIA|api[_-]?key|token|password|secret|credential|private[_-]?key|mongodb://|postgres://|mysql://|redis://|-----BEGIN)"
```

### Patterns to block

| Type | Pattern | Example |
|------|---------|---------|
| API Keys | `api[_-]?key`, `apiKey` | `API_KEY=abc123` |
| AWS | `AKIA[0-9A-Z]{16}` | `AKIAIOSFODNN7EXAMPLE` |
| Tokens | `token`, `auth_token`, `jwt` | `AUTH_TOKEN=xyz` |
| Passwords | `password`, `passwd`, `pwd` | `DB_PASSWORD=secret` |
| Private Keys | `-----BEGIN PRIVATE KEY-----` | PEM files |
| DB URLs | `mongodb://`, `postgres://`, `mysql://` | Connection strings |
| OAuth | `client_secret`, `oauth_token` | `CLIENT_SECRET=abc` |

### Files to warn about

- `.env`, `.env.*` (except `.env.example`)
- `*.key`, `*.pem`, `*.p12`
- `credentials.json`, `secrets.json`
- `config/private.*`

### Action on detection

1. **BLOCK commit immediately**
2. Show matching lines: `git diff --cached | grep -B2 -A2 <pattern>`
3. Suggest: "Add to .gitignore or use environment variables"
4. Propose unstage: `git reset HEAD <file>`

**Do not continue until the user confirms the issue is resolved.**

## Pre-push gate (harness)

See SKILL.md's HARD-GATE section for the pre-push hook description (env scrub, `artifact_check.check_stage`, fail-closed behavior) — not repeated here.

## Branch protection

### Never force push

- `main`, `master`, `production`, `prod`, `release/*`

If user requests a force push to these branches -> warn clearly, do not execute.

Force push to a feature branch (only if user has explicitly agreed):

```bash
git push -f origin HEAD
```

Warning: "Force push rewrites history. Collaborators may lose work."

### Pre-merge check

```bash
git merge --no-commit --no-ff origin/{branch} && git merge --abort
```

### Use remote for comparison

```bash
# Correct
git diff origin/main...origin/feature

# Wrong — includes local uncommitted changes
git diff main...HEAD
```

## Error recovery

### Undo last commit (not yet pushed)

```bash
git reset --soft HEAD~1   # keep changes staged
git reset HEAD~1          # keep changes unstaged
```

### Abort merge

```bash
git merge --abort
```

### Discard local changes

```bash
git checkout -- <file>    # single file
git reset --hard HEAD     # all changes (DANGEROUS)
```

**Always confirm with the user before running destructive operations.**
