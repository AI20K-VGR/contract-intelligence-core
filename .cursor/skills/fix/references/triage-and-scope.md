# Triage and scope definition

Used at Step 2 (Diagnose). Goal: prove the root cause BEFORE touching code.

## 6 required questions (answer fully, no vagueness)

1. **Exact symptom**: copy-paste the actual error/output — no paraphrasing.
2. **Reproduction steps**: the minimal command to trigger the failure.
3. **Expected vs actual**: the correct behavior vs what is happening.
4. **Root cause at `file:line`**: the specific defect (missing check, bad logic, contract violation).
5. **Why now**: the change or condition that exposed it — recent commit, data shape, env, or dep upgrade.
6. **Blast radius**: every code path that depends on the broken behavior.

Any answer that is vague ("probably", "I think") → `AskUserQuestion` or scout further. Do not propose a fix until all 6 questions are answered.

## Collect baseline (required before any change)

```bash
# Capture state before
python3 -m pytest harness/tests/ -q 2>&1 | head -50   # or target repo runner
git log --oneline -20                                   # which recent commit is the cause?
```

Save this output — Step 4 uses it for before/after comparison.

## Blast radius classification

| Type | Description | Action |
|------|-------------|--------|
| Narrow | 1 file, no external callers | Quick mode is sufficient |
| Medium | 2-5 files, related tests exist | Standard mode |
| Wide | Multiple modules, public contract | Deep mode + full code-reviewer sweep |

## Hypothesis chain (when cause is unclear)

For each hypothesis:
1. State the hypothesis clearly.
2. What evidence would CONFIRM it?
3. What evidence would REFUTE it?
4. What is the fastest test?

Use the `@debugger` agent to run hypotheses in parallel (max 3 agents per round). If 2+ hypotheses fail → escalate to `deep`, ask user before continuing.

## Trace chain (from symptom to root)

```
Symptom (where the failure appears)
  ↑ Immediate cause (what triggers the failure)
    ↑ Contributing factor (conditions that led to it)
      ↑ ROOT CAUSE (fix must happen here)
```

Never fix at the failure site — trace back to the root.
