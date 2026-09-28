# Verify and gate — pre-ship checklist

Used at Step 6. Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/hooks/gate_stage.py` + schema `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json`.

## How the gate works

`harness/hooks/gate_stage.py` reads `verification.json` at stage `push|pr|ship|deploy`. If the file is missing, any check is non-PASS/SKIP, or `verdict == BLOCKED` → gate **blocks** (exit 2, fail-closed). PASS_WITH_RISK passes verification; only review-decision / critique-consensus require exact PASS. The gate is a **presence gate**: it proves the step ran, not who ran it.
Details: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`.

## Pre-done checklist

```
□ Original symptom no longer reproduces (re-run exact repro from Step 2)?
□ New (regression) test is GREEN?
□ Full suite GREEN: python3 -m pytest harness/tests/ -q?
□ No new lint/type/build errors?
□ Public contract unchanged (signatures, schema, env vars) — or changed intentionally and clearly noted?
□ Blast radius sweep: tests for dependent modules pass?
□ verification.json fully written (stage, actor, ts, checks[], verdict: PASS/PASS_WITH_RISK)?
□ code-reviewer agent reviewed and flagged no blockers?
```

## Side-effect sweep

Before gate, sweep the full blast radius:

```bash
# Run tests for affected module + transitively affected modules
python3 -m pytest harness/tests/ -q -k "<relevant keyword>"

# Compare with baseline captured at Step 2
# If new red tests appear → STOP, report to user (see minimal-fix-discipline.md)
```

## When the gate blocks

The gate prints a specific reason (missing artifact / verdict BLOCKED). Debug checklist:

1. Does `verification.json` exist? (`ls harness/data/` or the path the schema specifies)
2. Is the `verdict` field `PASS` or `PASS_WITH_RISK` (not `BLOCKED`)?
3. Do all `checks[]` have a `"status"` of PASS or SKIP?
4. Was the file written by a valid `actor` (not hardcoded; use `resolve_actor()`)?

Fix each missing point and re-run — do not bypass the gate.

## After the gate passes

1. Ask user whether to commit: spawn `@git-manager` agent, conventional commit, no AI reference in the commit message.
2. If a plan is active → update plan status (hs:plan artifact).
3. If behavior/docs changed → spawn `@docs-manager` agent to update `docs/`.
4. Report final summary: root cause, files modified (absolute paths), tests added, gate verdict, side-effect sweep result.

## Final report format

```
Root cause: <file:line> — <1-line description>
Files modified: <list of absolute paths>
Tests added: <test name + file>
Suite: PASS (<N> passed, <M> warnings)
Blast radius sweep: PASS (<modules checked>)
Gate verdict: PASS
```
