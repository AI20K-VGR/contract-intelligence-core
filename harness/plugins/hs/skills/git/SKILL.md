---
name: hs:git
injectable: false
description: "Git operations with conventional commits. Use for commit, push, PR, merge. Auto-split commits by type/scope. Scan for secrets before committing."
allowed-tools: [Bash, Read, Grep, Glob, Task]
argument-hint: "cm|cp|pr|merge|merge-pr [args]"
metadata:
  compliance-tier: workflow
---

# hs:git — git operations

Delegates verbose git ops to the `@git-manager` agent. This skill is the thin orchestration core.

**What each step needs is routed by the CLI, not listed here.** Every envelope carries the
`rules` and `references` THIS state needs. Read what the envelope names, and only that. But a
satisfied envelope is not enough to have committed anything — the files on disk and the staged
diff are what the commit is about, so read those too.

## Default (no argument)

Use `AskUserQuestion` to ask which operation:

| Operation | Description |
|-----------|-------------|
| `cm` | Stage + commit |
| `cp` | Stage + commit + push |
| `pr` | Create Pull Request |
| `merge` | Merge branch |
| `merge-pr` | Merge an open PR (gh) |

## Arguments

- `cm` — stage + commit
- `cp` — stage + commit + push
- `pr [to-branch] [from-branch]` — PR (default: main <- current)
- `merge [to-branch] [from-branch]` — merge (default: main <- current)
- `merge-pr [number] [--squash|--merge|--rebase]` — merge an existing open PR via `gh pr merge` (default: the current branch's PR, `--squash`); load `references/workflow-merge-pr.md`

## Core workflow

1. **Stage + analyze**: `git add -A && git diff --cached --stat && git diff --cached --name-only`
2. **Secret scan (required before commit, MUST NOT skip)** — TWO layers, both required:
   - `hs-run git next` — the typed-pattern scan plus the split decision. exit 2
     `secret_found` → STOP, `warnings` names the pattern. exit 2 `unresolved_conflict` /
     `git_diff_failed` → STOP, the tree or git itself is not in a committable state. exit 0
     `nothing_staged` → `git add` first. exit 10 `ready` → `artifacts[0]` gives `plan`
     (`single`|`grouped`), `files`, `added_lines` for step 3.
   - **The routed commit drawer's grep (Tool 1) STILL RUNS.** A clear `commit-plan`
     is not a clear tree: that verb excludes `tests/ spec/ fixtures/ examples/ mocks/`,
     `test_*.py`, and `*.md *.lock *.example *.sample *.template *.dist` (standard practice, so
     the gate does not block on its own fake-secret fixtures), while the grep excludes nothing.
     Measured on one AWS key: at `app/main.py` the verb exits 2; the identical key at
     `tests/conftest.py` + `docs/setup.md` exits 10 `ready` while the grep still counts 2.
   **Secret found by EITHER layer → STOP immediately.** Warn the user, suggest `.gitignore` /
   environment variables. Do not continue committing until the user confirms the issue is
   resolved.
3. **Split decision + commit**: take `plan`/`files`/`added_lines` from step 2 —
   single-commit (same type/scope, FILES <= 3, LINES <= 50) vs multi-commit grouping
   (config/deps/test/code/docs separately), then `git commit -m "type(scope): description"`.
   The verb sizes the split; it never picks the message or the grouping.
4. **Push (`cp` only)**: `hs-run git next` again. Nothing is staged any more (the commit just
   took it), so `next` moves past the commit question and answers the push question instead —
   the same one door, not a second command. exit 10 `no_upstream` → this branch has never been
   pushed, use `git push -u origin HEAD`, not a plain push. exit 0 `nothing_to_push` → HEAD is
   already even with its upstream, nothing to do. exit 10 `ready_to_push` → `artifacts[0]` gives
   `upstream`/`commits`, safe to `git push`. exit 10 `push_gate_blocked` → the push itself
   will succeed, but CI's receipts-gate will refuse the result; `artifacts[0].gate_reason`
   names the gap. Close it first, or push knowing CI will red.
   For `cm` (commit only, no push): if step 2 answers `nothing_staged` because there was nothing
   to commit in the first place, stop there per Error handling below — `next`'s push-question
   fallthrough is what step 4 is for, not step 2 repeating itself.

## Output format

```
✓ staged: N files (+X/-Y lines)
✓ security: passed
✓ commit: HASH type(scope): description
✓ pushed: yes/no
```

## Error handling

| Error | Action |
|-------|--------|
| Secret found | Block commit, show file |
| No changes | Exit cleanly |
| Push rejected | Suggest `git pull --rebase` |
| Merge conflicts | Report to user |

## Operations with no verb behind them

These four are chosen from the argument you were given, not from anything on disk, so no state
routes their drawer. Open the one the argument names.

| Task | Reference |
|------|-----------|
| Pull Request | `references/workflow-pr.md` |
| Merge | `references/workflow-merge.md` |
| Merge open PR | `references/workflow-merge-pr.md` |
| Branch lifecycle | `references/branch-management.md` |
| GitHub CLI | `references/gh-cli-guide.md` |

## HARD-GATE (real wiring)

**Pre-push hook** `harness/install/git-pre-push-hook.sh` runs on ALL pushes at the transport layer — regardless of whether push is invoked via alias, eval, wrapper, or `sh -c 'git push'`:
- Scrubs all `HARNESS_*` env before checking (prevents override)
- Blocks locally on exactly three things: a destructive push to a protected ref, a secret in the diff, and a forged artifact
- Calls `artifact_check.check_stage("push", root)` — a missing `verification.json` prints `[pre-push warn]` and lets the push through; CI's receipts-gate is what enforces it
- No git repo, or no `python3` -> fail-closed exit 2 (gate does not silently pass)

**git-manager agent** (`harness/plugins/hs/agents/git-manager.md`): receives delegated verbose git ops (2-4 tool calls); re-invokes the `hs:git` skill internally.

Do not modify `.git/hooks/pre-push` to bypass the gate — any anomaly -> ask a human.

## Boundaries

- MUST NOT commit if the secret scan matches — STOP and ask the user before continuing.
- NO force push to `main`/`master`/`production` — warn if user requests it.
- Do NOT push automatically when the user only invokes `cm` (without `cp`).
- Do not write AI attribution into commit messages.
- YAGNI: do not create new remotes/configs outside the request scope.
- Activate `hs:context-engineering` if context is nearly full before a large op.
