# Probe catalog

How to build and run each contract-validation probe **safely**. Read this before constructing any command. The safety model: a probe is a skill-layer tool you run deliberately, never a gate.

## Safety model — how a command is built (R6, read this first)

This file is markdown an agent reads then **builds a command from** — one indirection from injection: plan/spec text is AI-authored, untrusted.

- The command you run **must be reviewed by the human or agent before it hits the shell**, exactly like every other Bash tool call. Never let a command string flow straight from unreviewed plan/spec text into `sh -c`.
- The structural test `test_contract_validation_not_in_stage_requires` proves only that the probe is **not gate-driven** (not in any stage `requires:`). It does **NOT** prove the AI-text→shell injection path is closed. Don't read it as injection coverage — review-before-run discipline closes that.
- A probe **inherits** the permissions of the tool-execution context. It never escalates and never fetches outside credentials.

## API probe (v1 — built)

Call a real HTTP endpoint and assert its contract: status code + payload fields.

- Build the request (method, URL, headers, body) from **reviewed** values — not pasted verbatim from generated spec text.
- Run it (`curl`/`httpx`), capture status + body, assert the expected status and the payload fields that define the contract.
- Record the outcome as a `manual` check (`evidence_tier: anchored`) — see the anchor convention below.

## CLI probe (v1 — built)

Run a target command and assert its contract: exit code + stdout/stderr pattern.

- Reviewed before it runs (same rule as Bash tool calls). Never interpolate unreviewed text into a shell string.
- Capture exit code + output, assert the expected exit code and the output pattern.
- Record as a `manual` check.

## Browser probe (stub — v2)

Validate a page through a real browser. **Not wired in v1** — Playwright + headless display (xvfb) are heavy. v2 reuses `hs:web-testing` (Playwright, already reaching live). Still inherits context permissions; never gate-driven.

## DB probe (stub — v2)

Validate a real query result. **Not wired in v1** — needs live database credentials; a probe never fetches outside credentials. v2 reuses `hs:manual-test` admissibility for the real query, running with the context's permissions.

## Anchor convention — ride the `manual` tier

Every probe records its result as the `manual` check `hs:manual-test` already defines: the manual-test hook witnesses the Bash run and emits an anchor id; cite it in verification.json as `anchor_id` with `evidence_tier: anchored`. The DoD gate (`artifact_check.evaluate_test_policy`) cross-checks the anchor and **reads** it — it never re-runs the probe. No new admissibility tier
(reuse, not reinvent).

Write it via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/write_verification.py <plan_dir> --from -`, piping a composed record whose `checks[]` entry carries `anchor_id`/`evidence_tier` (Bash — no Write tool needed; matches this skill's `allowed-tools`).
The flag-builder mode (`--check name:status`) has no field for `anchor_id`/`evidence_tier`, so use `--from` instead. A raw Bash-redirect write skips the same producer hook manual-test's own evidence relies on.
