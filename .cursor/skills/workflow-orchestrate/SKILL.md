---
name: hs:workflow-orchestrate
injectable: true
description: Design a spawn strategy for a delegated task — pick subagents vs Workflow vs Agent Teams, size and group the fan-out, batch-consolidate, early-write findings — then present it for approval before spawning. The delegation planner other skills call.
argument-hint: "<task to delegate> [--mode subagents|workflow|team] [--run-id ID] [--product]"
allowed-tools: [Bash, Read, Write, Glob, Grep, Task, Workflow]
metadata:
  compliance-tier: workflow
---

# hs:workflow-orchestrate — plan the spawn before you spawn

Input: a task worth delegating to more than one agent — a research sweep, a multi-lens critique, a broad review, a decomposition. No input -> `AskUserQuestion`: what the task is, how wide, whether the findings feed a later stage, and where reports should land.

This skill does NOT do the research itself. It produces a **spawn-strategy proposal** — mode, group sizing, batch cadence, template reuse, early-write paths — presents it for approval, then drives it. It exists so delegation is planned and grouped, never a reflex of one-subagent-per-finding.

It builds ON `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md` (delegation context, write-lane preflight, base-workflow reuse) — it does not restate it. Load that rule when spawning.

## Three modes

| Mode | Shape | When |
|---|---|---|
| **A — subagents** | inline `Task` fan-out, batches of ≤2 | single stage, no barrier, few subs, no need for deterministic control flow |
| **B — workflow** | a `Workflow` script over subagents | multi-stage, needs a barrier (a stage needs all prior results), wants determinism, or wide enough (≥6 subs) that hand-driven batches get unwieldy |
| **C — agent teams** | persistent teammates that message each other + a shared task board, worktree-isolated, **mutating** | long-lived parallel *build/research* where units coordinate mid-flight (not one-shot advisory findings); requires the experimental Agent Teams flag |

A and B are one-shot advisory fan-outs — the sub reads, returns findings, exits. C is a different beast: teammates are long-lived, talk to each other, and write code. Do not model a build-many-slices-that-coordinate job as B, or a read-only findings sweep as C.

Mode is derived by `plan_orchestration.py` from the task's knobs (reproducible, not vibes) — it proposes **C only on the narrow `--coordinate --long-lived` signal**; a plain wide fan-out never misroutes to the experimental team path. Override with `--mode` when the knobs miss a reason. Mode C's experimental gate + live API: `references/mode-c-handoff.md`.

### Execution-gate policy (how the mode actually runs)

The script emits an `exec` block. Honor it — do NOT improvise a silent downgrade:

| Mode | ultracode ON | ultracode OFF |
|---|---|---|
| **A subagents** | run inline (`auto`) | run inline (`auto`) |
| **B workflow** | run the `Workflow` (`auto`) | **`confirm_required`** — a MANDATORY `AskUserQuestion` before running; **never** quietly fall back to inline subagents to dodge the ask |
| **C team** | `confirm_required` (experimental + high cost) | `confirm_required` |

`exec.no_silent_downgrade` is always true: when the right mode is workflow/team, the only sanctioned paths are *run it* (ultracode / user-approved) or *the user declines* — dropping to Mode A on your own is a policy violation.

## Process

1. **Frame + size.** Read the task and nearby context. Decide the groups (by *concern/dimension*, never one group per expected finding) and how many subs each needs. State the knobs: stage count, barrier?, determinism?, and — the load-bearing one — **fan-out→dedup vs find→verify shape**: ask "are the findings apply-ready, or will something act on them?" If a verdict, an edit, or a `--fix`
   consumes them, it is a **find→verify** task (pass `--find-verify`); a survey you will only read is fan-out→dedup. Getting this wrong ships unverified findings into a fix.

