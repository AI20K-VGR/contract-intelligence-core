# Gate Sequence — hs:ship

Detail for each pipeline step. Read when tracing a gate error or debugging an artifact.

## Step 1 — Preflight

Load `references/preflight-checklist.md`. Summary: branch check → mode detect
→ diff summary → secret scan → dry-run gate → early artifact warning.

## Step 2 — Merge target

```bash
git fetch origin <target>
git merge origin/<target> --no-edit
```

- Auto-resolvable conflicts (lockfile, version file): resolve and continue.
- Complex conflicts → **STOP**, show conflicting files.
- Already up-to-date → continue silently.

## Step 3 — Test

Skip if `--skip-tests`.

Auto-detect runner in order:
`pytest.ini/pyproject.toml[tool.pytest]` → `pytest` | `package.json scripts.test` → `npm test` | `Makefile test:` → `make test` |
`Cargo.toml` → `cargo test` |
`go.mod` → `go test ./...`

Delegate to `hs:test`. Do not inline test execution.

- Any test FAIL → **STOP**. Do not continue the pipeline.
- No runner found → AskUserQuestion: ["Skip tests", "Enter test command"].

## Step 4 — Review → review-decision.json

Skip only if `review-decision.json` already exists with verdict PASS (a prior cook run already performed the review).

If missing or verdict ≠ PASS: delegate to `hs:code-review`.

`hs:code-review` writes:
```
plans/<active-plan>/artifacts/review-decision.json
  verdict: PASS | PASS_WITH_RISK | BLOCKED
```

**Verdict rule (hard)**:
- `PASS` → continue.
- `PASS_WITH_RISK` → **STOP**: AskUserQuestion ["Fix now and re-review", "Accept risk (BLOCKED ship)", "Cancel"]. Gate `stage-policy.yaml` requires exactly `PASS` — no workaround.
- `BLOCKED` → **STOP**: must fix, re-review, get a new verdict.

## Step 5 — Verification artifact check

`verification.yaml` (preferred) or legacy `verification.json` must exist at `plans/<active-plan>/artifacts/`.
Pass conditions:
- File exists.
- No check has `status: FAIL`.
- `verdict` is `PASS` (not `BLOCKED`).

This artifact is produced by `hs:cook` when a phase runs — if missing, the user must run cook or create it manually per schema `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json`.

```bash
python3 -c "
import pathlib, sys
sys.path.insert(0, 'harness/scripts'); import artifact_check
d = artifact_check.resolve_active_plan('.')
if not d: sys.exit('verification: no active plan')
p = artifact_check._artifact_path(pathlib.Path(d), 'verification')
if not p.is_file(): sys.exit('verification: MISSING')
v, err = artifact_check._load_artifact(pathlib.Path(d), 'verification')
if err: sys.exit(f'verification: {err}')
fails = [c for c in v.get('checks',[]) if c.get('status')=='FAIL']
if fails: sys.exit(f'verification FAIL checks: {fails}')
if v.get('verdict') == 'BLOCKED': sys.exit('verification verdict: BLOCKED')
print('verification:', v.get('verdict'))
"
```

## Step 6 — Plan approval artifact check

`plan-approval.yaml` (preferred) or legacy `plan-approval.json` must exist at `plans/<active-plan>/artifacts/`.

Check using the official script:
```bash
python3 -c "import sys,pathlib; sys.path.insert(0,'harness/scripts'); import artifact_check; d=artifact_check.resolve_active_plan('.'); sys.exit(0 if d and artifact_check._artifact_path(pathlib.Path(d),'plan-approval').is_file() else 1)" || echo "plan-approval: MISSING"
```

The artifact is created by the approver via `plan_approval.py`. The gate is **personal-first SLIM** — it checks ONLY:
- `verdict: APPROVED`
- `plan_hash` matches the current plan hash (drift → FAIL)
- the artifact parses and carries the required fields

There is **no roster and no reviewer≠author check** (`artifact_check.py`): actor fields are attribution, never authorization, and self-approval is deliberate anti-drift discipline — actor strings stay spoofable by design. "No self-ship" is NOT enforced here.

If the plan is edited after approval → hash drift → the `plan-approval` check FAILs on the `pr`/`ship`/`merge` stage.
Resolution: re-approve after editing the plan.

