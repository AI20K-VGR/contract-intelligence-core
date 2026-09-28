---
name: hs:sequential-thinking
injectable: true
description: Multi-step analysis with revision — decompose complex problems, verify hypotheses, adjust direction mid-stream. Use when scope is unclear, reasoning needs a trace, or errors must be caught early.
argument-hint: "<problem> [--report]"
allowed-tools: [Read, Write, Glob, Grep, Bash]
metadata:
  compliance-tier: workflow
---

# hs:sequential-thinking — verified sequential reasoning

Step-by-step analysis: revise, branch, converge. Does **not** implement code; writes only under `plans/reports/`. Output: labeled Thought sequence + optional report.

**Evidence rule** at `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` — claim unanchored to `file:line`/real command output → tag `[ASSUMED]` (or `[PRIOR]` if resting on prior/training knowledge); later steps must not build on it.

## When to use

- Complex problem, scope unclear or emerging gradually
- Reasoning trace needs to be public so the user can review / catch errors early
- Hypotheses need verification before `hs:plan`/`hs:debug`
- Architecture decision with multiple parallel hard constraints
- Stuck in a loop — `hs:sequential-thinking` forces externalized thinking

## Modes

| Mode | When | Behavior |
|---|---|---|
| `explicit` (default) | scope is unclear, user wants to follow along | Thought markers displayed |
| `implicit` | task is clear, thinking supports internal work | No markers printed, result delivered directly |

Flag `--report`: saves the Thought sequence to `plans/reports/`.

## Structure of each Thought

```
Thought N/M [label]: [content]
```

**Labels required on special events:**

| Label | When |
|---|---|
| `[REVISION of Thought X]` | New insight invalidates a previous Thought X |
| `[BRANCH A / BRANCH B]` | Exploring ≥2 parallel directions |
| `[CONVERGENCE]` | Integrating branches, selecting a direction |
| `[HYPOTHESIS]` | Proposing a hypothesis that needs testing |
| `[VERIFICATION]` | Result of testing a hypothesis |
| `[META]` | Observing the thinking process itself — use when going in circles |
| `[FINAL]` | Last Thought, solution is fully qualified |

## Procedure

1. **Initial estimate** — select total N (initial M) based on perceived complexity. `Thought 1/N: [initial analysis]`

2. **Dynamic adjustment** — after each Thought:
   - More complex than expected → increase M
   - Simpler than expected → decrease M
   - Major revision encountered → add label, assess downstream impact (see `references/patterns.md`)

3. **Branch when needed** — maximum 2-3 branches at a time; convergence is required before opening a new branch. Load `references/patterns.md` for trade-off evaluation and hypothesis testing patterns.

4. **Stop when conditions are met** — place `[FINAL]` only when:
   - Solution verified
   - All hard constraints addressed
   - No unaddressed uncertainty remains
   - Load `references/advanced.md` if Spiral Refinement/Parallel Constraint Satisfaction needed
   - Worked examples: `references/examples-api.md`, `references/examples-debug.md`, `references/examples-architecture.md` — full loop traces on real problems.

5. **Report (optional)** — on `--report` flag or user request: summarize reasoning → `plans/reports/<slug>-sequential-thinking-<date>.md`. Return absolute path.

## Boundaries

- Do NOT write code, do NOT implement.
- Do NOT write markdown outside `plans/reports/` (CLAUDE.md rule #3).
- Claims in Thoughts must be anchored to `file:line` or command output — no anchor → `[ASSUMED]`/`[PRIOR]`.
- If the problem needs multi-direction brainstorming: suggest `hs:brainstorm`.
- If reasoning leads to a plan: suggest `hs:plan` (do not open it automatically).
- If reasoning leads to a bug root-cause: suggest `hs:debug`.

## Wiring

This skill is a **pure reasoning scaffold** — no harness gate blocks stage. Emits no gate-required artifact.

Cross-refs when escalating:
- `hs:brainstorm` — when more option divergence is needed
- `hs:plan` — when reasoning has converged and an action plan is needed
- `hs:debug` — when reasoning focuses on bug root-cause
- `hs:problem-solving` — when stuck and a hard structured reframe is needed

## Workflow position

**Typically called from:** `hs:brainstorm` (complex sub-problem), `hs:plan` (internal constraint analysis), `hs:debug` (multi-step root-cause trace).
**Typically leads to:** `hs:plan` (output = approach), `hs:debug` (output = root-cause), or straight to implementation when reasoning is short enough.
