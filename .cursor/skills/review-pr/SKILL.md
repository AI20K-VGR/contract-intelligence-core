---
name: hs:review-pr
injectable: false
description: Review a GitHub PR or GitLab MR (forge auto-detected from the git remote) — diff, CI, correctness, security, breaking changes, anti-slop. Supports --fix (fix + commit) and --reply (post to the forge). Use for a full PR/MR review; for small local diffs use hs:code-review.
argument-hint: "<#PR|#MR|url> [--fix] [--reply] [--html] [--ultra [N] | --debate]"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob, Task]
metadata:
  compliance-tier: workflow
---

# hs:review-pr — comprehensive pull request review

Review PR `$ARGUMENTS` in this repository.

Relationship to **hs:code-review**: suited for a diff/commit/pending changes. hs:review-pr covers the PR/branch level — CI status, PR metadata, scope mismatch, --fix loop.

**What each step needs is routed by the CLI, not listed here.** Every envelope carries the
`rules` and `references` THIS state needs. Read what the envelope names, and only that. But a
satisfied envelope is not enough to have reviewed anything — the review lives in the PR's diff
and in the changed files on disk, so open those before forming a verdict.

## Modes

| Mode | When |
|---|---|
| Review-only (default) | Print findings to chat. No edits, commits, or pushes. |
| `--fix` | Review -> fix findings -> commit+push -> re-review. Loop until no actionable findings remain. |
| `--reply` | After review (or after the fix loop), post the review to GitHub via `gh pr review`. |

Flags combine: `review-pr 123 --fix --reply` runs fix loop then posts final review.

## Argument parsing

Extract `PR_REF` from `$ARGUMENTS`: strip `--fix`/`--reply`. Flags: substring match, order-independent.

No argument -> `AskUserQuestion`: PR number/URL, mode, --fix y/n.

## Workflow (hard)

### 1. Gather PR context

**Detect the forge first**, from `git remote get-url origin`, and use ONE CLI for the whole run — never mix `gh` and `glab`. A remote naming neither forge is a question for the user, not a guess. The CLI reports the same detection in every envelope (`forge`, `cli`), and routes the mapping drawer at each state where the answer stopped there.

For a **GitHub** remote, gather context with `gh`:

```bash
gh pr view "$PR_REF" --json title,body,author,baseRefName,headRefName,headRefOid,files,additions,deletions,changedFiles
gh pr diff "$PR_REF"
gh pr checks "$PR_REF" 2>/dev/null || echo "No checks found"
gh pr diff "$PR_REF" --name-only 2>/dev/null | head -50
```

For **GitLab**, use `glab mr` equivalents (`glab mr view "$PR_REF"`, `glab mr diff "$PR_REF"`, …; `glab mr view` prints text — JSON via `glab api`).

### 2. Read project context

Read `CLAUDE.md`, `docs/code-standards.md`, `docs/system-architecture.md` if present — detect project-specific convention violations.

**Structured rule layer** (preferred): the prose pattern in `references/project-rules-example.md` is now encoded as a diff-aware rule layer — run `rule_view.load_rules_dual` over the changed files (operational rules from the standards tree, the single source), judge the applied rules, and write `rule-scan.json` via `rule_view.build_rule_scan` (records `changed_files`). See
`code-review/references/review-rules-layer.md` for the procedure and the rule-scan/gate contract. To add a per-repo rule, use the rule-author skill (it writes `standards.user.yaml`). `references/project-rules-example.md` is retained as a worked example of the rule shape.

### 3. Mandatory gates

Two gates run before the verdict, and both produce findings even when the code is correct: the **Duplicate / prior-work gate** and the **Strategic-necessity gate**. What each one searches, and the severity a failed one carries, arrives with the envelope at the state where the verdict is being formed — run them from that drawer rather than from memory.

(Project standards already loaded in step 2 — no separate standards gate needed.)

### 4. Analyze the diff

Read each changed file. For modified files, read the full file (not just the diff) for surrounding context. Check:

**Correctness**: logic error, off-by-one, nil/null dereference, missing error handling, race condition, edge case.

**Security**: injection (SQL/XSS/command/SSRF/path traversal), hardcoded secrets, missing input validation at system boundary, auth gap.

**Breaking changes**: API contract change without migration/shim, schema change without migration, removed/renamed public interface.

**Anti-slop**: the taxonomy — with its severity rules, phrasing guide and stack appendix —
arrives with the envelope at the verdict state. Its trigger conditions are what a reader has to
hold here: a diff over ~300 lines, or more than two new files landing in
`utils/`/`helpers/`/`lib/common/`, or any single one of a generic new file name, a parallel
reimplementation of an existing utility, an abstraction with one caller, a config flag standing
in for a constant, catch-and-swallow, a linter silencer, phantom coverage, a title that does not
match the diff's size, or LLM-style commit messages.

**Testing**: Are new code paths tested? Do existing tests still pass? Phantom coverage?

### 5. Synthesize findings

**Summary**: 1-2 sentences on what the PR does.

**Mandatory gates**: Duplicate — clear | overlap | duplicate · Strategic necessity — clear value | questionable | not justified. A failed gate blocks at **Important** severity.

**Risk level**: Low / Medium / High — by scope, complexity, breakage potential.

