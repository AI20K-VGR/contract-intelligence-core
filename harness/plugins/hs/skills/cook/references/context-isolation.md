# Context isolation — cook from a clean context

Details for the "Context isolation" section in SKILL.md.
Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` #5, `"${HARNESS_BIN_ROOT:-.}"/harness/hooks/cook_isolation_nudge.py`.

## Why

Planning carryover (research, red-team, debate) accumulates in context and shifts cook's focus — the agent can get pulled into old reasoning instead of executing the plan.

## Recommended procedure

```
hs:plan → human approves → /clear → /hs:cook <absolute-path>
```

hs:plan returns an **absolute path** so the next session can find the plan after `/clear`.

## Nudge (advisory, does not block)

`"${HARNESS_BIN_ROOT:-.}"/harness/hooks/cook_isolation_nudge.py` detects plan + cook in the same session → prints a `/clear` suggestion. The hook is telemetry fail-open: silent on error, does not block cook.

## Accepted exceptions

- Cook running in CI / AFK (no human interaction): skip `/clear`.
- Very small plan (< 1 phase, no prior research): user decides.
- User explicitly waives isolation: cook continues without asking again.

This is a recommendation, not a gate — `gate_stage.py` does not check this condition.
