---
name: spec-compliance
description: Stage 1 spec-compliance for the --spec flag — compare implementation against plan/spec artifact before quality review
---

# Spec compliance (Stage 1)

Drawer for the `--spec <plan>` flag. When the flag is active, `hs:code-review` runs Stage 1 BEFORE the Stage 2 quality review: it compares the actual code against the *approved intent* in the plan/spec. Stage 1 asks "does the code do the right thing?"; Stage 2 asks "is the code written well?". A cleanly written implementation that drifts from the spec still FAILs Stage 1.

Stage 1 FAIL → fix → re-review Stage 1 until PASS → then continue to Stage 2. Do not skip Stage 1 to do a "quick" quality review.

---

## What to load

`<plan>` points to the active plan directory. Read in order:

1. `plans/<plan>/plan.md` — status, phase list, acceptance criteria, scope
2. `plans/<plan>/phase-*.md` AND `plans/<plan>/phases/phase-*.md` — requirements, files to modify/create/delete, implementation steps, and validation for each phase under review
3. The diff/changeset under review (from the resolved input mode)

If the plan does not exist or lacks acceptance criteria → clearly state there is insufficient basis for a spec-check, ask the user, do NOT invent criteria.

---

## What to compare

Cross-reference **plan vs code** on these axes:

| Axis | Question | FAIL when |
|---|---|---|
| Scope | Do the changed files match the plan's "files to modify/create/delete"? | Code touches out-of-scope files without explanation, or omits files the plan requires |
| Acceptance criteria | Does each criterion in the plan have corresponding code/test? | Criterion has no implementation, or only a partial one |
| Behavior | Does the code's behavior match what the phase requirement describes? | Logic differs from what the plan describes (wrong contract, wrong flow) |
| Public contract | Does the interface/schema/config match the shape the plan locked? | Contract drifts from the plan without user acceptance |
| Phase order | Do steps follow the dependency order the plan specifies? | A later phase is implemented before its dependency phase is complete |
| Test mapping | Is each acceptance criterion proven by a test? | Criterion is claimed "done" but no test covers it |

Each finding records: which criterion/requirement · actual code `file:line` · expected (per plan) vs actual (per code) · why the deviation matters.

---

## Pass / fail

**PASS Stage 1** when:
- Every acceptance criterion in review scope has an implementation + (where applicable) a test
- No unexplained scope creep
- Public contract matches the plan, or any drift has been explicitly accepted by the user
- No phase dependency is violated

**FAIL Stage 1** when any of:
- A criterion has no implementation or only a partial one
- Behavior deviates from the plan requirement
- Contract drift has not been accepted
- An out-of-scope file is touched without plan authorization

FAIL is not a style issue — it means the code has not done the job it was assigned. Stage 1 FAIL blocks progression to Stage 2; report findings, route to fix, re-check.

---

## Plan drift after approval

If plan.md changed AFTER the code was written (sha mismatch), the spec-check may compare against the wrong version. Compute `plan_hash` (sha256 of the current plan.md) and record it in the verdict artifact — this helps detect cases where the plan was edited after review. If plan drift is suspected, report it clearly rather than silently PASSing against the modified plan.

---

## Relationship to the verdict

Stage 1 does not write its own artifact — it is a prerequisite for entering Stage 2. The final verdict (`review-decision.json`) is written only after both stages are complete (see `references/verdict-and-artifact.md`). If Stage 1 FAIL persists through re-review cycles without converging → escalate to user; do not unilaterally relax the spec.
