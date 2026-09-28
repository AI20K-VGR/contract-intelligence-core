# Verify before done — end-of-phase verification

This drawer describes the final verification step of a phase before cook advances to the next phase or writes an artifact. Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`, `"${HARNESS_BIN_ROOT:-.}"/harness/hooks/gate_stage.py`, `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/artifact_check.py`.

## 5 invariants (from verification-mechanism.md)

1. **Anchored**: every claim must be accompanied by a commit SHA, `file:line`, or real command output.
2. **Downstream rejects UNVERIFIABLE**: the next step does not build on unanchored claims.
3. **Artifact is the source**: verdict is written to machine-written JSON, not stated verbally.
4. **Self-report does not self-approve**: gate reads artifact + verdict policy.
5. **Trace records steps**: significant steps emit via `"${HARNESS_BIN_ROOT:-.}"/harness/hooks/trace_log.py`.

## End-of-phase checklist

Before writing `verification.json` and advancing the phase:

- [ ] Full suite green (`python3 -m pytest harness/tests/ -q`) — or, under the plan's
  `defer_suite: true`, the current phase's declared test files only (the full suite
  still owes ONE run before `cook close` —
  `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/cook/references/deferred-suite.md`)
- [ ] No new lint/type/build errors
- [ ] Every acceptance criterion in the phase file has evidence (file:line or command output)
- [ ] **When the phase was delegated to `@developer`**: main re-read the subagent's test — it was RED before the implementation (fails on a broken/blank impl, not tautological) and covers each acceptance criterion — and reviewed the code, before trusting the green suite
- [ ] No regression in shared touchpoints: walk each caller of a changed function and any module sharing a file/contract with the change
- [ ] Public contract (signature, schema, env var) unchanged — or reason for change clearly documented
- [ ] `verification.json` written per schema `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json`, carrying `phase: <P-id>` (the matching `plan-graph.yaml` node) so the per-phase evidence snapshot drives safe auto-close —
  prefer `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/write_verification.py <plan_dir> --phase <id> --stage <stage> --verdict <V> --check <type>:PASS ...`, which writes the canonical verification, snapshots it,
  and runs the lifecycle in one deterministic step (works from Bash, where the PostToolUse hook would not fire)

## Side-effect check

When a regression or contract break is detected: STOP, ask AskUserQuestion with:
- What is affected (file, test, workflow)
- One-line cause
- 2-4 specific action choices

Do not silently self-patch regressions. Do not advance a phase while any UNVERIFIABLE claim exists.

## Gate wiring

`"${HARNESS_BIN_ROOT:-.}"/harness/hooks/gate_stage.py` (PreToolUse Bash, advisory, exit 0) reads `verification.json` from the filesystem before the next stage. `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/artifact_check.py` is a helper for schema validation. Missing artifact → gate advises + prints the file creation path (command still proceeds; presence enforcement lives in remote CI).
