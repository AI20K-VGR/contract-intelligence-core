# Regression test — red→green procedure

Used at Step 4. Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md` + schema `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json`.

## Invariant rules

1. **Test BEFORE fix** (or confirm an existing test fails at the right point).
2. Run test → must be **RED** (intentional failure — no skipping, no fake green).
3. Apply fix → re-run → must be **GREEN**.
4. Run the **full suite**: `python3 -m pytest harness/tests/ -q` (or the target repo runner).
5. **Deleting/skipping/weakening tests** to go green is forbidden. "Fix regressions, not the test."

## Writing a regression test

The test must:
- Reproduce the exact bug (using the baseline captured at Step 2).
- Fail without the fix, pass with the fix — provable causal link.
- Be placed in the existing test module (do not create a standalone test file if a suitable location exists).
- Name the behavior being locked, not the implementation.

```python
# Pattern example — name describes behavior, not code
def test_<specific_behavior>_when_<condition>():
    # arrange: reproduce conditions that caused the bug
    # act: call the fixed code
    # assert: correct result (expected behavior)
```

## Run and confirm

```bash
# Step 4a — run new test BEFORE fix (must be RED)
python3 -m pytest harness/tests/path/to/test_file.py::test_name -v

# Step 4b — apply fix, re-run (must be GREEN)
python3 -m pytest harness/tests/path/to/test_file.py::test_name -v

# Step 4c — full suite (all must pass)
python3 -m pytest harness/tests/ -q
```

## Write verification.json

After the full suite is green, write `verification.json` per schema
`"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json`. Write it through
`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/write_verification.py <plan-dir> ...`
rather than by hand — it
resolves the canonical path under `<plan-dir>/artifacts/` and stamps the fields
the gate reads.

A plan dir is REQUIRED, not optional. The schema lists `plan` under `required`
and types it `string`, and `write_verification.py` takes it as a mandatory
positional; there is no plan-less write path. A fix that has to clear the push
gate opens a minimal plan first. (This example carried `"<plan-path or null>"`
until the schema was read against it — a null there fails validation.)

```json
{
  "stage": "fix",
  "plan": "<plan-dir name>",
  "actor": "<resolve_actor()>",
  "ts": "<ISO timestamp>",
  "checks": [
    { "name": "regression-test", "status": "PASS", "detail": "pytest ..." },
    { "name": "full-suite", "status": "PASS", "detail": "pytest harness/tests/ -q" }
  ],
  "verdict": "PASS"
}
```

`verdict` is `PASS` only when **all** checks pass. Verdict BLOCKED → `harness/hooks/gate_stage.py` blocks push/ship.

## When no test framework exists

- Add an inline assertion at the affected site.
- Record in `verification.json` checks[] with `"status": "SKIP"` and a note explaining why.
- Clearly state in the summary: "No test framework — added runtime assertion at `file:line`."

## Defense in depth — fix the class, not just this bug

A regression test proves THIS instance is dead. Before declaring done, ask whether a guard at a higher layer stops the whole class from recurring — not every fix needs all, but always consider each:

| Layer | Apply when | Example |
|---|---|---|
| Entry-point validation | the fix involves external/user input | reject the bad input at the boundary, not deep in the call stack |
| Logic-level assertion | the fix involves data transformation | assert the invariant holds where the data is produced |
| Environment guard | the fix involves an env-sensitive operation | refuse the dangerous op in the wrong context (cf. `bash_safety_guard`) |
| Diagnostic instrumentation | the bug was hard to diagnose | capture the context that would have made it obvious |

A single targeted guard often retires a recurring bug class more cheaply than N future one-off fixes. Keep it minimal — one guard at the right layer, not four redundant ones.
