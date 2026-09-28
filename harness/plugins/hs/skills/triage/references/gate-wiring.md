# Gate Wiring — Pre-gate artifact checklist, side-effect sweep, review surface

## Backing

Gate: `harness/hooks/gate_stage.py` (presence gate, compliance-class). Personal-first:
a missing receipt is advisory locally and enforced in remote CI (`receipts-gate`);
the forgery arm — a shell write to a receipt path — is the one hard local block.
Verification schema: `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json`.
Review schema: `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-review-decision.json`.
Evidence rule: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`.

The gate is a **presence gate** — it proves a step was run, not who ran it.

## Checklist before the gate allows a stage

### Required for all modes

- [ ] `plans/<plan>/artifacts/verification.json` exists on the filesystem.
- [ ] `verification.json` → `verdict` field = `"PASS"`.
- [ ] `checks[]` lists all of: test suite pass, blast radius sweep, no new regressions.
- [ ] `stage`, `plan`, `actor`, `ts` all have values (not null).

### Additional for severe defects (severity high/critical)

- [ ] `plans/<plan>/artifacts/review-decision.json` exists.
- [ ] `review-decision.json` → `verdict` = `"PASS"`.
- [ ] `hs:code-review` was run with input: modified files + blast radius from scout.

### Gate block — action

When the gate refuses (an actionable reason; `exit 2` only on the forgery arm or
an internal crash):
1. Read the actionable reason from gate output — do not guess.
2. Identify which artifact is missing or which verdict ≠ PASS.
3. Do not edit `harness-hooks.yaml` / `stage-policy.yaml` to pass through — files are tracked in git; any edit is exposed by diff + trace.
4. Genuinely stuck → ask the user via AskUserQuestion.

## Side-effect sweep (before writing verification.json)

Before declaring PASS, check:

| Item | Question |
|---|---|
| Public contract | Did any signatures, schemas, or env vars change? |
| Dependents | Do files in the blast radius have their own tests? Were they run? |
| Regression | Does the full suite pass (`python3 -m pytest harness/tests/ -q`)? |
| Docs | Did behavior change? Does `docs/` need updating? |
| BACKLOG | Was anything discovered outside scope? Recorded via `backlog_register.py add`? |

If any item is unclear → STOP, do not write verdict PASS.

## Review surface (mode standard + severe defects)

When `review-decision.json` is required:

1. Spawn `hs:code-review` with input:
   - Modified files (absolute paths).
   - Blast radius report from `hs:scout`.
   - Diagnosis report from `hs:debug`.
2. Reviewer checks: root cause truly resolved / no regressions / contract preserved.
3. If reviewer flags an issue → AskUserQuestion with 2-4 specific options (do not self-decide).
4. Result written to `review-decision.json` (schema `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-review-decision.json`).

Optional review surface via Plannotator: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/plannotator-review-gates.md` (helper `plannotator_surface.py review <diff>` — fail-open, not required).

## Writing verification.json

After all checks pass:

```json
{
  "stage": "fix",
  "plan": "<plan-id or slug>",
  "actor": "<resolved via harness/hooks/hook_runtime.py resolve_actor()>",
  "ts": "<ISO 8601>",
  "checks": [
    {"name": "test_suite", "status": "PASS", "detail": "pytest -q: 0 failed"},
    {"name": "blast_radius_sweep", "status": "PASS", "detail": "<file:line>"},
    {"name": "regression_suite", "status": "PASS", "detail": "pytest harness/tests/ -q: 0 failed"}
  ],
  "verdict": "PASS"
}
```

`actor` is NOT filled in manually — resolve via `hook_runtime.resolve_actor()`. Emit trace via `"${HARNESS_BIN_ROOT:-.}"/harness/hooks/trace_log.py` (`append_event`) — do not hand-craft JSONL.

## After gate passes

1. Ask the user: commit? (spawn `hs:git`, conventional commit, no AI references).
2. If docs/behavior changed → update `docs/`.
3. If an active plan exists → update the plan status.
4. Final report: root cause (file:line), files modified, tests added, verdict.
