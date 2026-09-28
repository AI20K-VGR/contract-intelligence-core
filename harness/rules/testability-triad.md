# Testability triad (on-demand)

Load when `hs:plan` writes acceptance criteria (write-AC step) — classifies each AC as
one of exactly three testable forms. Term-collision fix: the third branch is named
`invariant`, deliberately NOT `rule` — a prior port used "rule" here and it collided
with the rule-file vocabulary (`harness/rules/*.md`); this rename is intentional, do not
"restore" the old name when porting prose from elsewhere.

## Decision tree — ask in order

1. **Can this be exercised by an automated test that asserts a concrete input/output?**
   Yes -> `test`. No -> continue to question 2.
2. **Is it a property that must hold at all times rather than a single input/output
   pair** (a schema shape, a monotonic count, "never both X and Y")? Yes -> `invariant`.
   No -> continue to question 3.
3. **Does it require a human judgment call an automated check cannot render** (visual
   polish, UX feel, a live external system with no test double)? Yes -> `manual`. No ->
   go back to question 1 — the AC is not yet concrete enough to classify.

### test

An automated test with a concrete assertion (`assert output == expected` for a given
input) — the default branch, prefer it whenever the AC is genuinely a single
input/output pair.

### invariant

A property checked structurally rather than by one example — a schema constraint, a
guard, a count that must never decrease. Universal invariants (hold for every instance,
e.g. "every record has an id") and behavioral invariants (hold across a specific
transition, e.g. "balance never goes negative after a withdrawal") are DIFFERENT
SHAPES — split them into two separate ACs rather than one that conflates both. An
invariant must never be satisfied by SAMPLING a few instances and calling it proven — it
either holds structurally (a schema/type check) or it is not actually an invariant.

### manual

Needs a human in the loop — no automated check exists or is worth building. The manual
branch MUST bind the literal keyword `manual_test_anchor.py` (the manual-test anchor
hook at `harness/hooks/manual_test_anchor.py`) — an AC classified `manual` without that
anchor is invisible to the DoD gate's Lớp B check and silently fails later.

### anti-tautology

A criterion that restates the implementation instead of describing observable behavior
("the function returns what the function computes") is not testable in ANY branch —
push back and ask what OBSERVABLE behavior the user actually cares about.

## Examples

OUT -> IN: "the system must be fast" (untestable — fast compared to what, measured how)
-> IN: "the search endpoint returns results in <200ms p95 under 50 concurrent requests"
(a `test` branch AC with a concrete assertion).
