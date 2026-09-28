# TDD discipline — shared rules for cook + test (always reference)

## Red -> green, non-negotiable

1. **Test first**: write the test for new or locked behavior, run it to **intentional
   FAIL** (wrong assert / ImportError) — do NOT skip, do NOT fake green.
   That red run LEAVES A TRACE: `track_script_execution` logs each pytest invocation
   under `pytest:<target>` with its exit code, and `hook_runtime.had_red_before_green`
   answers per target whether a failing invocation preceded a passing one. A floor, not
   an authentication — a determined faker can break something first — but the honest
   path leaves evidence and the skipped path leaves a visible hole.
2. **Implement to green**: write the minimum code to make the test pass.
3. **Run the full suite**: `python3 -m pytest harness/tests/ -q` (or the target repo's
   suite per standards) — not just the test just written. Exception: inside `hs:cook`
   driving a plan whose frontmatter carries `defer_suite: true`, this step scopes to
   the current phase's declared test files instead — the full suite still runs once,
   before `cook close` (`"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/cook/references/deferred-suite.md`).
   Every other caller of this step — a standalone `hs:test` run (no plan to read a flag
   from), a plan without the flag, or `hs:fix`/`hs:plan` reaching this same rule — has
   no `defer_suite` to condition on, so the full suite above stays the unconditional
   default.
4. **Commit the pair** test+module, conventional commit, no AI reference.

## 100% pass is a gate

- Fail means fix the **code**, or fix a **genuinely wrong test** (state the reason
  explicitly). Do not delete/skip/weaken a test to reach green. "Fix regressions, not
  the test."
- Reports must be honest: list **every** test failure (name + one-line reason); final
  verdict is PASS / PASS_WITH_RISK (state the risk) / BLOCKED.
- Verdict + checks[] are written to `verification.json` (schema
  `harness/schemas/artifact-verification.json`) — this is the hard input for the gate
  stage. See `verification-mechanism.md` for evidence rules.
