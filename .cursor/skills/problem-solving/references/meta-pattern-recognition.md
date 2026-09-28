# meta-pattern-recognition — recognizing meta-patterns

Identify a pattern in 3+ domains to find a reusable universal principle.

## Core principle

**Find the pattern in how patterns appear.** When the same shape appears in 3+ independent domains, it's universal — extract and reuse it.

## When to use

| Symptom | Action |
|---|---|
| Same problem in many places | Extract the abstract form |
| Deja vu when solving | Find the universal pattern |
| Reinventing wheels across domains | Recognize the meta-pattern |
| "We have done something like this before" | Yes — find it and reuse it |

## Process

1. **Detect repetition** — same shape in 3+ places
2. **Extract the abstract form** — describe it independently of any specific domain
3. **Identify variation points** — how does the pattern adapt across domains?
4. **Check applicability** — where else could it be beneficial?
5. **Document the pattern** — make it reusable

## The 3+ domain rule

- 1 occurrence = coincidence
- 2 occurrences = possibly a pattern
- 3+ occurrences = likely universal

**Domain-independence test:** Can the pattern be described without naming any specific domain?

## Harness-relevant example

**Pattern detected:** The same structure "check -> verdict -> downstream rejection" appears in:
- `gate_stage.py`: check artifact -> pass/fail -> block stage
- `artifact_review_decision.json`: review -> verdict -> cook rejects continuation
- `verification-mechanism.md`: claim -> anchor evidence -> next step rejects an unanchored (ASSUMED) claim

**Abstract form:** `check(input) -> verdict -> downstream_policy(verdict)`

**Variation points:** input type, verdict schema, policy action
**New applications:** Any new gate in the harness follows the same shape

## Red flags — missing a meta-pattern

- "This problem is unique" (likely not)
- Multiple teams solving "different problems" in exactly the same way
- Reinventing wheels across domains
- "We did something like this before" (correct — find it)

## Benefits

- **Battle-tested** — proven across multiple domains
- **Reusable** — applicable to new situations
- **Domain-independent** — a universal solution
- **Documented variations** — known adaptation points
