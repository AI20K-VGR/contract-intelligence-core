---
name: hs:manual-test
injectable: false
description: Run a session-based manual/exploratory test (SBTM charter → session → debrief) and emit anchored, admissible evidence. Use for behavior a static result file cannot capture — exploratory passes, manual API/UX checks, staging smoke. The result must be admissible at a gate.
allowed-tools: [Bash, Read, Write, Grep, Glob, Task]
argument-hint: "[interactive|auto] [charter: what to explore]"
metadata:
  compliance-tier: workflow
---

# hs:manual-test — session-based manual testing with admissible evidence

Manual/exploratory testing that produces evidence a gate can READ — not a prose claim. Follows SBTM: **charter → session → debrief**. The output is admissible only to the floor its evidence earns (see Admissibility); it never overclaims.

## Charter → session → debrief

1. **Charter** — one focused mission for the session (≤ one paragraph): what area, what risk, what "done" looks like. For a HARD gate the charter must be
   **co-signed** by a rostered reviewer distinct from the author (reuse `plan_approval`); without a co-sign the result is soft.
2. **Session** — timeboxed exploration. Run real commands. Arm anchoring so the `manual_test_anchor` hook records each Bash command as a telemetry anchor (the hook witnesses cmd+output; you cite the anchor, not assert it). Two ways to arm, either works:
   - **Env:** `export HARNESS_MANUAL_TEST_SESSION=1`.
   - **Marker (subagent-safe):** `manual_test.arm_session(state_dir, session_id)` drops a session marker under the shared state dir, so anchoring works even without the env var or subagent inheritance.
   For a single deliberate probe without a session, `python3 manual_test.py --anchor --cmd "<command>"` self-executes the command and records a `source:"cli"` anchor from the output IT captured — the caller cannot supply the output, so it cannot anchor a command that never ran.
3. **Debrief** — the PROOF table, written to the verification artifact as a `manual` check (see Evidence).
   Then append one row to the committed discovery ledger:
   `manual_test.append_ledger(plan_dir, {"charter": ..., "story": ..., "anchor_ids": [...], "cosign": ...})`
   writes `plans/<plan>/manual-test-log.md` (committed, shows in the PR diff). The ledger is a DISCOVERY
   marker so a human reading the PR knows a manual test ran — it is NOT a second evidence tier;
   admissibility still rests on the anchor + a distinct co-sign.

## Admissibility — claim TRUTHFULLY (the floor, not forgery-proof)

A telemetry anchor proves *a real command ran and this is its real output* — it kills pure fabrication. It does **not** prove the command tested the right thing (an agent can run a real command against the wrong endpoint and cite a real trace). So:

| Evidence | Admissible at |
|---|---|
| `claimed` (agent-written, no anchor) | soft only |
| `anchored` (anchor id present in the hook telemetry) | soft |
| `anchored` + human charter co-sign **distinct from the author** | **hard** |
| `anchored` with a fabricated anchor id, or no anchor sink at all | rejected |
| `anchored` + a co-sign that **equals the author** (self co-sign) | soft only (not hard) |

Never describe anchored evidence as "forgery-proof". Co-sign = human judgement the machine can't supply; a hard gate needs it from someone OTHER than the author (a self co-sign vouches for one's own work, so it stays soft).

## Evidence — the `manual` check in verification.json

Write the manual result as a check the DoD gate re-reads (it does not trust the status):

```json
{ "name": "manual", "format": "manual", "status": "PASS",
  "evidence_tier": "anchored", "anchor_id": "<from the hook telemetry>",
  "cmd": "<the exact command you ran>",
  "cmd_hash": "<sha256(command)[:16]>", "output_hash": "<sha256(real output)[:16]>",
  "actor": "user:<author>", "charter_cosign": "user:<reviewer, distinct from actor>|null" }
```

Include the raw `cmd` — `verify_portable` needs it (it reads `check["cmd"]`), and a remote reviewer needs to know WHICH command to re-run.

The gate (`artifact_check.evaluate_test_policy`) cross-checks the anchor and the co-sign; a `manual` type is required only when a tier-2 policy or component declares it (opt-in). Details: `references/sbtm.md`.

**`cmd_hash` / `output_hash` are for a HUMAN to recompute, not to raise the tier.** They make the check
*portable*: a reviewer on another machine can run `manual_test.verify_portable(check,
observed_output=<their own re-run output>)` to confirm the record survived transit intact. That is
transport-integrity ONLY — it grants NO tier and the DoD gate never calls it. A self-referential command
(`printf PASS`) recomputes to a matching hash yet proves nothing, so the reviewer must run the REAL command
in the real environment and judge whether it tested the right thing. The floor is unchanged: a fabricated
anchor id — or a citation with no sink at all — is still `rejected`.

## Boundaries

- Manual-test is **opt-in**: it gates nothing unless a policy requires `manual`.
- The contract-validation probe (`hs:contract-test`) rides this `manual` check and the same admissibility — adds no new tier; one way to generate anchored evidence.
- The anchor is tamper-EVIDENCE, not authentication. A citation not in the telemetry is rejected; and forging a sink entry buys no tier a trivial real command would not already earn — `anchored` alone is never hard without a co-sign distinct from the author — so self-fabrication cannot lift the floor.
- e2e / staging smoke / visual export JUnit and ride the normal DoD reader — only the human/exploratory tier needs this skill.