**Findings** by severity:
- **Critical**: must fix before merge (bug, security, data loss)
- **Important**: should fix (logic issue, missing validation, structural slop)
- **Suggestion**: nice-to-have (style, micro slop)

> Severity rule: structural slop -> Important; micro slop -> Suggestion.
> If you cannot articulate a **concrete cost** in this codebase -> do not flag.

**Verdict**:
- **Approve** — no Critical or Important findings
- **Request changes** — has Critical or Important findings
- **Comment** — Suggestions only, safe to merge

## Fix loop (`--fix`)

Do not stop at "code review clean" while merge conflicts or failing/pending checks remain. Blocking set = union of: review findings (all Critical/Important + concrete in-scope Suggestions), **merge state** from `gh pr view "$PR_REF" --json mergeStateStatus,baseRefName,headRefName,headRefOid`, **CI** from `gh pr checks "$PR_REF"` + `statusCheckRollup`. Approve only when all three are clear.

1. If no actionable findings, no merge blockers, all required checks green -> stop, report **Approve**.
2. Fix findings using `hs:fix` with full context (PR ref, base/head branch, changed files, each finding: severity / file / line / expected / actual / why).
   Constraints: stay within PR scope, do not refactor outside scope, do not break the public contract unless the finding requires it.
3. Before committing, verify the worktree is still on the PR head: `git rev-parse HEAD` must match `headRefOid` from step 1. If diverged, re-fetch PR metadata, warn of concurrent changes — do not commit to the wrong branch. After `hs:fix` verifies -> `hs:git` commits+pushes to the PR head branch. Do not push if verification failed, secrets present, or the working tree has unrelated changes.
4. **Resolve conflicts.** If the PR is not mergeable (branch stale or conflicted): `git fetch origin` → merge or rebase the PR head against `origin/<baseRefName>` per repo convention → resolve every conflict in real files → run the relevant tests → commit. Never mark the loop complete while `mergeStateStatus` still indicates conflicts.
5. **Watch CI.** After the push, drive the poll loop from the CLI — it owns the round counting
   and the 30-minute ceiling, so neither is re-derived by hand:
   `hs-run review-pr next --poll-n 0`, then re-run the command its `next_command` names,
   verbatim, until the exit code leaves 11. Two rungs, and only two: **11** means one more
   round — wait the interval the printed hint states (~60s, thirty rounds to the ceiling),
   then run that command. **0** means this verb has nothing further to report, which is NOT
   the same as CI passing: it covers both all-green and no-checks-at-all, and the `state`
   is what tells them apart. Everything else — a failing check, the ceiling, an
   unauthenticated CLI, a CLI that is not installed, a remote naming no known forge — is
   exit **2**, so the exit code alone never distinguishes "CI is broken" from "the tooling
   could not ask". Read `state` and `warnings` before concluding anything about the PR.
   `--poll-n` is required; omitting it is exit 2, because a loop that silently restarts at 0
   can never reach the ceiling.
   **Name the PR when it is not yours**: with no `--pr`, the verb answers about the PR/MR of
   the branch currently checked out — so reviewing someone else's PR without checking it out
   returns a confident, correctly-shaped answer about a different PR. Pass
   `--pr <number|url|branch>` (GitLab: the MR's branch) and the ref rides every round of the
   loop and comes back in the envelope's `pr` field.
   **The rerun judgment stays here, not in the CLI**: on a clearly transient infrastructure
   failure, `gh run rerun <run-id> --failed` once then re-watch — do NOT rerun to hide a
   deterministic failure. `ci_failed` reports THAT checks failed; whether a failure is
   transient is a judgment the verb never makes and never authorises. All required checks must
   be green before an
   **Approve** verdict in `--fix` mode.
6. Re-review: repeat from step 1 with `--fix` (and `--reply` if set initially).

Stop when:
- Re-review has no remaining actionable findings, no merge conflicts, all required checks green
- `hs:fix` is blocked by an open user/business decision
- The same blocker survives 3 fix attempts (loop doesn't converge)
- An external blocker remains (missing credentials, service outage, unavailable approval)

Final `--fix` output: iteration count, final verdict, commits pushed, remaining findings, blockers.

## Reply mode (`--reply`)

Posts the review to the PR. Full procedure: `references/reply-mode.md` — gh pre-flight (falls back to local print if gh absent/unauthenticated, never fails the skill), body format + footer + 60k cap, verdict→`gh pr review` flag map, self-PR 422→`--comment` fallback, `--fix --reply` (posts final re-review on convergence).

## Final output

- Verdict (Approve / Request changes / Comment)
- Iteration count if `--fix` ran
- Commits pushed if `--fix` ran
- `--reply` succeeded / fell back / printed-locally
- Remaining findings or blockers
- Open questions if any

`--ultra [N]`/`--debate`: call `hs:workflow-orchestrate --ultra [N]|--debate --run-id <slug>` to size + drive N independent review passes over the SAME diff (no shared context); `hs:escalation-consultant` synthesizes the verdict, and only that synthesized verdict feeds the `--fix`/`--reply` steps below. Approval gate is `hs:workflow-orchestrate`'s own.

## Auto-decision ledger

When acting autonomously (editing or deciding without asking), append one advisory line per governance-bearing decision. The rule arrives with the envelope at the state where that autonomy is actually exercised — deciding alone whether a failed check is worth rerunning.
