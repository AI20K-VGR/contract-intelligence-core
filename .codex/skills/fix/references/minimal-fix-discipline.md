# Minimal-fix discipline

Used at Step 3 (Fix). Goal: minimum change, fix the ROOT CAUSE, do not expand scope.

## Core principles

- **Fix the root cause, not the symptom.** Patching the symptom means the bug comes back.
- **Minimum change**: only necessary files; do not touch unrelated code.
- **Follow existing patterns**: find how similar cases are handled in the codebase; be consistent.
- **Do NOT create new abstractions** when not directly required.
- **Do NOT refactor** outside bug scope — refactoring is a separate task with its own plan.

## Anti-patterns (forbidden)

| Anti-pattern | Reason |
|---|---|
| Fix at the failure site rather than at the root | Symptom fix — bug comes back |
| Add a "precautionary" wrapper/helper not explicitly required | YAGNI, increases coupling |
| Fix style/naming in the same change | Noise, makes blast-radius review harder |
| Create a new abstraction to make it "cleaner" | Scope creep, not required |
| Change a public contract (signature, schema, env var) | Silent breaking change |

## Pre-commit checklist

```
□ Only modifying files in the blast radius identified at Step 2?
□ Fix is at the root cause (file:line stated in the diagnosis)?
□ No unrequested abstraction/wrapper added?
□ Public contract (signatures, schema, env vars) unchanged — or intentionally changed and clearly noted?
□ Following existing patterns in the codebase?
```

## Three-strike rule

After 3 fix attempts fail (test still red or new side effects appear):
1. **STOP immediately.**
2. Reframe the architectural question — is there a fundamental design problem?
3. Use `AskUserQuestion` with 2-3 specific options (revert / escalate to mode deep / redesign with hs:brainstorm) — do not decide unilaterally.

## Side-effect sweep (after fix, before review)

Re-run the full blast radius:

```bash
python3 -m pytest harness/tests/ -q          # full suite
# compare output with baseline captured at Step 2
```

If new red tests appear → STOP, report to user per HARD-GATE-NO-SIDE-EFFECTS:
- Which file/test is affected
- Why the fix caused it (one line)
- 2-4 specific options (revert / narrow scope / update dependent / accept with explicit note)
