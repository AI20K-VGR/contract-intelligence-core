---
name: hs:vibe
injectable: true
description: One command takes a GitHub issue or feature request through the whole SDLC spine — worktree, planned gates, cook or fix, code-review, ship PR, review-pr, and optional merge with post-merge CI convergence. Use for issue→merged-PR autonomous runs.
argument-hint: "[--ship] [--beta] <github-issue-url | feature request>"
allowed-tools: [Bash, Read, Glob, Grep, Task, SlashCommand]
metadata:
  compliance-tier: workflow
---

# hs:vibe — issue → merged-PR pipeline

One command drives a request through the SDLC spine to a review-ready PR (and, with `--ship`, to a merged commit with post-merge CI convergence). vibe is an **orchestrator**: it chains existing harness skills and **bypasses no gate**. The plan-approval HUMAN gate, the cook plan-exists gate, the ship review-PASS + verification-PASS + human-approval gate, the protected-branch + stage policy, and
the security floors all stay exactly where they are — vibe routes through them, it does not re-implement or weaken them.

## When to use

A GitHub issue, feature request, or bug report to carry end-to-end without hand-driving each step. For a single SDLC step, invoke that skill directly (`hs:plan`, `hs:cook`, …).

## Inputs

```bash
/hs:vibe <github-issue-url>
/hs:vibe --ship --beta <github-issue-url>
/hs:vibe --ship <feature request>
```

| Flag | Effect |
|---|---|
| `--beta` | Ship to the beta/dev target via `hs:ship beta`; final ready label `ready to ship beta`. |
| `--ship` | After review/fix/reply, merge the PR and watch/fix target-branch CI until green or a true external blocker. |
| no `--beta` | Ship stable via `hs:ship official`; final ready label `ready to ship stable`. |
| no `--ship` | Stop after the PR is reviewed, fixed, replied, and labeled ready. |

A GitHub issue is the source of truth — never open a duplicate. Natural-language input becomes a new issue only **after** the plan passes validation + red-team.

## Pipeline (detail: `references/pipeline.md`)

1. **Parse & analyze** — strip flags; resolve repo (`gh repo view`); for an issue URL, confirm `OWNER/REPO` matches the current repo (else stop and ask); read the issue (`gh issue view`) or the request text; extract outcome, acceptance criteria, scope, constraints, touched surfaces; classify route (**bugfix** vs **feature**); detect a reusable existing `plan.md`. Ambiguity that changes
   implementation → ask before creating a worktree.
2. **Worktree** — `hs:worktree` for an isolated branch off the default base; descriptive name; reuse a matching clean worktree if present. Never work on a protected branch.
3. **Plan + gates** — reuse a valid `plan.md` or `hs:plan` to author one; then ALWAYS run the harness gates: validate + red-team + the whole-plan consistency sweep. The plan's **HUMAN approval gate is real** — vibe cannot self-approve. Do not implement while validation failures, accepted red-team findings, or contradictions remain.
4. **Issue intake** — ensure labels exist (`ready to cook` / `in progress` / `ready to ship stable` / `ready to ship beta`); update the source issue or create one (route, branch, relative plan link, ship mode, acceptance criteria). Add `ready to cook`; clear stale ready labels.
5. **Implement** — flip the issue to `in progress`; then route: feature → `hs:cook` (honor every hard gate, autonomy cadence applies), bugfix → `hs:fix` (failure evidence + plan + scope + acceptance). A user/business blocker → record on the issue and stop.
6. **Local review** — `hs:code-review`; resolve Critical + Important findings; re-verify.
7. **Ship PR** — `hs:ship beta` or `hs:ship official`; the ship gate (review-PASS + verification-PASS + human approval) still governs. Capture the PR URL/number.
8. **Review/fix/reply PR** — `hs:review-pr <pr> --fix --reply`; continue only when actionable findings are resolved or an external blocker is recorded; checks terminal + green.
9. **Ready label** — add `ready to ship beta|stable` to issue + PR; remove `ready to cook` / `in progress`.
10. **Optional merge + CI converge** (`--ship` only) — merge by repo convention + branch
    protection (`gh pr merge --auto` when checks pending); never force-push, never direct-push a
    protected branch. Watch target-branch CI for the merge commit; on a deterministic repo-fixable
    failure, branch from target, `hs:fix` with the exact error, re-ship + re-review + re-watch.
    Stop at green, an external blocker, or the same blocker surviving 3 attempts.

## Autonomy & gates

vibe respects `HARNESS_AUTONOMY` / `autonomy_policy.py` cadence — it pauses at the same human checkpoints (plan approval, ship) any autonomous run does, and cannot self-merge past a human gate. Where unattended machinery overlaps `hs:afk`, lean on afk over duplicating it. The real gate wiring (`plan_approval.py`, stage-policy, protected-branch guard) is unchanged:
vibe supplies the artifacts those gates require, it never edits the gate config.

## Security

Never write secrets/tokens/customer data/private env into issues, PRs, comments, plans, or logs; redact command output before posting. If `gh` auth lacks a needed capability (label/issue/PR/ review/merge), stop and report the exact missing capability. CI failing on missing secrets, unavailable services, or required human approval = an **external blocker**, recorded — never weaken a test or
hide a failure to make it pass.

## Completion report

End with a `Vibe Result` block: source, branch/worktree, plan (relative), issue URL, PR URL, mode, route, review outcome + fix iterations, merge (skipped|merged|blocked), CI (green|failed|blocked), and an Unresolved-questions list. Template: `references/pipeline.md`.

## Related skills

- `hs:afk`: unattended plan/PRD runner — vibe's autonomous overlap leans on it.
- `hs:worktree` / `hs:plan` / `hs:cook` / `hs:fix` / `hs:code-review` / `hs:ship` /
  `hs:review-pr`: the spine skills vibe orchestrates.

## Auto-decision ledger

When acting autonomously (editing or deciding without asking), append one advisory line per governance-bearing decision — see `"${HARNESS_BIN_ROOT:-.}"/harness/rules/auto-decision-ledger.md`.
