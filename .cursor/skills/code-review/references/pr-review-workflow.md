---
name: pr-review-workflow
description: Details for the fix loop and reply mode of hs:code-review when reviewing a GitHub PR
---

# PR review workflow

Details for the `--fix` and `--reply` flags when reviewing a PR. SKILL.md orchestrates; this file is a drawer loaded on demand when either flag is used.

---

## Fix loop (`--fix`)

### 1. Decide whether a fix is needed

- No actionable findings → report **Approve**, stop.
- Actionable = all **Critical** + **Important** + **Suggestion** that are concrete, low-risk, and within PR scope.
- Do not invent new suggestions to keep the loop running.

### 2. Fix all findings

Delegate to `hs:fix --mode quick` with full context:

```
hs:fix --mode quick "Fix all actionable findings from hs:code-review <PR_REF>:
  <finding summary>"
```

Pass exactly:
- PR ref, base branch, head branch
- Changed files
- Each finding: severity · file path · line/function · expected vs actual · why it matters
- Constraint: stay within PR scope, no out-of-scope refactoring, keep public contract backward compatible (unless the finding requires a contract change)

`hs:fix` scouts, diagnoses, implements, and verifies on its own. Do not bypass its hard gate.

### 3. Commit and push

After `hs:fix` finishes verification:

```
hs:git cp
```

Do not run if: verification fails · a secret is detected · the working tree contains unrelated user changes.

### 4. Re-review

After a successful push, re-run `hs:code-review <PR_REF> --fix` (keeping `--reply` if it was set originally). Repeat until:

- Re-review finds no more actionable findings
- `hs:fix` is blocked due to a missing user/business decision
- A finding persists across 3 consecutive fix cycles (no convergence)
- CI or local verification fails in a way `hs:fix` cannot resolve

**Final fix-loop output:**
- Iteration count
- Final verdict
- Commits pushed
- Remaining findings (if any)
- Blockers or unresolved questions

---

## Reply mode (`--reply`)

### 1. Pre-flight

```bash
command -v gh >/dev/null 2>&1 || { echo "gh CLI not found — printing review locally"; exit 0; }
gh auth status >/dev/null 2>&1  || { echo "gh not authenticated — printing review locally"; exit 0; }
```

Failure → fallback to printing the review in chat; do NOT fail the entire skill.

### 2. Build the review body

Markdown containing: summary · risk level · findings by severity · verdict.
Traceability footer:

```
*Posted by hs:code-review at <ISO-8601 UTC timestamp>*
```

```bash
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

GitHub limit ~65 536 chars — if body > 60 000 chars, truncate the Findings section and append `[truncated — N findings omitted; see local output]`.

### 3. Map verdict → gh flag

| Verdict | Command |
|---|---|
| Approve | `gh pr review "$PR_REF" --approve --body-file -` |
| Request changes | `gh pr review "$PR_REF" --request-changes --body-file -` |
| Comment | `gh pr review "$PR_REF" --comment --body-file -` |

Pipe body via stdin to avoid shell-quoting issues.

### 4. Self-PR fallback

GitHub blocks approving your own PR (HTTP 422). If `--approve` fails with "Can not approve your own pull request" → retry with `--comment`. Record the downgrade in chat output.

### 5. Combined `--fix --reply`

Post **only the final re-review** once the loop converges. Iteration history lives in the commit log — keeps the PR conversation clean.

If the loop terminates due to a blocker → still post the review; let the verdict reflect remaining findings and note the blocker in the body so the human reviewer knows where to pick up.

---

## Final output (all modes)

Report in chat:
- Verdict (Approve / Request changes / Comment)
- Iteration count if `--fix` ran
- Commits pushed if `--fix` ran
- `--reply` result: succeeded / fallback / printed-locally
- Remaining findings or blockers
- Unresolved questions if any
