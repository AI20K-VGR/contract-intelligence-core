# Secret lifecycle — 7-stage handling checklist (on-demand)

A `hs:security-scan` review reference. The secret-scan detector (literal-pattern grep +
pre-push hook) catches a secret that is *shaped* like one; this checklist catches how a
secret is *handled* — stored encrypted, scoped tightly, rotated on a schedule, never
logged. It is a review discipline, advisory (personal-first), not an automated detector.

## Trigger conditions

- A diff adds a new secret consumer (env-var prefix, vault path, KMS key reference).
- A diff adds a logger call in a function that has secrets in scope.
- A diff adds a service-to-service credential.
- A plan introduces a new third-party API with authentication (the auth-lifecycle overlap
  with the deep dependency-risk review — cross-referenced in prose, see the skill).

## The 7 lifecycle stages

| Stage | Check | Pass criteria |
|---|---|---|
| **Creation** | Generated, not hand-entered | Created via KMS / vault API; no "paste the API key here" flow |
| **Storage** | Encrypted at rest | sops+age for repo-tracked, vault for runtime; plain env files never |
| **Distribution** | Reaches only the workload that needs it | No blanket env dumps; per-service scope |
| **Use** | Accessed via SDK, not string interpolation | Prevents accidental logging through error messages |
| **Rotation** | Rotation procedure documented and tested | Rotation runbook exists; rotation performed at least once in non-prod |
| **Revocation** | Revocation procedure documented | "If leaked, run X; invalidates in Y seconds" |
| **Logging safety** | Logger wrappers redact known secret fields | Test: logging a struct with a known secret field yields `<REDACTED>` |

## Steps

1. Detect a trigger match.
2. For each new secret consumer, verify all 7 stages.
3. Advisory verdict per stage; a failing stage is a finding with the specific gate named.
   Fold the verdict into `security-scan.json` (Severity-mapped). If a revocation procedure
   is absent, file a blocker work item.

## Anti-patterns

- Env vars passed through argv (visible in `ps`).
- Error messages that include the secret value on a mismatch.
- Secrets in Docker build args (they leak into image history).
- Rotating one secret by writing a new one alongside — the old one is still valid.
- A "temporary" hard-coded secret for local dev that gets committed.

## Examples use placeholders only

Any example in a review references a redacted placeholder (`<REDACTED_API_KEY>`), never a
real value — credential hygiene applies to the review artifact itself.

Adapted from `docs/product/_refs/frankcode-src/qa/methodology/qa/secret-lifecycle.md`; the
off-limits-paths and escalation-on-second-revise references (a different paradigm) are
dropped, and the "block on any gate fail" rule is applied as an advisory review checklist
(local never hard-blocks). The STRIDE information-disclosure parent is in
[`threat-model.md`](threat-model.md). The SaaS-auth overlap with the deep dependency-risk
review is noted here in prose only. Routing this reference into `security-scan/SKILL.md` is
the security-skill integration phase's job — not done here.