2. **Get the strategy (backing, not vibes).** Run the lead:

   ```bash
   python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/workflow-orchestrate/scripts/plan_orchestration.py \
       --run-id <slug> {--groups "research:4,critique:6,recommend:1" | --ultra [N] [--debate]} [--barrier] [--determinism] \
       [--fanout|--find-verify] [--coordinate --long-lived] [--ultracode] [--mode team] \
       [--reason "<why, cite evidence>" --strategy "<mode+template named>" --scope "<bounded>"] \
       [--token-budget <tokens> [--per-sub-cost <tokens>]] [--product]
   ```

   It emits JSON: `mode`, `groups`, `sub_count`, `batch_size`, `template`, `report_dir`, `reason`, and `exec` (the gate policy above). Pass `--ultracode` when ultracode is on, and `--coordinate --long-lived` when the task needs mid-flight coordination (Mode C). A team plan additionally carries `experimental`, `requires_flag`, and `api`.

   **`--ultra [N]` and `--debate` size a PANEL** — N independent producers plus one
   separate reader at the strongest tier, barrier on. Either is the whole argument and
   either REPLACES `--groups`; passing both a panel flag and `--groups` is refused,
   because two sources for one number produce a plan that is neither.

   They are PEER shapes of one panel, not a flag and its sub-mode: `--ultra` (5) produces
   N attempts and keeps the best; `--debate` (3) produces N positions and keeps what
   survives the argument. One emitter, because everything except that last instruction is
   identical and two copies of it drift. The emitted `panel` block carries the two
   properties both shapes live or die on: the members never see each other's output
   (shared context collapses the spread the count is paying for), and the reader who
   decides is `hs:escalation-consultant`, never one of the members.

   Reach for a panel when several answers are defensible and nothing on disk separates
   them; a task with one right answer pays N times for it. Choose the shape by what the
   run needs at the END — a choice, or an answer that survives the disagreement. Any skill
   can call this seam directly and bring the emitted plan back here for approval; the gate
   below is not optional for a panel, which is exactly the spend it exists to hold.

   Pass `--reason/--strategy/--scope` to earn `route_depth:light` in the emitted `assess` block (a cheap-fan-out signal, never a verification bypass) — omitting them (or an unbounded scope / uncited reason) routes `route_depth:agent`.

   Pass `--token-budget <tokens> [--per-sub-cost <tokens>]` to size the fan-out against a token/cost target — an advisory, non-destructive trim, never silent. Full mechanics + the Layer-1b spawn-COUNT distinction: `references/strategy-decision.md` §Token-budget-aware sizing.

3. **Present for approval.** Show the user: mode, total subs, the group→count map, the batch cadence, the template being reused, and the early-write dir. **Do not spawn before approval** — this skill's whole point. Use `AskUserQuestion` for any real fork (scope, sub-count, isolation).
   **On approval — and only then — mint the spawn-budget token.** This is the step that actually widens the provenance guard's spawn-COUNT budget from the un-ticketed session threshold to the approved `sub_count`; Step 2 did NOT do it. Never before approval (a rejected strategy must not bless a fan-out, memory `anchor-cli-self-auth-hole`), never at the strategy-emit step:

   ```bash
   python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/workflow-orchestrate/scripts/run_state.py \
       write-token --run-id <slug> --mode <mode> --sub-count <sub_count> \
       --groups '<json: [{"key": "..."}]>' --report-dir <report_dir> \
       --session <session_id>
   ```

   Use the `run-id`, `mode`, `sub_count`, `groups`, and `report_dir` from the Step-2 plan JSON, and the current `session_id`. `sub_count` is clamped to `sub_count_cap` (default 32) at write time. If a prior budget block already tripped, this is the sanctioned way to widen it — not hand-editing state.
   Full rationale + the pre-spawn checklist (incl. token TTL + no re-minting per batch): `references/spawn-discipline.md` §4.

4. **Execute — reuse before you hand-roll.**

   **Pick the SHAPE before the base — the script sizes the spawn, it does NOT make this call for you.** *Mode (A/B/C) is the spawn mechanism; SHAPE (fan-out→dedup vs find→verify) is an orthogonal axis — both bases below are Mode B (Workflow scripts).* A fan-out→dedup (`base-fanout-consolidate`) returns RAW, unvalidated findings: fine for a survey you will read, NEVER apply-ready. If the
   findings will drive a verdict, an edit, or a `--fix`/`--fix-auto`, you **MUST** use the find→verify shape (`base-pipeline-verify`) OR verify each finding yourself against the source before acting. `route_depth:light` sizes the fan-out cheaply; it **never** licenses skipping verification.
   - Mode B, fan-out→dedup → `Workflow({name:"hs:base-fanout-consolidate", args:{lenses, findingsSchema, dedupKeyFields}})`. Findings are unverified — read-only survey, not apply-ready.
   - Mode B, find→verify → `Workflow({name:"hs:base-pipeline-verify", ...})`. Each finding is adversarially re-checked before it counts — use whenever findings feed a verdict/edit/`--fix`. (Per-finding verify is the intended pattern; only cap its WIDTH — the base warns when a lens over-produces.)
   - Mode B, bespoke multi-stage → inline `Workflow({script})` (research→consolidate→critique→recommend).
   - Mode A → inline `Task` fan-out in batches of `batch_size` (≤2 per turn).
   - Mode B when `exec.gate == confirm_required` (ultracode off) → **ask first** via
     `AskUserQuestion` ("run this as a Workflow, or you'd rather I don't?"). Run the Workflow on
     yes; on no, run the reduced Mode-A fan-out the user accepted. Never skip the ask by silently
     picking A (`exec.no_silent_downgrade`). Workflows are plan-gated — resolve per `orchestration-protocol.md`.
   - Mode C → hand off execution to the Agent Teams skill (see **See also**) per the plan JSON (`TaskCreate` per group, worktree-isolated `Agent` spawn, `SendMessage` coordination, always `confirm_required`): `references/mode-c-handoff.md`.
   - Stamp which path ran: `Workflow(name)` | `Workflow(scriptPath)` | `inline-Task` | `agent-teams`.

