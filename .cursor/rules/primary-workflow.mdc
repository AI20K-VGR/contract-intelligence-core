# Primary workflow

Load this when a task needs an implementation workflow beyond a direct answer and no
specific SDLC skill has been invoked yet. It is the default entry router; the SDLC skills
(`hs:plan`, `hs:cook`, `hs:test`, `hs:code-review`, `hs:ship`) own the detailed steps.

## 1. Understand

- Read the request, relevant docs, and nearby code before planning.
- Clarify only decisions that cannot be discovered from the repo (scout first).
- For broad or risky work, route to `hs:plan` and create/update a plan in `plans/`.
- For an ambiguous step sequence, load `hs:cook`'s own step reference (its `references/`
  index names the current one; the file has been renamed once already).

## 2. Implement

- Change existing files when that matches the design; create new files only for real boundaries.
- Keep behavior compatible unless the accepted scope says otherwise.
- Prefer local helpers, conventions, and test utilities over new abstractions (YAGNI, KISS, DRY).
  Before writing new code, walk the **minimal implementation ladder** — take the first rung that fits:
  1. **Delete** — can existing code, config, or a doc note remove the need entirely?
  2. **Standard library** — does the language's standard library already cover it?
  3. **Existing** dependency or in-repo utility — does something already do this?
  4. **Tiny** change — is a one- or few-line edit to existing code enough?
  5. **Shrink** — write the minimal version that satisfies the contract.
  The ladder trims accidental complexity only. **Do not cut** required scope, trust boundaries,
  data-loss protection, security, a11y, observability, or error handling to descend a rung.
  A seam, extension point, or explicit contract that the approved plan asked for is REQUIRED
  scope, not speculation — descending a rung by dropping it is cutting scope, and the call to
  build it belonged to `hs:plan`. Re-open it there rather than shrinking it away here.
- For bugs, prove the cause before changing behavior (route to `hs:debug`).
- Drive multi-phase work through `hs:cook` so each phase records its verification artifact.

## 3. Verify

- Run focused tests for touched behavior.
- Broaden to lint, typecheck, build, or integration tests when shared contracts changed.
- Fix regressions instead of weakening tests or gates.

## 4. Review and explain

- Use `hs:code-review` for high-risk, cross-module, or public-contract changes.
- Update docs only when user-facing behavior, workflows, commands, or architecture changed.
- Explain the result plainly; reach for `/hs:preview` only for complex workflows or architecture.

The hard stages (`push|pr|ship|deploy`) all reach the presence gate
(`harness/hooks/gate_stage.py`); this rule routes, it does not replace the gate.
Personal-first since `fd607c15`: a missing receipt there is advisory locally and
enforced in remote CI (`receipts-gate`). The one hard local block is the
artifact-forgery arm.

Related: `harness/rules/agent-operational-discipline.md` — think before every
action, never discard output you might need, validate locally before remote.
