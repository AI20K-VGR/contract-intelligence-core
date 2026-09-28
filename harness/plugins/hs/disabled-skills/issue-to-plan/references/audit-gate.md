# Audit gate (hs:issue-to-plan, Step 3)

Activate `hs:brainstorm` and evaluate the issue's fit against this repo's standards,
architecture, roadmap, security model, maintainability, and user value. Decide exactly ONE
outcome, post the evaluation comment BEFORE stopping or planning, and apply the label(s).

## The five outcomes

- **proceed to plan** — the issue is real, in scope, and worth doing; continue to Step 4.
- **needs decisions** — blocked on a human/product/architecture decision; apply the decision
  label with the required decisions and wait for maintainer input (stop unless a
  decision-oriented plan is explicitly useful).
- **duplicate / already handled** — covered by an existing issue, PR, or shipped code.
- **reject / defer** — out of scope or postponed, with a stated rationale.
- **not worth implementing** — the value does not justify the maintenance / security /
  complexity cost.

## Stop-rule

If the decision is **duplicate, already handled, reject, defer, needs-decisions, or not worth
implementing**, STOP here. Do NOT run `hs:plan`, do NOT create a worktree, and do NOT push a
branch. Apply `duplicate`, `deferred`, `wontfix`, `question`, or the repo-standard equivalent.
Only **proceed to plan** continues the pipeline.

## Evaluation comment (post before stopping or planning)

```markdown
## Issue-to-Plan Evaluation
- Classification: <bug|feature|refactor|docs|security-risk|task|decision>
- Scout findings: <real|already-implemented|duplicate|out-of-scope|under-specified>
- Evidence: <files/symbols/docs/prior PRs>
- Decision: <proceed to plan|needs decisions|duplicate|reject/defer|not worth implementing>
- Rationale: <one or two lines>
- Labels applied: <labels>
```

## Planning handoff (only when the gate passed and the plan was built)

```markdown
## Issue-to-Plan Handoff
- Decision: <ready for plan audit|need decisions>
- Branch: `<branch-name>`
- Plan: `<relative/path/to/plan.md>`
- Validation: <pass|revised>
- Red-team: <applied|N findings, M rejected with rationale>
- Unresolved questions: <list or none>
- Next: <recommended command or owner>

### Phase summaries
- Phase 1 — <name>: <one-line summary of what it delivers>
- <one line for every remaining phase in the plan>
```

## Labels

- `--plan-ready-label` (default `ready for plan audit`) when the plan is validated, red-teamed,
  pushed, and no blocking questions remain. A missing label is created, e.g.
  `gh label create "ready for plan audit" --color "0E8A16" --description "Plan validated and red-teamed; awaiting plan audit"`.
- `--decision-label` (default `need decisions`) when a human/product/architecture decision is
  needed before implementation.
- `duplicate`, `deferred`, `wontfix`, `question`, or a repo-standard label when the gate stopped
  the workflow before planning.
