---
name: hs:plan
injectable: false
description: Create a verified implementation plan — research, constraint-scan, phase design, red-team, and validate before cook. Use when a real feature or refactor needs a verified plan before any code is written.
argument-hint: "[--fast | --hard] [--tdd] [--deep] [--parallel] [--grid] [--defer-suite] [--in-place] [--yagni] [--html] [--wiki] [--debate | --ultra [N]]"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob, Task]
metadata:
  compliance-tier: workflow
---

# hs:plan — verified planning, sequenced by `hs-run`

`--yagni` cuts scope not needed for the stated outcome; the default delivers the full ask. Pass it to `hs-run`, which stamps the posture and names the rule.
`--html` renders a self-contained page beside the markdown; `--wiki` publishes it after your confirmation. Pass them to `hs-run`, which stamps the rung and names the rendering rule.

Creates a plan under `plans/<timestamp>-<slug>/` (plan.md + `phases/` + `plans/<slug>/plan-graph.yaml`).
The plan is the contract for hs:cook: cook runs only after a **HUMAN** approves it.

The split this skill is built on: **`hs-run plan` owns the ORDER of the steps and their
parameters. You own whether a step applies and what goes into it.** Read
`"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/_shared/hs-run/hs-run-contract.md` once — the exit ladder, the
two-beat delegation pattern, and why `next` is a projection rather than a progress file.

**What each step needs is routed by the CLI, not listed here.** Every envelope carries
`rules` and `references` — the rule files and the reference/standards documents THIS state
needs — plus an `advisory` line when the step has one. Read what the envelope names, and
only that. But the envelope routes DOCUMENTS, never the object of the work: reading
everything it names is not enough to have done the step — the artifact on disk is what the
step changes, so open it.

**Probe-first ★** — the priority discipline: a load-bearing assumption the plan rests on that CAN be checked empirically gets RUN before
the plan builds on it, not deferred to cook. A doc / `--help` / grep / chain of reasoning is a
*hypothesis*, NOT a probe; an unrun claim is `[ASSUMED]` (`[PRIOR]` if training knowledge),
never OBSERVED. Held at MAIN, never delegated.

## Step 0 — standards are input, not decoration

The plan references the shared standards instead of inventing its own.
Standards missing → author them first
(`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/scaffold_standards.py`) rather than planning on an empty base; the CLI
warns at `no_plan` and lets you continue, because a project may be planning its own
standards — so this one is on you, not on a gate. Settled vocabulary is
injected at session start — name things with it and respect its forbidden wording.

## Who does what — main vs subagent

On `--hard`, **delegate by default**. `--in-place` keeps the delegated middle (plan-writing,
red-team) at main; `--fast` skips research + red-team outright (the small / low-risk lane).

| Held at MAIN — never delegated | Delegated to a subagent |
|---|---|
| the interview bookends — understand · scope-challenge · validate · **approval** (they call AskUserQuestion, which dies with no TTY) · probe-first empirical checks · constraint-scan · the final consistency sweep · recording the approval | `@researcher` · `@planner` — writes plan.md + phase files · `@red-teamer` — attacks the plan |

A subagent has no TTY, so any step that must ask the user stays at main. On `--hard`, do NOT
hand-author plan.md/phase files at main — that is `@planner`'s job.

## Modes — one judgment, made up front

| Mode | When | Gates |
|---|---|---|
| `--fast` | small task, 1–2 files, low risk | skips research + red-team |
| `--hard` (default) | a real feature or refactor | constraint-scan → red-team → validate |

**Scope-driven default**: unless the user typed a mode, assess scope after the understand step
and default to `--hard` + `--tdd`. Switch to `--fast` or drop `--tdd` **only when the exception
is clear** — 1–2 files, no logic change, no new tests needed, or the user asked for lighter.

