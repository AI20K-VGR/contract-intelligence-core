# Workflow: commit (cm)

Delegates to `hs:git-manager` agent. Maximum 4 tool calls.

## Tool 1 — Stage + analyze + secret scan

```bash
git add -A && \
echo "=== STAGED ===" && git diff --cached --stat && \
echo "=== SECURITY ===" && \
git diff --cached | grep -c -iE "(AKIA|api[_-]?key|token|password|secret|credential|private[_-]?key|mongodb://|postgres://|-----BEGIN)" | awk '{print "SECRETS:"$1}' && \
echo "=== GROUPS ===" && \
git diff --cached --name-only | awk -F'/' '{
  if ($0 ~ /\.(md|txt)$/) print "docs:"$0
  else if ($0 ~ /test|spec/) print "test:"$0
  else if ($0 ~ /package\.json|lock/) print "deps:"$0
  else print "code:"$0
}'
```

**SECRETS > 0 -> STOP.** Show matching lines, block commit. See `safety-protocols.md`.

## Tool 2 — Split decision

From groups, choose:

**A) Single commit** — same type/scope, FILES <= 3, LINES <= 50

**B) Multi commit** — different type/scope, group:
- `docs:` -> `docs: ...`
- `deps:` -> `chore(deps): ...`
- `test:` -> `test: ...`
- `code:` -> `feat|fix|refactor: ...`

See full standards: `commit-standards.md`.

## Tool 3 — Commit

**Single:**
```bash
git commit -m "type(scope): description"
```

**Multi (sequential, reset then add each group):**
```bash
git reset
git add file1 file2 && git commit -m "type(scope): desc"
# repeat for each group
```

## Tool 4 — Push (only for `cp`)

```bash
git push && echo "pushed: yes" || echo "pushed: no"
```

Only push if the user explicitly requested it (`cp`, "commit and push"). Pre-push hook `harness/install/git-pre-push-hook.sh` runs automatically — do not bypass.
