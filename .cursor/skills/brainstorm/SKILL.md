---
name: hs:brainstorm
injectable: true
description: Brainstorm solutions with honest trade-off analysis — ideation, architecture decisions, technical debate, feasibility exploration. Use before committing to an approach.
argument-hint: "<question> [--diverge | --converge | --critique] [--quick] [--ultra [N] | --debate]"
allowed-tools: [Bash, Read, Write, Glob, Grep, Task, SlashCommand]
metadata:
  compliance-tier: workflow
---

# hs:brainstorm — verified solution exploration

Divergent exploration, trade-off debate, convergence to a recommendation — via the `@brainstormer` agent. Does **NOT** implement, does **NOT** write code. Pure advisor, not executor.

**General rules** (YAGNI/KISS/DRY, Evidence Filter) at
`"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` — read before running any mode.

## Modes and flags

| Flag | Effect | When to use |
|---|---|---|
| _(default)_ | full diverge → converge | open question, direction not yet known |
| `--diverge` | exploration phase only, no convergence | need multiple options, not ready to commit |
| `--converge` | skip diverge, go straight to trade-off + recommendation | already have ≥2 options, need a verdict |
| `--critique` | adversarial pass: steelman → assumption attack → failure modes → verdict | have a specific idea/approach, want to challenge it before committing |
| `--quick` | single-pass, skip research phase | simple question, low risk |
| `--html` | render the final brainstorm as a self-contained editorial-magazine HTML report | want a polished, shareable write-up |

`--html` follows the editorial-print design system in `references/editorial-magazine-html.md` (diacritic-preserving, no-emoji — aligned with the harness humanizer). When the problem itself is unclear, decompose it with `references/problem-first.md` (solution→problem + evidence-status taxonomy) before diverging.

## Standard procedure (diverge → converge)

1. **Scout** (required): use `hs:scout` to read related code, `docs/`, active `plans/`. Summarize 3-6 bullets for the user before asking. No scout = no brainstorm.
2. **Discovery**: use `AskUserQuestion` to extract: expected output, acceptance criteria, scope boundary, hard constraints, touchpoints. Loop until all 5 items are specific.
3. **Scope check**: request describes ≥3 independent concerns → decompose into sub-projects, brainstorm each separately, do not bundle them together.

4. **Research** (skipped with `--quick`): spawn `@brainstormer` agent to explore options — read external documentation, query real schema/data if the decision depends on it.
5. **Analysis**: `@brainstormer` presents 2-3 directions, compared across specific dimensions (complexity, cost, latency, maintainability, second-order effects). **MUST** name the lowest-complexity option that still meets the requirements "MVS" and default to it absent specific evidence it is insufficient. Technical details → `references/divergence-techniques.md`.
6. **Debate**: present each option with its trade-offs and your recommendation in visible response text *first*, then use `AskUserQuestion` to capture the choice — never offer an option you have not described in the response (extended-thinking analysis is invisible to the user). Challenge preferences, iterate to consensus.
7. **Consensus + Decision**: finalize the approach, document the decision. Details → `references/convergence-and-decision.md`. Architecture call → `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py --append-alloc ...` to record DEC.
8. **Report**: create a markdown report in `plans/reports/` (see "Boundaries").
9. **Plan handoff**: if brainstorm converged and the user wants to continue, `AskUserQuestion` proposes `/hs:plan` (fast|hard, `--tdd` if refactoring core logic).

## Mode --critique (adversarial)

Load `references/critique-protocol.md`. Steps:

1. **Steelman**: present the strongest version of the idea — no straw-manning.
2. **Assumption attack**: list ≥3 implicit assumptions; attack each with a counter-scenario.
3. **Failure modes**: predict ≥3 ways the approach breaks in practice (operational, security, scale, maintenance). Each failure: 1 sentence scenario + 1 sentence consequence.
4. **Verdict**: Adopt / Adopt-with-guard / Reject — with 2-3 sentences of reasoning.
5. If Adopt-with-guard or Reject → propose an alternative or conditions for reconsideration.

`--critique` never skips scout: attacks must be grounded in real code, not hypothetical targets.

## HARD-GATE (real wiring)

- `@brainstormer` (`harness/plugins/hs/agents/brainstormer.md`) performs divergent exploration; skill = orchestrator, agent = executor.
- Convergence on an architecture call → must be recorded via
  `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py` — prevents re-litigation.
- Report must be in `plans/reports/` — CI invariant forbids markdown outside `plans/` and `docs/` (CLAUDE.md rule #5).
- No gate blocks stage; a `/hs:plan` generated from here carries the normal stage policy at ship time.

## Output language

Render reports per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/output-rendering.md`: resolve `language` / `audience` / `humanize` live via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/output_config.py --resolved` (never hand-read the tracked file); the rule holds the register behavior and the evidence-invariant fence.

## Boundaries

- Do NOT implement, do NOT write code, do NOT modify harness files.
- Do NOT finalize an approach without presenting trade-offs — a recommendation without evidence is treated as a violation of the Evidence Filter (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`).
- Architecture call finalized → record DEC via `decision_register.py`; when revisiting old tension read the register first, do not relitigate.
- Report: `plans/reports/<slug>-brainstorm-report.md` (naming from `## Naming` in the hook's context injection); use `hs:sequential-thinking` if the problem requires multi-step analysis with revision.
- On completion: return the absolute path to the report + suggest the next step (further validation / `/hs:plan` / stop).
- `--ultra [N]`/`--debate`: call `hs:workflow-orchestrate --ultra [N]|--debate --run-id <slug>` to size + drive N independent brainstorm passes over the SAME question (no shared context); `hs:escalation-consultant` synthesizes the option set, and only that synthesized set is written to the report. Approval gate is `hs:workflow-orchestrate`'s own.

## Workflow position

**Typically after:** `hs:debug` (solutions for a diagnosed problem), `hs:scout` (after gaining a codebase picture).
**Typically before:** `hs:plan` (plan the agreed approach).
**Related:** `hs:research` (deep-dive one option), `hs:sequential-thinking` (multi-step analysis with revision).

## Interview rigor (voice knobs)

Read three knobs from `"${HARNESS_BIN_ROOT:-.}"/harness/data/terminal-voice.yaml` (resolved by `voice_prefs.py`, injected at session start) and let them shape how hard you interrogate the idea, not the design doc:

- `interview_rigor` (light | standard | **deep**) — at `deep`, challenge assumptions harder, push more alternatives, and probe more failure modes / edge-cases before converging; at `light`, surface only the decisive trade-offs.
- `action_prompting` (minimal | standard | proactive) — at `proactive`, offer more next-step suggestions at turn boundaries.
- `terminal_voice_level` (0–5) — sizes discussion prose + follow-up count too (turn verbosity; the former `detail_level` folds in here). The summary report's length stays governed by `output.yaml`.

