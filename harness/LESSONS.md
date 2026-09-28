# Lessons learned

Agent-level, machine-readable capture of past failures so they are not repeated.
Each entry follows the same shape: **what failed and why -> which test or code
caught it (or should have) -> the rule that prevents it next time.** This is a
preflight input: read it before `hs:understand` and `hs:plan` so a known
failure mode shapes the approach instead of being rediscovered.

## How to use this file

- Read it at the start of comprehension and planning. A relevant past lesson is
  cheaper than re-living the failure.
- After any correction — a bug you fixed, missing wiring you added, a pattern you
  got wrong, anything the user had to point out — add the pattern here. Do not
  wait to be asked.
- Keep entries short and concrete. Name the test or check that catches the
  failure so the lesson is verifiable, not folklore.

## Entry template

```
## <one-line title: the failure, not the fix>

<2-4 sentences: what happened, the root cause, the concrete instance.>

Rules:

1. <the rule that prevents recurrence>
2. <the test / check / code path that catches it>
```

---