## Step 7 — Changelog + Version (conditional)

**Changelog**: look for `CHANGELOG.md` / `CHANGES.md` / `HISTORY.md`. If none → skip silently.

Generate entry from `git log origin/<target>..HEAD --oneline` + diff.
Classify: Added (feat:) | Changed (refactor:/perf:) | Fixed (fix:) | Removed. Do not ask the user for content — infer from commits + diff.

**Version**: look for `VERSION` / `package.json` / `pyproject.toml` / `Cargo.toml`. If none → skip silently.

Bump logic:
- Default → patch (the safe default, regardless of diff size)
- Breaking change / major feature → AskUserQuestion: ["Minor", "Patch"]

## Step 8 — Release notes

Load `references/release-notes.md` to generate PR body content.

## Step 9 — Commit + Push

Stage everything:
```bash
git add -A
```

Final secret scan before committing:
```bash
git diff --cached | grep -iE "(AKIA|api[_-]?key|token|password|secret|credential|private[_-]?key|mongodb://|postgres://|-----BEGIN)"
```
Match found → **STOP immediately**.

Conventional commit:
```bash
git commit -m "$(cat <<'EOF'
type(scope): description

Short body from changelog entry or commit log.
EOF
)"
```

Push:
```bash
git push -u origin $(git branch --show-current)
```

**Pre-push hook** `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/push_gate.py` (wired via `git-pre-push-hook.sh`) runs automatically.
Its ONLY hard blocks: the two Tier-A floors — a **destructive push to a protected branch** and a
**detected secret** (exit non-zero). A **missing/failed receipt only WARNs** —
`[pre-push warn] … remote receipts-gate will enforce`, then exit 0. It does NOT fail-closed on a missing
`verification.json`.

A `git push` detects as the **`push` stage** (`gate_stage.py` + `stage-policy.yaml`), requiring only `verification` and **ADVISES** (exit 0 + `[advisory]`) — it does not block. The 3-artifact floor (`verification` + `review-decision` + `plan-approval`) enforces at the **`pr` stage** when `gh pr create` runs; hard presence enforcement = the remote receipts-gate.

If push is rejected: suggest `git pull --rebase` → retry once. No force push.

## Step 9.5 — Link Issues

Find or create related GitHub issues for traceability, before the PR:

```bash
# Search existing open issues by keywords from the branch name
BRANCH=$(git branch --show-current)
KEYWORDS=$(echo "$BRANCH" | sed 's/[^a-zA-Z0-9]/ /g' | tr '[:upper:]' '[:lower:]')
gh issue list --state open --limit 10 --search "$KEYWORDS"
# Also scan commits for already-referenced issues
git log <target>..HEAD --oneline | grep -oE '#[0-9]+' | sort -u
```

- **Issues found** → note numbers for the PR's `Linked Issues` block.
- **None found** → `gh issue create` with a structured body whose `Human Review Tasks` checklist matches the PR template below; store the new number for Step 10.

## Step 10 — PR

```bash
gh pr create \
  --base <target-branch> \
  --title "type(scope): description" \
  --body "$(cat <<'EOF'
## Summary
<bullets from commit log>

## Linked Issues
<from Step 9.5>
- Closes #XX — <issue title>
- Relates to #YY — <issue title>
<or "No linked issues.">

## Pre-Landing Review
<verdict + findings from step 4>

## Test Results
- [x] All tests pass (<N> tests)

## Changes
<git diff --stat trimmed>

## Ship Mode
- Mode: official|beta
- Target: <target-branch>

## Human Review Tasks
- [ ] Verify business logic correctness
- [ ] Check for edge cases not covered by tests
- [ ] Validate UX/API contract changes (if any)
EOF
)"
```

If a PR already exists for the branch → use `gh pr edit` instead of create.

**Final output**: PR URL — what the user sees.

## Error handling summary

| Error | Action |
|-----|-----------|
| Artifact MISSING | Show which artifact is missing, suggest how to create it |
| Gate exit 2 | Read gate stderr, report the artifact error |
| Push rejected | `git pull --rebase`, retry |
| `gh` not installed | Guide installation, stop after push |
| Plan hash drift | Re-approve plan via `plan_approval.py` |
