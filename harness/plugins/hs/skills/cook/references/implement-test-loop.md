# Implement-test loop — conformance checklist + verify-after-file

Supplemental drawer for per-phase-tdd.md. Load when the order of checks before/after writing code in a phase needs reminding.

## Conformance checklist (BEFORE writing code)

1. Read `docs/code-standards.md` — confirm naming, file structure, and error-handling match current standards.
2. Scout neighboring code in the files to be modified — follow the same import, logging, and error-wrapping style.
3. Look for existing helpers before creating a new utility — maintain DRY.
4. Check the interface contract — new code extends the existing surface, does not create a parallel one. Use `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/check_standards.py` when available.
5. Cross-check the phase checklist — every file in the phase inventory is addressed.

Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/check_standards.py`, `"${HARNESS_BIN_ROOT:-.}"/harness/rules/harness-contract.md`.

## Verify-after-file (AFTER each file is modified)

- **Compile/type-check**: run the command appropriate for the project stack.
- **Pattern verify**: new code matches neighboring conventions.
- **Import check**: no circular dependency, no dead import.

## Test loop (repeat until green)

```
write test → FAIL? → implement → run suite → FAIL? → fix code → run suite → PASS → paired commit
```

Forbidden: deleting tests, skipping, or weakening assertions to go green.
Forbidden: committing while tests are red without a clearly recorded reason.

Final verdict written to `verification.json` (schema `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json`). Gate `"${HARNESS_BIN_ROOT:-.}"/harness/hooks/gate_stage.py` reads this artifact — missing → advisory, exit 0 (command proceeds; presence enforcement lives in remote CI).
