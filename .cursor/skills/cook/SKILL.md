---
name: hs:cook
injectable: false
description: Execute an approved plan phase by phase — TDD red→green, generate verification/review-decision artifacts, trace every step. Use when a human-approved plan is ready to implement.
argument-hint: "<plan-path> [--phase <id>] [--parallel] [--tdd] [--grid] [--defer-suite] [--in-place] [--review <low|medium|high|xhigh|max>] [--yagni]"
allowed-tools: [Bash, Read, Write, Edit, MultiEdit, Grep, Glob, Task]
metadata:
  compliance-tier: workflow
---

# hs:cook — execute plan by phase

Input: path to a human-approved plan. No approved plan → return to hs:plan (gate `require_plan` blocks hard stages if you try to skip this).

**What each step needs is routed by the CLI, not listed here.** Every envelope carries
`rules` and `references` — the rule files and reference documents THIS state needs — plus
an `advisory` line when the step has one. Read what the envelope names, and only that. But
the envelope routes DOCUMENTS, never the object of the work: reading everything it names is
not enough to have done the step — the code and the phase file are what the step changes,
so open them.

**Context isolation:** cook should run from a CLEAN context — `/clear` after approving the plan, then `/hs:cook <absolute-path>`. Planning carryover (research, debate, red-team) shifts cook's focus. Nothing enforces this and nothing reminds you: the advisory that once did ships disabled, so noticing that plan and cook are in the same session is yours.

**Flags carried from the plan (`--tdd` / `--parallel` / `--grid`):** NOT new cook decisions — the plan already locked them; hs:plan hands you the exact cook command.
Cook auto-inherits when a flag is absent (TDD plan runs red→green regardless; `--parallel` also resolves from env/config), but the flag makes the behavior **explicit and traced** vs implicit. Surface it to the user, do not swallow it:
- `--tdd` → announce the per-phase Tests Before → Implement → Tests After → Regression Gate split is active for this run (vs the plain red→green cook prints otherwise).
- `--grid` → announce that each phase builds its executor micro coverage-grid BEFORE
  red→green, and that its thin corners land in the phase's test plan — it makes TDD more
  complete, it never replaces a test, relaxes the 100%-pass gate, or hard-blocks. It carries
  from the plan's own `grid: true` with no retyping, so surface "grid carried from plan" —
  never silent, never `--auto`.
- `--parallel` → announce which phases fan out concurrently BEFORE the first slice, and that
  the integration barrier still runs the full suite serially. If the plan's handoff
  recommended sequential but `--parallel` was passed anyway, say so; the partitioner
  re-demotes overlapping batches and is the final arbiter. Never fan out silently.

**Probe-first ★** — the priority discipline: a load-bearing assumption the phase rests on
that CAN be checked empirically gets RUN before the code builds on it. A doc / `--help` /
grep / chain of reasoning is a *hypothesis*, NOT a probe; a plan claim not exercised is
`[ASSUMED]` (`[PRIOR]` if training knowledge), never OBSERVED. Held at MAIN, never
delegated.

## Step 0 — Standards are input

Same as hs:plan: read `docs/code-standards.md` + `docs/system-architecture.md` before writing code. Code follows the shared `docs/code-standards.md` — that is why the harness exists on this machine.

## The loop — `hs-run cook` owns the ORDER, you own the JUDGMENT

```
hs-run cook next
```

Run it, read the `state`, do the judgment that state names, run it again. Every state is
re-derived from artifacts on disk, so deleting an artifact regresses the state — that is
the design. Exit ladder: `0` nothing left · `10` a model turn · `11` one deterministic
step · `2` the CLI cannot answer — **STOP**. Read `warnings` at every exit: at `2` they say
why the run stopped, at `0` they are information the run continued past. Full contract (the
two-beat `prompt`→`record` pattern, why `next` is a projection):
`"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/_shared/hs-run/hs-run-contract.md`.

Every envelope prints its own `state` and exit rung, and `next_action` names the judgment
that state contains. Do that judgment — do not look for the state in a table here. There is
no table: a hand-copied index of a machine that emits thirty-five states goes stale where
nothing can see it, and a partial index reads exactly like a complete one.

**One command, and the run prints the rest.** `next` is the only verb you type. Opening the
plan, verifying a phase, recording a delegation, closing out — each arrives as a
`next_command` in the envelope that needs it, `--plan` and `--phase` already filled from the
plan's own frontmatter. Read it out and run it; do not compose one yourself. A hand-typed
verb is a second answer to a question the CLI already answered, and the two drift.

`record` is an ATTESTATION that you ran the step. The CLI checks it against the spawn ledger
and reports `spawn_attested` — but `false` there means *no evidence*, never *no spawn*:
reviewing the subagent's output is still your job, before you call `record`.

