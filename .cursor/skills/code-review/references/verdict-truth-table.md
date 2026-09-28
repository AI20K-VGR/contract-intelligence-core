# Verdict truth-table — per-finding

Pin every verdict/severity label to an existing scale — see
`"${HARNESS_BIN_ROOT:-.}"/harness/rules/scoring-rigor-contract.md` (routed from `code-review/SKILL.md` step 5;
this reference is context only, the required route-existence citation lives in the
SKILL.md body).

Every finding gets exactly one verdict. The verdict is **binary by construction**: a finding is `confirmed` only when *every* condition below is TRUE — **any single condition FALSE ⇒ `dismissed`** (or `needs-human` when a human judgment is required to decide).

| Verdict | Meaning |
|---|---|
| `confirmed` | a real defect; all conditions below TRUE; `code_evidence` pasted |
| `dismissed` | at least one condition is FALSE — not actionable as written |
| `needs-human` | cannot be decided mechanically (business judgment, intended trade-off, ambiguous spec) — escalate, do not guess |

## Conditions (all must be TRUE for `confirmed`)

| Condition | If FALSE |
|---|---|
| **code_evidence present** — the exact `file:line` + snippet the finding points at is pasted | `dismissed` (a claim without evidence is not a finding) |
| **reproducible** — the failure mode actually follows from the cited code, not a guess | `dismissed` |
| **in-scope** — the finding is about the diff under review, not pre-existing unrelated code | `dismissed` |
| **not already addressed** — the diff does not already handle it | `dismissed` |
| **decidable without business judgment** — correctness, not a product trade-off | `needs-human` |

## `code_evidence` is mandatory

A `confirmed` finding **must** carry `code_evidence`: the literal snippet at the cited `file:line`. Evidence is never translated and never paraphrased — it is quoted. A finding that cannot paste its evidence is `dismissed` by the first condition above.

## Before finalizing — check the dismissals store

Before recording a `dismissed` verdict (and when re-encountering a finding), compute its fingerprint and `lookup` the per-repo dismissals store (`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/dismissals_store.py`,
`docs/review/dismissals.jsonl`). If a prior dismissal matches, **SHOW** it to the reviewer ("dismissed before — reason: …") — the store never auto-hides a finding. A genuinely-reintroduced bug still surfaces; the
reviewer decides with the prior context visible.