5. **Early-write every finding.** Each spawned agent flushes its result to disk the moment it lands — an agent must not hold output in its return value alone (a stalled consolidation loses it):

   ```bash
   python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/workflow-orchestrate/scripts/write_finding.py \
       --run-id <slug> --group <group> --title "<finding>" --body "<one-para>" [--product]
   ```

   Append-only, one file per group under `report_dir` (`docs/product/_refs/<slug>/` with `--product`, else `plans/reports/<slug>/`).

6. **Consolidate in batches.** Merge per group / per direction, not all subs at once — a single giant consolidation Write stalls at idle. Small batches, mechanical dedup (reuse the base template's dedup or `cat` the group files), then rank.

7. **Arbiter checklist.** Before the report ships, answer these independently — the final report is blocked until the arbiter answers:
   - Did each job produce the requested artifact?
   - Did any job fail, timeout, or emit an uncertainty marker?
   - Do job outputs contradict each other?
   - Were all listed checks run, and did they pass?
   - Are claims supported by file paths, command output, citations, or tests?
   - Are any destructive actions proposed but not approved?
   - Are unresolved questions listed plainly?

8. **Report.** Write the consolidated output to `report_dir` (or `plans/reports/` for a review). Return the run's absolute paths.

## Backing

- `scripts/plan_orchestration.py` — deterministic mode/template/report-dir proposal (tested).
- `scripts/write_finding.py` — append-only early-write per group (tested).
- `scripts/run_state.py` — atomic `state.json` writer + `--resume` reader (skip completed, re-dispatch in-flight) (tested).
- `scripts/orchestrate_metrics.py` — append-only `orchestrate-history.jsonl` corpus, actor+ts stamped (tested).
- `harness/plugins/hs/workflows/base-fanout-consolidate.js`, `base-pipeline-verify.js` — reusable bases.
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md` — delegation context, write-lane preflight, Workflow opt-in.
- Component agent: `@workflow-orchestrator` (strategy planner). Referenced by name; never imported.

## Boundaries

- This skill PLANS and DRIVES delegation; it does not do the analysis itself, and does not block. It never spawns before presenting the plan.
- Respect the 2-subagent-per-turn limit in Mode A — fan out in batches, never the whole set at once.
- Workflows are plan-gated: absent the opt-in, fall back to inline-Task batches (mandatory, not optional).
- Write-lane: before delegating a Write-bearing task, check the target role's lane (`orchestration-protocol.md`) or delegate read-only and let the parent write.
- Do not invent a bespoke `Workflow` script when a base template fits — reuse first.
- On completion: mode + template that ran, sub count, and the absolute report paths.

## References (load on demand)

| Drawer | Content | When to load |
|---|---|---|
| `references/strategy-decision.md` | The mode A/B/C decision matrix, the exec-gate policy + override rules, token-budget sizing detail | Step 1–2 (every invocation) |
| `references/spawn-discipline.md` | Grouping, batch-consolidate cadence, early-write protocol, spawn-budget token TTL | Step 4–6 |
| `references/templates.md` | Reusing the base workflows vs authoring a new `workflows/*.js` | Mode B execution |
| `references/run-state.md` | Run-state `state.json` fields, `--resume` semantics, metrics corpus + routing-suggestion rule | Fan-out resume / metrics |
| `references/mode-c-handoff.md` | Mode C's experimental gate, live team API, and the Step-4 execution hand-off to the Agent Teams skill | Mode C selected |

## See also

- `hs:team` — executes Mode C. When the strategy resolves to Agent Teams (long-lived,
  coordinating, mutating teammates), hand it the sized plan JSON; this skill plans the mode,
  `hs:team` runs it. Soft pointer, not a co-install dependency (Teams is experimental-flag gated).
- `hs:coding-agent-orchestration` — the sibling for choosing an *external* coding agent/CLI (Codex, Cursor, Amp, Droid, OpenCode, Antigravity) when the internal partner/gemini lanes do not cover the tool. This skill owns internal harness fan-out; that one owns the cross-tool selection + handoff shape. Soft pointer, not a co-install dependency.