## The grid preflight — presence is checkable, QUALITY is yours

The preflight belts (the mandatory `plan-graph.yaml` sidecar, and the MACRO `coverage-grid`
presence gate when grid mode is carried) run inside `next`; a block arrives as a state, not
as a separate command you type. What no gate can check is the part that matters: a grid
below floor (`coverage_ratio < density_tier floor`) or verdict `reject` PASSES presence.
Never skip it silently — surface the thin cells + confab signals and **AskUserQuestion;
proceed only on explicit confirm**. Micro one-pass: spawn @grid-axis-selector, receipt +
freeze before fill, no diff.

## Per-phase loop

1. **Conformance checklist**: read the phase file; list files to create/modify; verify naming/format match standards; any deviation from the plan → STOP and ask, never silently change.
   A `warnings` line naming a phase file means the approval hash misses that file —
   re-approve before trusting the plan contract. Advisory by design; the hash is what blocks.
2. **TDD red→green**: test-first intentional FAIL → implement until green → re-run full
   suite (or, on a plan carrying `defer_suite: true`, the current phase's declared test
   files only — the full suite still owes one run before `cook close`) → paired commit
   test+module.
   **Before a phase's red→green (3.T test + 3.I implement) on a `mode: hard` plan: STOP — the WHOLE phase delegates to `@developer` by default; going inline needs an explicit flag or a surfaced decision (see §Per-phase red→green).**
   Flag `--tdd` (carried from the plan, or passed here): each phase splits Step 3 into the
   explicit Tests Before → Implement → Tests After → Regression Gate sequence. Without it cook
   still runs red→green; `--tdd` just makes the split explicit and traced.
   On green, before advancing, a **simplification pass**: if the change grew a special case or
   duplicated an existing pattern, collapse it (suite stays green). Pattern library:
   `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/problem-solving/references/simplification-cascades.md`.
3. **Verify before done**: before writing artifact and advancing phase — suite green, no new lint/type errors, every acceptance criterion has evidence (file:line), no silent contract change. If a side effect appears → STOP AskUserQuestion with 2-4 choices; do not self-patch.
4. **Artifacts**: the verify command the envelope prints writes `verification.json` with the
   phase already named — a per-phase snapshot, never a plan-wide one. Review adds
   `review-decision.json` (schema in `harness/schemas/`). The gate reads from the
   **filesystem**, so no commit is needed for it to see an artifact — but `plans/` is tracked
   (only `plans/reports/` is scratch), so commit them into the plan at finalize.
5. **Trace**: significant steps emit events via `"${HARNESS_BIN_ROOT:-.}"/harness/hooks/trace_log.py` (append_event —
   actor auto-resolved, never hand-craft JSONL). Carve-out: a phase declared stateless
   (frontmatter `stateless: true` or `# stateless-by-design`) skips trace; gate_stage still
   runs — trace is telemetry fail-open, not a compliance gate.

## Per-phase red→green (3.T+3.I): delegate to `@developer` by default — STOP before coding inline

**Before you write ANY test or implementation code for a phase, STOP and resolve the delegation — this is a checkpoint, not a suggestion.** On a `mode: hard` plan the phase's **full red→green (test 3.T + implement 3.I)** goes to a `@developer` subagent BY DEFAULT.
Main keeps verify (3.V), a **review of the subagent's code AND test** (catch a tautological or weakened test), and the paired commit. This is the only delegation with **no gate behind it** — nothing mechanical stops you from sliding into inline coding, so the discipline is on you. Run this check every phase:

1. **Resolve the mode deterministically** — READ it from a flag, the phase frontmatter, the
   plan frontmatter or the graph, in that order. Never infer it from a prose impression that
   a plan "feels hard". **Only `--in-place` or a phase's `in_place: true` authorizes inline.**
