# Outcome Contract

## Purpose

User-approved definition of success that is **immutable** for the warmup run
and for the subsequent long-run handoff.

## Schema (required fields)

| Field | Meaning |
|-------|---------|
| Intended result | Observable end state |
| In scope | Must-have deliverables |
| Out of scope | Explicit exclusions |
| Acceptance signals | How the user judges success (commands, artifacts, behaviors) |
| Constraints | Budget, deadline, platforms, quality/security |
| Allowed substitutions | Only explicitly approved alternatives |
| Decision owner | Always `user` |

## Approval gate

1. Present the full contract markdown.
2. Require `ask_user` with options: **approve** / **edit** / **abort**.
   Free-form inference is not approval.
3. On edit: revise and re-approve before planning.
4. On abort: stop; no plan, no preflight.

## Immutability

After approval:

- Planner, review, and preflight may add risks, evidence, questions, alternatives.
- They **must not** redefine intended result, remove a must-have, or silently
  substitute an approach not in Allowed substitutions.
- Any proposed outcome/scope change → classify `outcome-change-request` and
  enter **Decision required**.

## Storage (v1)

- Carry in session context and Ready handoff packet only.
- Do not write untracked project files solely to hold the contract.
- Never embed secret values; redact if user pastes credentials.

## Abbreviated interview

When the user already supplies a complete contract-like brief, still:

1. Restate it in the schema above.
2. Require explicit approval.
3. Skip only the exploratory interview questions that no longer change the reframing.
