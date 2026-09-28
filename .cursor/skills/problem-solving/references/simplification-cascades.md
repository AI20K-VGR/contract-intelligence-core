# simplification-cascades — simplification chains

Find a single insight that eliminates many components at once. "If this is true, we no longer need X, Y, or Z."

## Core principle

**Everything is a special case of a general pattern** — recognizing that pattern collapses accumulated complexity.

One strong abstraction beats ten clever hacks.

## When to use

| Symptom | Action |
|---|---|
| Same thing implemented 5+ ways | Find the common pattern |
| List of special cases keeps growing | Find the general case with no exceptions |
| Complex rule with many exceptions | Find the rule with no exceptions |
| Config file ballooning | Find the default that covers 95% of cases |

## Process

1. **List the variants** — what is being implemented in multiple ways?
2. **Find the essence** — what is the same beneath all the variants?
3. **Extract the abstraction** — what is the domain-independent pattern?
4. **Test the fit** — do all cases fit cleanly into the abstraction?
5. **Measure the cascade** — how many things become unnecessary?

## Harness-relevant example

**Before:** Separate validation for hook output, script output, and gate output
**Insight:** "All of these are structured events with actor + ts + payload"
**After:** One shared event schema (`harness/schemas/`) — 3 separate validators removed
**Cascade:** Duplicate code eliminated, trace log standardized

## Red flags — missing a cascade

- "Just need to add one more case..." (repeating endlessly)
- "This is similar but different" (may actually be the same thing)
- Whack-a-mole refactoring (fix here, break there)
- "Don't touch it, it's complicated" (complexity is hiding the pattern)

## Success metrics

- Measured by "how much was deleted?"
- Lines of code removed > lines added
- Special cases unified, not added
- Config options reduced, not increased