Orthogonal flags: `--tdd` (per-phase test-first/implement-after pair) · `--deep` (per-phase
file inventory, test-scenario matrix, dependency map) · `--parallel` (dependency matrix +
file-ownership table so cook can fan out) · `--in-place` (keep the delegated middle at main
when delegation overhead is not worth it, or the subagent lane is unavailable) · `--grid`
(coverage becomes a first-class step — **do not declare it by default**) · `--defer-suite`
(stamps `defer_suite: true`, carried into cook's suggested command).

**Complexity hint — advisory cross-check, never a decision.** After reading the goal, print one
line: `complexity: simple|standard|complex · ~N phases · risk: <area>`. Agrees with the mode
the user typed → stay silent. Disagrees → interactive: confirm via `AskUserQuestion`
(recommended option first); headless (no TTY): record one line in `## Validation Log`
(`VL-n | hint=complex but mode=--fast | keep user-chosen mode | <reason>`) and **keep the
user's mode**. The hint is **advisory only** — it never **auto-routes** gate depth and never
changes the mode on its own.

## The loop

```
hs-run plan next
```

Run it, read the `state`, do the judgment that state names, run it again. Every state is
re-derived from artifacts on disk, so deleting an artifact regresses the state — that is the
design. Mode is read from disk too: a plan whose frontmatter says `mode: fast` stays fast
across sessions without the flag. A typed `--fast` still wins, and says so in `warnings` when
it contradicts the plan's own `mode:` — fix whichever side is stale.
Exit ladder: `0` nothing left · `10` a model turn · `11` one deterministic step · `2`
the CLI cannot answer — **STOP**. Read `warnings` at every exit: at `2` they say why the
run stopped, at `0` they are information the run continued past.

Every envelope prints its own `state` and exit rung, and `next_action` names the
judgment that state contains. Do that judgment — do not look for the state in a table
here. There is no table: a hand-copied index of a machine that emits thirty states
goes stale where nothing can see it, and a partial index reads exactly like a
complete one.

**`--fast` skips are VISIBLE**: every projection carries a `skipped` list naming exactly which
gates `--fast` bypassed — sizing, research, red-team. Read it before claiming a plan went
through any of them. A gate the plan had already CLEARED is not in that list (the flag waived
nothing), and neither is a gate that does not apply at all — `next`'s own `checklist` marks the
grid row skipped on a plan with no grid, which is a different question with the same word.

## What `no_plan` contains — the understand + scope-challenge bookends

Read the request, docs, and related code; identify the real scope (cut YAGNI).
`interview_rigor` sets HOW HARD to probe, never whether — the 5-fact floor is INVARIANT
regardless of density_tier. Before decomposing you MUST be able to state each in one concrete
sentence (use AskUserQuestion to pin any that stay vague):

- **expected output** — the artifact the user sees: path / behavior / endpoint+payload / CLI+flags
- **acceptance criteria** — inputs→outputs and edge cases that mean "done"
- **scope boundary** — what is explicitly OUT this round. An empty answer is a push-back
  trigger.
- **non-negotiable constraints** — stack, locations, naming, back-compat, perf
- **touchpoints** — which existing files/contracts get modified, so options stay grounded in
  real paths

**Scope challenge** (skip on `--fast`, or a task under 20 words and unambiguous): ask four
questions — what existing code can be reused? what is the minimal change set? does this touch
>8 files / >2 new classes / >3 phases? and, in the other direction, **who else lands on this
surface** — is it single-owner and short-lived (where the minimal change is the right one), or
long-lived and shared (where a seam, an extension point, or an explicit contract is cheaper to
build now than to retrofit through every caller later)? The first three questions all pull
toward less; this one is what stops that pull from becoming automatic. Whatever it decides
becomes REQUIRED scope for cook — a later "shrink" step may not drop it.
Then choose EXPANSION / HOLD / REDUCTION via AskUserQuestion before any research.

## Grid coverage — only when `--grid`

Build the planner macro coverage-grid (feature × layer × lifecycle × risk × stakeholder) and
**resolve every thin/absent cell before red-team** (cover it or mark `[JUSTIFIED-THIN]`), then
`emit` the artifact. A **hard PRESENCE + provenance gate**: `plan_approval` refuses APPROVED
without it, and no hand-built shortcut clears it. Stamps `grid: true` for cook; never
auto-edits, never hard-blocks downstream. Axis-selection is GATED; the combination-ban is
frozen; the below-floor confirm goes through AskUserQuestion.

**Do NOT declare `--grid` by default, and do not decide it from this paragraph.** Four
preconditions must ALL hold, the cost floor is flat rather than proportional, and the
declaration gates your own approval — the run routes the file that owns those criteria
before you type the flag.

## Finish

Return the **ABSOLUTE PATH** of the plan and recommend the next step — a further validate pass,
cook, or stop. That recommendation is a judgment, not a fixed default.

Plan approval belongs to the **HUMAN**; autonomy at every level stops here. Ask via
`AskUserQuestion` with three options [Direct Review (Plannotator) / Approve / Reject], then
record the verdict through the command `next` printed. The approval is content-bound: edit the
plan after approving and the state regresses to `approval_invalid` on its own.

**Context isolation before cook**: after approval, recommend `/clear` to isolate planning
context, then the cook command. **Do not compose that command yourself** — the `approved`
envelope's `next_action` already carries it, flags and all, derived from the plan's own
frontmatter. Read it out; re-deriving it by hand is how the two answers drift apart.

The `/clear` happens AFTER the user has noted the cook command. Write every command as
**inline code** (single backticks), never a fenced block — the terminal highlights inline
`/...` commands and renders a fence flat and uncoloured.

## Boundaries

- Do NOT write code; do not modify files outside `plans/`.
- Archiving a finished plan is a separate end-of-lifecycle action, never part of authoring —
  it journals and then deletes the plan directory. Ask
  before writing the journal entries and ask **again** before archiving. Never fire it on a
  plan you just created.
- Do not weaken a gate or a threshold to make a step pass.
- `--debate`/`--ultra [N]` are mutually exclusive with `--fast/--hard/--deep/--parallel` (refuse the combo, name the conflict).

## Panel mode (`--debate` / `--ultra [N]`)

Call `hs:workflow-orchestrate --debate|--ultra [N] --run-id <slug>` before phase design to
size + drive N independent planners over the SAME research/constraint-scan (no shared context
between them); it hands the panel to `hs:escalation-consultant`, which synthesizes ONE plan out
of the N positions. Only that synthesized plan proceeds to red-team/validate below —
`hs:workflow-orchestrate`'s own approval gate applies first.

## Interview rigor

The voice knobs (`interview_rigor`, `action_prompting`, `terminal_voice_level`) are resolved
and injected at session start; they shape the interview, never the artifact. At `deep`,
challenge claims harder and probe more gaps / edge-cases / acceptance-criteria holes in the
scope-challenge + validate steps; at `light`, ask only the blocking questions.

## Observe checkpoint (end-of-work)

When the plan is done, emit at most ONE closed-vocab signal — valid terms here:
`thin-evidence`, `red-team-reopened`, `plan-revised-post-approval`, `trigger-near-miss`.
Most runs emit nothing.
