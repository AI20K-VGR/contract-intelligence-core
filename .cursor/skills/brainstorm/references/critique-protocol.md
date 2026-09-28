# Critique protocol — adversarial pass (--critique mode)

Load when the `--critique` flag is passed. Goal: challenge an idea/approach before the team commits — find failure modes, not strengths.

## Prerequisites

1. Scout the codebase FIRST — attacks must be grounded in real code/schema/config, not hypothetical targets.
2. If the idea is not yet described specifically → `AskUserQuestion` to extract:
   - What is the approach (1-3 sentences)?
   - What are the key assumptions the approach rests on?
   - Scope (in/out)?

## Step 1 — Steelman

Present the **strongest** version of the idea:
- What does the best-case scenario look like?
- What is the most compelling reason to choose this approach?
- Has something similar been used successfully elsewhere?

Purpose: ensure the attack targets the real idea, not a straw man. The user must confirm the steelman is "on target" before moving to step 2.

## Step 2 — Assumption attack

List ≥3 **implicit** (unspoken) assumptions the approach depends on. For each assumption → 1 counter-scenario:

```
Assumption: <statement>
Counter-scenario: What happens when this assumption is wrong?
Evidence: <file:line or verification command> or [ASSUMED]
```

An assumption without a counter-scenario is not an attack — discard it. `[ASSUMED]` is valid when the counter-scenario is plausible but lacks specific evidence — must explicitly state "needs further verification".

## Step 3 — Failure modes

Predict ≥3 ways the approach breaks in practice. Classify by vector:

| Vector | Guiding question |
|---|---|
| Operational | How does it break at 10x load? When an operator must intervene at 2am? |
| Security | What attack surface is opened? What input is not validated? |
| Scale | Which assumption about data size / concurrency breaks first? |
| Maintenance | Can a new maintainer understand and fix this quickly 6 months later? |

For each failure mode:
- **Scenario** (1 sentence): what happens
- **Consequence** (1 sentence): specific impact
- **Severity**: C (critical) / H (high) / M (medium) / L (low)

Cap at 10 failure modes after deduplication — keep the highest severity, cluster the rest.

## Step 4 — Verdict

One of three:

| Verdict | Meaning | Condition |
|---|---|---|
| **Adopt** | Approach is sound, proceed | Failure modes at M/L, no C/H assumptions disproved |
| **Adopt-with-guard** | Proceed with additional conditions | ≥1 H assumption disproved → specific mitigation required before committing |
| **Reject** | Do not use this approach | ≥1 C assumption disproved, or a C failure mode has no mitigation |

Reasoning: 2-3 sentences, not an essay.

## Step 5 — Alternative (if Adopt-with-guard or Reject)

- Name ≥1 simpler or lower-risk alternative.
- If no clear alternative exists → list conditions for reconsideration (e.g., "Reconsider when evidence X is available or constraint Y is relaxed").

## Critique rules

- Attacks must have evidence (file:line, command, or explicit `[ASSUMED]`). An attack without evidence → reject the finding, do not include it in the report.
- Steelman must come before the attack — do not open with a rebuttal.
- The verdict belongs to the advisor (brainstormer agent), not the user — the user may override, but an override must record the reason in the report.
- `--critique` report is saved to `plans/reports/<slug>-critique-report.md`.
