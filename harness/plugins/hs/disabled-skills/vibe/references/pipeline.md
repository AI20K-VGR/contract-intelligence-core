# vibe pipeline — full step detail

Detail behind `SKILL.md`'s 10-step summary. Every command routes through an existing harness skill or `gh`; vibe adds no gate of its own and edits no gate config.

## 1. Parse and analyze the request

- Strip `--ship` and `--beta` from the arguments.
- If the remaining input is a GitHub issue URL/number, treat that issue as the source of truth — do not create a duplicate.
- If the remaining input is natural language, treat it as the feature request and create the GitHub issue only **after** the plan passes validation + red-team.
- Resolve the repo: `gh repo view --json nameWithOwner,defaultBranchRef`.
- For an issue URL, parse `OWNER/REPO` from the URL and compare with the current repo. If they differ, stop and ask the user to switch to the matching repo/worktree or supply an issue from the current repo.
- For an issue input, read title + body + comments with `gh issue view`. For natural-language input, use the text directly.
- Extract concrete outcome, acceptance criteria, scope boundary, non-negotiable constraints, blockers, and the surfaces likely touched.
- Classify the implementation route:
  - **Bugfix route** — a bug, regression, broken behavior, failing test/CI, production/staging
    incident, error log, or an explicit fix/debug/repair ask.
  - **Feature route** — net-new capability, enhancement, refactor, or ambiguous product work.
- Detect a reusable plan: a user-supplied plan path, a `plans/.../plan.md` linked in the issue body/comments, or a matching plan already in the current worktree. Verify the file exists before treating it as reusable.
- If anything ambiguous would change the implementation, ask **before** creating a worktree. Otherwise proceed and carry the extracted requirements into planning and the issue updates.

## 2. Isolated worktree and branch

- `hs:worktree` to create an isolated worktree + branch off the default base.
- Descriptive branch name derived from the issue/request.
- Reuse an existing clean matching feature worktree/branch if present, and record why.
- Never work directly on a protected branch (`main`, `master`, `dev`, `beta`, `develop`).

## 3. Plan intake and gates

- If a valid existing `plan.md` was detected, set its absolute path, reuse it, and skip planning.
- Otherwise, in the new worktree run `hs:plan` (TDD mode) on the source issue / feature request; capture the absolute `plan.md` path it emits.
- ALWAYS run both gates, even on a reused plan: the harness plan **validate** pass and the
  **red-team** pass, then the whole-plan consistency sweep `hs:plan` requires.
- The plan's HUMAN approval gate is real (`plan_approval.py`) — vibe cannot self-approve. Do not proceed to implementation while validation failures, accepted red-team findings, or unresolved contradictions remain.

## 4. Create or update the GitHub issue

Ensure the pipeline labels exist (create any that are missing; stop and report the exact `gh` error on any failure other than "already exists"):

```bash
gh label list --json name --jq '.[].name' | grep -Fx "ready to cook" >/dev/null \
  || gh label create "ready to cook" --color "0E8A16" --description "Plan validated; ready for hs:cook or hs:fix"
gh label list --json name --jq '.[].name' | grep -Fx "in progress" >/dev/null \
  || gh label create "in progress" --color "FBCA04" --description "Implementation is in progress"
gh label list --json name --jq '.[].name' | grep -Fx "ready to ship stable" >/dev/null \
  || gh label create "ready to ship stable" --color "5319E7" --description "PR reviewed and ready for stable merge"
gh label list --json name --jq '.[].name' | grep -Fx "ready to ship beta" >/dev/null \
  || gh label create "ready to ship beta" --color "1D76DB" --description "PR reviewed and ready for beta merge"
```

- Compute the plan link relative to the repo root.
- If a source issue exists, update/comment on it; if the input was natural language, create the issue now. The issue update must include: branch name, route (feature via `hs:cook` / bugfix via `hs:fix`), implementation summary, relative plan link, ship mode (official|beta), and the acceptance criteria from the plan.
- Add `ready to cook`; remove stale `ready to ship stable` / `ready to ship beta`.

## 5. Implement or fix

Before implementing, flip the issue state:

```bash
gh issue edit <issue-number-or-url> --add-label "in progress" --remove-label "ready to cook"
```

(If `ready to cook` is not currently set, add `in progress` without `--remove-label`. On any other failure, stop and report the exact `gh` error — do not start while the issue still says `ready to cook`.)

- **Bugfix route**: `hs:fix` in auto mode, passed the source issue/request, failure evidence, validated plan path, scope boundary, and acceptance criteria. Honor every hard gate in `hs:fix`.
- **Feature route**: `hs:cook` in TDD + auto mode on the plan. Honor every hard gate in `hs:cook`; the `HARNESS_AUTONOMY` cadence (plan-approval + ship pauses) still applies.
- If implementation stops for a user/business decision, update the issue with the blocker and stop.

## 6. Review the local implementation

- `hs:code-review` over the pending changes.
- Resolve Critical and Important findings before shipping; re-run the relevant validation after.

## 7. Ship the PR

- `--beta` → `hs:ship beta`; otherwise `hs:ship official`.
- The ship gate (review-PASS + verification-PASS + human approval + stage policy) still governs; vibe supplies the artifacts, it does not bypass the gate.
- Capture the PR URL/number from the ship output.

## 8. Review / fix / reply the PR

- `hs:review-pr <pr-url-or-number> --fix --reply`.
- Continue only when actionable findings are resolved or an external blocker is documented. PR checks must be terminal and green unless the blocker is external and recorded.

## 9. Apply the ready label

- Beta mode → `ready to ship beta`; otherwise `ready to ship stable`.
- Apply to both the source issue and the PR when possible.
- Remove `ready to cook` and `in progress` once PR review/fix succeeds.

## 10. Optional merge and CI convergence (`--ship` only)

- Merge via GitHub using repo convention + branch protection. Prefer `gh pr merge --auto` when required checks are still pending; otherwise the repo's allowed merge method.
- Never force-push. Never direct-push to a protected target branch (the protected-ref guard enforces this independently).
- After merge, watch the target-branch CI/deploy workflows for the merge commit.
- On a deterministic, repo-fixable CI failure:
  1. Inspect the failed run/job logs (`gh run view`).
  2. Branch a follow-up fix worktree from the target branch.
  3. `hs:fix` in auto mode with the exact failing command/error evidence.
  4. Ship the follow-up in the same mode, `hs:review-pr --fix --reply`, merge, watch again.
- Stop only when target-branch CI succeeds, an external blocker remains, or the same blocker survives 3 fix attempts.

## GitHub issue body template

```markdown
## Outcome
<user-visible outcome>

## Implementation
- Branch: `<branch-name>`
- Plan: `<relative/path/to/plan.md>`
- Mode: `<official|beta>`
- Route: `<feature|bugfix>`
- PR: `<url once created>`

## Acceptance Criteria
- [ ] <criterion from plan>

## Pipeline State
- [x] Worktree and branch created
- [x] Plan created or existing plan reused
- [x] Plan validated
- [x] Plan red-teamed
- [x] Issue labeled `in progress` before implementation
- [ ] Implementation complete
- [ ] PR reviewed and fixed
- [ ] Merged and CI green (only when --ship)
```

## Completion report template

```markdown
**Vibe Result**
- Source: <issue/request>
- Branch/worktree: <branch> | <path>
- Plan: <relative path>
- Issue: <url>
- PR: <url>
- Mode: official|beta
- Route: feature|bugfix
- Review: <approve/request-changes/comment + fix iterations>
- Merge: skipped|merged|blocked
- CI: green|failed|blocked

Unresolved questions:
- None
```
