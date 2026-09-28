# Escalation Criteria — When to escalate vs fast-fix

## Core rule

Triage escalates to `hs:plan` when a fix requires a **design change**, not merely an implementation fix. Fast-fixing an architectural defect creates new bugs.

## Signals that require escalation

Any of the following signals → mode `escalate`:

| Signal | Example |
|---|---|
| Root cause is in a contract/schema/interface | Schema change breaks multiple consumers |
| Fix requires modifying ≥ 3 unrelated modules | Bug in a shared helper used in many places |
| 3+ hypotheses all failed in `hs:debug` | No clear root cause found |
| Blast radius > 5 files with different owners | Cross-cutting concern |
| Defect reproduces differently across environments | Systemic flakiness |
| Minimal fix violates YAGNI (requires a new abstraction) | Refactor needed before fixing |
| Security/data integrity affected with unclear scope | Threat model not yet clear |

## The "3 hypotheses" rule

If `hs:debug` Phase 3 tries 3+ hypotheses and all fail:
1. STOP immediately — do not try a 4th hypothesis without additional evidence.
2. Ask the user via AskUserQuestion with 3 options:
   - **Escalate to hs:plan** (Recommended) — redesign the approach.
   - **Add instrumentation** — gather more data before continuing.
   - **Call hs:problem-solving** — reframe the problem from a different angle.
3. Do not self-decide — this is a mandatory stopping point.

Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` (fix-loop chains 6/7).

## Fast-fix is allowed when

All of the following conditions hold:

- [ ] Root cause is identified at a specific `file:line` (not "possibly").
- [ ] Minimal fix: 1-3 files, no new abstraction needed.
- [ ] Blast radius is clear and narrow (confirmed by scout).
- [ ] No architectural signals from the table above.
- [ ] `hs:debug` already has a failing repro test (required evidence).

## Escalate to hs:plan — handoff

When escalating:
1. Write a report at `plans/reports/<slug>-triage-escalation-report.md` including:
   - Symptom + reproduction steps.
   - Hypotheses tried + why they failed (evidence chain).
   - Architectural signals discovered.
   - Files + dependencies involved (from scout).
2. Ask the user: "This defect requires a redesign — open a new plan with hs:plan?"
3. Route: `/hs:plan <problem description> --context <path-report>`.

## Escalate to hs:problem-solving

When the problem is not architectural but thinking is stuck:
- 3+ hypotheses failed but blast radius is narrow.
- Need to reframe the question before continuing to debug.
- Route: `/hs:problem-solving` with context from the debug report.
