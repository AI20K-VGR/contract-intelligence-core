# hypothesis-loop — hypothesis to evidence loop

Load when: Phase 1 is complete (evidence in hand) and hypotheses need testing before a fix.

## Principles

Test only **one hypothesis** and **one variable** at a time. Multiple simultaneous changes mean you cannot tell what caused the result — you must start over.

## Tracing back up the call stack

When the failure is deep in the call chain:

1. Identify where failure appears (symptom).
2. Ask: "What calls this function?" — trace up one level.
3. Continue tracing up until you find where bad value originates.
4. Add instrumentation if can't trace manually (see `instrumentation.md`).

**Core principle:** Do NOT fix at the site where the failure appears. Fix at the source.

## Loop procedure

```
State a specific hypothesis
    ↓
Test with the smallest possible change
    ↓
Read actual output — do not guess
    ↓
Confirmed → Phase 4 (failing test + root cause)
Eliminated → state a new hypothesis (do not stack fixes)
    ↓
After ≥ 3 hypotheses fail → STOP, reconsider the architecture
```

## Hypothesis format

> "X is the cause BECAUSE Y, provable by Z."

Not acceptable: "It might be X." — missing evidence link.

## When ≥ 3 hypotheses fail

Three consecutive failures typically signal an architectural problem:
- Each fix exposes new shared state/coupling elsewhere.
- STOP — ask the user, consider `hs:brainstorm` to revisit design.
- Do NOT add a fourth fix without discussion.

## Red flags in the loop

- "Let me try this and see" → hypothesis lacks an evidence link.
- "Fix 2 things at once to go faster" → eliminates the ability to measure anything.
- "Probably passes, no need to run the test" → you must run it and read the actual output.
