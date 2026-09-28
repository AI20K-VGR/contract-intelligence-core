# inversion-exercise — inverting assumptions

Invert core assumptions to expose hidden constraints and alternative approaches. "What if the opposite were true?"

## Core principle

**Inversion reveals hidden assumptions.** Sometimes the opposite is the answer — or at least it shows why the current approach is context-dependent.

## When to use

| Symptom | Action |
|---|---|
| "There is only one way to do this" | Invert that assumption |
| Solution feels forced | Invert the constraint |
| Cannot explain why it must be done this way | Question the "must" |
| "This is the standard approach" | Try the opposite |

## Process

1. **List core assumptions** — which "musts" are being treated as obvious?
2. **Invert each one systematically** — "What if the opposite were true?"
3. **Explore the consequences** — how would things be done differently?
4. **Find valid inversions** — which ones actually work somewhere?
5. **Record the insights** — what was learned?

## Common inversions

| Standard assumption | Inverted | Reveals |
|---|---|---|
| Cache to reduce latency | Add latency to enable caching | Debouncing patterns |
| Pull data when needed | Push data before it is needed | Prefetching, eager loading |
| Handle errors when they occur | Make errors impossible to occur | Type systems, contracts |
| Add features users want | Remove features users do not need | Simplicity > addition |
| Validate after receiving | Validate before receiving | Schema-first design |

## Distinguishing valid from invalid inversions

**Valid:** The inversion works in at least one context.
- "Store data in DB" -> "Derive on-demand instead" — valid when computation is cheaper than storage

**Invalid:** The inversion does not work in any real context.
- "Validate user input" -> "Trust all user input" — invalid (security hole)

**Test:** Does the inversion work in ANY context? If yes, it is valid somewhere.

## Harness-relevant example

**Assumption:** "The gate must block at the end of the pipeline (pre-push)"
**Inverted:** "The gate blocks at the start of the pipeline (pre-tool-call / preflight)"
**Valid because:** Fail-fast is better than fail-late — `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/preflight_deps.py` embodies this pattern, blocking early instead of waiting until ship

**Insight:** The harness already applied this inversion — preflight is an "inverted gate"

## Notes

- Not every inversion works — test the boundaries
- Valid inversions reveal the context-dependence of the "rule"
- Record both successful and failed inversions
- Question "must be" statements — many are assumed, not real