2. **No inline flag but you want to go inline anyway? That is a DECISION, not a default — surface it.** Never bury it in an announce line. STOP and AskUserQuestion (why inline, what is lost), then wait. Rationalizing inline from a memory or an edge case is the exact failure this guards.
3. **Proactive / autonomous output style does NOT waive this.** "Prefer action, execute inline" is a style default; `mode: hard` delegation is a plan mandate and **out-ranks** it. On conflict, delegate (or surface per #2) — never let the style bias silently pick inline.
4. **Already inside a worktree**: still delegate — a plain `@developer` spawn (no `isolation`
   param) runs in-place and inherits the current working directory, so its writes land in
   THIS worktree. Only `isolation="worktree"` gets its OWN tree, which is for `--parallel`
   slices editing shared files — never a reason to implement inline in a sequential phase.

## After the last phase — MANDATORY delegation (Steps 4–6, never skip)

Cook is NOT done at the last phase's integration barrier + `verification.json`. The post-build steps are MANDATORY and MUST be delegated via the Task tool — never done inline, never skipped on a "small" task.

- **Step 4 — test**: MUST spawn `@tester`. Running the suite yourself is NOT a substitute for the independent tester delegation.
- **Step 5 — code review**: MUST spawn `@code-reviewer` on the diff — at this final gate, **DO NOT review code yourself**. The FINAL review re-derives correctness and catches what same-thread self-review misses. It does NOT replace main's per-phase review of each `@developer` slice — that happens every phase.
  **`--review <low|medium|high|xhigh|max>`** dials how hard this review digs, never *whether* it runs. There is no `skip` value: the floor is always a real independent review writing `review-decision.json`.
- **Step 6 — finalize**: MUST spawn `@docs-manager` + `@git-manager`, run project-management sync-back, then close. Skipping any leaves the plan half-shipped.

**Hard rule**: if Task-tool calls = 0 at the end of a cook run, the workflow is INCOMPLETE.

## Pause cadence — HARNESS_AUTONOMY

| Level | Behavior |
|---|---|
| `default` | run per-phase sequence automatically; **pause at 2 checkpoints: plan approval + ship** |
| `ask_all` | pause after EVERY phase |
| `god` | no pauses (trace still records fully — autonomy comes with a trace) |

Resolve the level deterministically — never eyeball the env. At each boundary run `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/autonomy_policy.py --boundary <plan_approval|phase|ship>` and pause only when it prints `pause` (`--show` emits the resolved level + matrix; the two flags are mutually exclusive). A missing/invalid level falls back to `default`.

No level self-ships: stage `push|pr|ship|deploy` always goes through the artifact gate.

When pausing for human (`ask_all` after a phase, or before writing `review-decision.json`): ask AskUserQuestion with 3 options [Review directly (Plannotator) / Approve / Reject]; choosing (1) → `plannotator_surface.py review <diff>` (rule `plannotator-review-gates.md`).

## Parallel execution (`--parallel`, default-on)

Default is now **parallel-on** (`cook.parallel: true`): cook runs independent phases concurrently to save wall-clock — without weakening a gate or trusting a subagent on sight. Full protocol: `references/parallel-execution.md` (this one the CLI cannot route — see below).

Three things the drawer cannot enforce, and they are the ones that go wrong:

- **A returned subagent is an unverified CLAIM, not a result.** Every slice self-verifies
  (its tests + lint, its diff against the phase's acceptance criteria), and a risky one —
  touches a gate/hook, changes a contract, thin test evidence — gets an independent verifier
  that re-derives correctness from the diff ALONE. A slice failing either tier does not merge.
- **Never parallel-edit a shared path**, and never fall back to sequential silently. The
  partitioner demotes both sides of an ownership overlap and reports it; say so.
- **The integration barrier stays serial.** Parallelism speeds the build, never the gate:
  the full suite runs serially after the merges, before any artifact is written.

## Gate wiring (personal-first: generate local, enforce remote)

`"${HARNESS_BIN_ROOT:-.}"/harness/hooks/gate_stage.py` ADVISES on a hard stage when `verification.json` is missing / verdict != PASS — `[advisory]` + `gate_advisory` trace, command proceeds (exit 0). The one hard LOCAL block is the artifact-forgery arm (shell write to a receipt path — the agent cage). Presence enforcement lives in remote CI (receipts-gate).

## References the CLI cannot route

Load these two yourself, on the condition named in the last column. No state expresses that
condition: `--parallel` resolves from a flag, an env var and a config file rather than from
anything on disk, and the artifact schema is needed *while writing* a file, not at a state.

| Drawer | Content | When to load |
|---|---|---|
| `references/parallel-execution.md` | Opt-in `--parallel` protocol: resolve → partition → delegate → verify → integration barrier | When cooking with `--parallel` |
| `_shared/workflow-artifacts.md` | JSON artifact schema (context-snippets/risk-gate/verification/review-decision/adversarial-validation), approval rules, redaction policy | When writing or validating review/finalize artifacts |

## Observe checkpoint (end-of-work)

When cook finishes, emit at most ONE closed-vocab signal — valid terms here:
`gate-repeat-block`, `plan-revised-post-approval`, `thin-evidence`. Most runs emit nothing.

## Boundaries

- Do not modify `harness-hooks.yaml`/`stage-policy.yaml` to pass the gate — git-tracked, any change shows in diff + trace. Genuinely stuck → ask the human.
- Work that arises outside the plan scope → record via `backlog_register.py add`; do not steer the plan mid-flight.
- Mid-phase, if the planned direction stalls and 2-3 alternatives are measurably comparable, escalate to `hs:bakeoff` (probe the alternatives, decide by numbers) instead of grinding one direction — then resume cook.

## Auto-decision ledger

Record ONLY decisions that DEVIATE from the approved plan.
