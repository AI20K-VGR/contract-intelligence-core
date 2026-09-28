---
name: hs:problem-solving
injectable: true
description: Structured unblocking — identify the block type, choose the right technique, reframe before resuming implementation. Use when stuck in a loop, complexity escalates, or a hypothesis fails 3+ times.
argument-hint: "<problem> [--report] [--ultra [N] | --debate]"
allowed-tools: [Read, Write, Glob, Grep, Bash]
metadata:
  compliance-tier: workflow
---

# hs:problem-solving — structured unblocking

Identify block type -> choose technique -> apply systematically -> exit loop.
**No implementation.** No file writes outside `plans/reports/`.

**Evidence rule** in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` — technique insights must anchor to `file:line` or a concrete observation; unanchored -> tag `[ASSUMED]` (or `[PRIOR]` if from prior/training knowledge).

## When to use

- Complexity escalating: same thing 5+ ways, special cases growing
- Creative block: conventional solutions insufficient, breakthrough needed
- Recurring pattern: same problem in many places, reinventing wheels
- Forced hypothesis: feels like "only one way", can't question the premise
- Scale uncertainty: unsure design works in production
- **Broken code / failing tests -> use `hs:debug` instead** (not this skill)

## Quick dispatch — symptom -> technique

| Symptom | Technique | Reference |
|---|---|---|
| Same thing implemented 5+ ways, special cases growing | Simplification Cascades | `references/simplification-cascades.md` |
| Conventional solutions not enough, breakthrough needed | Collision-Zone Thinking | `references/collision-zone-thinking.md` |
| Same problem recurring across domains, done this before | Meta-Pattern Recognition | `references/meta-pattern-recognition.md` |
| Solution feels forced, "must do it this way" | Inversion Exercise | `references/inversion-exercise.md` |
| Not sure if it will scale | Scale Game | `references/scale-game.md` |
| Two directions, reasoning exhausted, metric is mechanical | **Empirical bake-off** → `hs:bakeoff` (not a reframing technique — decide by running) |
| Type of block unclear | Flowchart dispatch | `references/when-stuck.md` |

## Process (hard)

1. **Identify the type of block** — match against Dispatch table; unclear -> load `references/when-stuck.md`, follow the flowchart. Do not skip — wrong technique wastes more time.

2. **Load the reference** — open the reference file for the chosen technique. References contain the detailed process, examples, and red flags. Do not apply a technique from memory.

3. **Apply systematically** — follow the technique's process; record:
   - Input (specific problem, observed constraints)
   - Steps applied
   - Insights gained (anchored to `file:line` or a concrete observation)
   - What could not be applied and why

4. **Check results** — does the insight resolve the original block?
   - Yes -> propose next step (`hs:sequential-thinking`, `hs:plan`, or implement)
   - No -> try another technique or combine them (see Combinations table below)

5. **Record** — if `--report` flag is set or more than one technique was applied (Combining techniques below): summarize insights -> `plans/reports/<slug>-problem-solving-<date>.md`; return the absolute path.

## Combining techniques

Some blocks require multiple techniques:

| Combination | When |
|---|---|
| Simplification + Meta-Pattern | Recognize pattern -> simplify all instances |
| Collision + Inversion | Force a metaphor -> invert its assumptions |
| Scale + Simplification | Test extremes -> reveal what can be removed |
| Meta-Pattern + Scale | Universal pattern -> test at extremes |

## Boundaries

- NO implementation, NO code edits, NO writes outside `plans/reports/`.
- If the problem is **broken code / failing tests**: use `hs:debug` — this skill does not replace hs:debug; debugging is its own domain (hypothesis loop, root-cause chain).
- If the problem requires **multi-step analysis with revision**: use `hs:sequential-thinking`.
- If the problem requires **exploring multiple directions with trade-offs**: use `hs:brainstorm`.
- On completion: return insights anchored to evidence and a clear next-step recommendation.
- `--ultra [N]`/`--debate`: call `hs:workflow-orchestrate --ultra [N]|--debate --run-id <slug>` to size + drive N independent unblocking attempts over the SAME block (no shared context); `hs:escalation-consultant` synthesizes the recommended path. Approval gate is `hs:workflow-orchestrate`'s own.

## Wiring

This skill is a **reframing scaffold** — it triggers no harness gate and emits no gate-required artifact.

Cross-refs when output leads to action:
- `hs:sequential-thinking` — when the insight needs further multi-step analysis
- `hs:brainstorm` — when the insight opens multiple design directions to evaluate
- `hs:debug` — when the block is actually a bug (switch to debug, do not use this skill)
- `hs:plan` — when the insight is clear enough to create an action plan

## Workflow position

**Typically called from:** `hs:sequential-thinking` (stuck in reasoning chain), `hs:debug` (hypothesis fails 3+ times), `hs:brainstorm` (complex sub-problem).
**Typically leads to:** `hs:sequential-thinking` (insight needs further validation), `hs:plan` (insight ready for action), or directly to implementation once block resolved.

## Attribution

The reframing techniques in this skill (simplification-cascades, collision-zone-thinking, meta-pattern-recognition, inversion-exercise, scale-game, and the when-stuck dispatch) are derived from the agent patterns in Microsoft's **Amplifier** project (https://github.com/microsoft/amplifier, commit `2adb63f`). They are adapted here as scannable, symptom-discovered quick-reference guides rather
than long-lived JSON-output agents.
