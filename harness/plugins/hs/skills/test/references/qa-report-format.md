# QA report format (on-demand)

Load when: generating a QA report after running the suite.

Rules: under 200 lines; list **ALL** failures — do not summarize away names; sacrifice grammar for concision.

## Template

```markdown
# QA Report — {date} — {scope / plan}

## Summary
- **Total**: X tests | **Pass**: X | **Fail**: X | **Skip**: X
- **Time**: Xs

## Coverage
| Metric   | Value | Threshold | Status     |
|----------|-------|-----------|------------|
| Lines    | X%    | 80%       | PASS/FAIL  |
| Branches | X%    | 70%       | PASS/FAIL  |
| Functions| X%    | 80%       | PASS/FAIL  |

Specific gaps (if any): `file:function` — percentage alone is not sufficient.

## Test failures (list all)

### `harness/tests/path/test_module.py::TestClass::test_name`
- **Error**: <short message>
- **Root cause**: <1 line>
- **Suggested fix**: <specific action>

## Items to watch
1. <risk / flaky / slow — record PASS_WITH_RISK if not blocking>

## Verdict

`PASS` | `PASS_WITH_RISK` | `BLOCKED`

> PASS_WITH_RISK: state the specific risk + file/function.
> BLOCKED: list the FAIL checks that block the hard stage.
```

## Accompanying artifact

After the report is complete → write `verification.json` (schema `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json`, rule `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`).
Details: `references/verification-artifact.md`.

## Saving the report

Use the naming pattern injected by hooks (timestamp + scope in the filename). Save to `plans/<plan>/reports/` or `plans/reports/` if no plan is active.
