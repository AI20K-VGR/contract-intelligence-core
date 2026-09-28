# Orchestration protocol (on-demand)

Load when spawning subagents or coordinating parallel work. Backing implementation
for skill `hs:team`; matches the harness multi-agent primitives (`claims.py`,
`SendMessage` + Task*).

## Delegation context — required in every subagent prompt

task · files allowed to read · files allowed to modify · acceptance criteria ·
constraints · work-context path · reports path (default `plans/reports/`). Include
env (CWD, OS) when handing off work.

## Write-lane preflight — before delegating a Write-bearing task

Write scope is a DENY-LIST: a subagent writes anywhere EXCEPT the hard floor (the
protected core + the `harness/**` binary, carve `harness/tests/**` only). So
project-source writes just work — a mismatch only happens when a task hands a subagent a
HARD-FLOOR target (guard code, `harness/**`, `.git`, secrets). Before handing such a
task, either (a) keep the floor write on the parent, or (b) delegate read-only (the agent
returns the content, the parent writes it). Read-only agents (no Write tool) never reach
the gate.

## Ultracode Workflow — shared base workflows + mandatory fallback

The Workflow tool runs a deterministic orchestration script over subagents. The harness
ships reusable base scripts so consumers do not each hand-roll one.

- **Plan the spawn first.** For a non-trivial fan-out (research sweep, multi-lens critique,
  broad review), skill `hs:workflow-orchestrate` (agent `hs:workflow-orchestrator`) is the
  delegation planner: it derives subagents-vs-Workflow, groups the fan-out by concern, sizes
  the sub-count, sets the batch-consolidate cadence, and lays out early-write report paths —
  then presents the plan for approval before anything spawns. Route delegation design through
  it instead of hand-sizing a fan-out ad hoc.
- **Common-workflow dir.** Base workflows live at `harness/plugins/hs/workflows/*.js`
  (plugin-root auto-load — self-contained, never touches `.claude/`). Two shapes ship:
  `base-pipeline-verify` (find → verify, no barrier — for review-shaped consumers) and
  `base-fanout-consolidate` (fan-out N lenses → mechanical dedup — for multi-lens
  consumers like critique / predict / scout / security-scan).
- **Named vs inline.** Prefer `Workflow({name})` — the portable, registry-resolved path.
  Plugin workflows register under the **`hs:` namespace**: call `hs:base-pipeline-verify`
  / `hs:base-fanout-consolidate`, NOT the bare `meta.name` (the bare name does not
  resolve). A registry that has not picked up a new workflow yet (no reinstall+restart)
  → `Workflow({scriptPath:"<plugin-root>/workflows/<file>.js"})`. A call that needs a
  bespoke per-run script the base cannot model → inline `Workflow({script})`.
- **Inputs are DATA, not callbacks.** The VM forbids passing functions across the
  boundary, so a base takes its spec as JSON `args` (lens prompts, a `{{field}}` verify
  TEMPLATE the base renders, JSON Schemas). A base is depth-1 (it never calls another
  base).
- **Mandatory fallback.** Workflows are plan-gated (entitlement can be off), so every
  consumer MUST keep a non-Workflow inline-Task fan-out and **stamp which path ran**
  (`Workflow(name)` | `Workflow(scriptPath)` | `Workflow(inline)` | `inline-Task
  fallback`). A consumer with no fallback breaks wherever the entitlement is absent.
- **Determinism trap.** The VM aborts (`errorCode:4`) on `Date.now()`, `Math.random()`,
  or `new Date()`. Retry backoff is attempt-indexed (`base * 2**attempt` + `setTimeout`),
  never wall-clock jitter. Also: no control characters in a script (the approval dialog
  rejects them) and no `import`/`require`/`eval`/`new Function`/fs.
- **Governance lives at the tool boundary, not in the script.** A base's `agent()` spawns
  a REAL subagent (`agent_type="workflow-subagent"`), so its tool calls pass through the
  SAME PreToolUse/PostToolUse hooks (gate_stage / write_guard / telemetry) as any
  other subagent. Do not embed governance in the script — it is both
  impossible (the VM is sandboxed) and redundant.
- **Write scope (deny-list).** `workflow-subagent`, like every subagent, writes anywhere
  EXCEPT the hard floor. A consumer `--fix` (code-review / security-scan) that edits
  project source works out of the box — no lane, no overlay. It is refused only the hard
  floor (guard code, `harness/**` binary, `.git`, secrets); a floor write stays on the
  parent. The block-reason names the path at block time, so discovery is just-in-time.

## Route at the execution step

`hs:workflow-orchestrate` is the standard front door for a fan-out. These four clauses
are the single source the enforce-skills propagate from — do not re-derive them per skill.

1. **Route at the numbered step, not an end section.** Declare the
   `hs:workflow-orchestrate` route INSIDE the numbered execution step where the fan-out
   actually happens — never only in a trailing standalone section. A route parked at
   end-of-file is read as optional: the numbered workflow → base-template chain is
   self-contained and skips it. The route is the layer BEFORE the spawn line, not a
   replacement for it.
2. **Fixed vs variable fan-out.** For a **config-fixed** set (critique lenses, predict's
   five personas, security-scan's personas, code-review levels) `hs:workflow-orchestrate`
   has nothing to *size* — its value is the **challenge layer** (is this fan-out plan
   sound?), so route cheaply via the script's heuristic bypass. For a **variable** set
   (research angles, open scope) the route also sizes and groups — the count is unknown
   until routed.
3. **reason / strategy / scope contract.** The caller states three fields before routing —
   `reason` (concrete, citable trigger), `strategy` (mode + base template + group→count +
   barrier/parallel/isolation), `scope` (file-surface/SCALE + variable-vs-fixed count).
   `plan_orchestration.py` REFLECTS them verbatim and emits an advisory `assessment`
   (complexity / confidence / route_depth); the skip-vs-escalate decision stays with the
   model — the script never gate-blocks the choice. `route_depth:light` proceeds via the
   base; `route_depth:agent` escalates the `hs:workflow-orchestrator` agent before spawning.
4. **Three structural anti-waste mechanisms.** group-cap (wave-2 spawn ≤ the cross-cutting
   cap — never one sub per finding), batch-consolidate (per-group mechanical merge — never
   one giant Write), early-write (each sub flushes via `write_finding.py`). The
   cross-cutting caps live in ONE source — `harness/data/orchestration.yaml` (read via
   `orchestration_config.py`) — not per-skill prose. The base workflows surface a
   structural warning (visible in the run log) when a run exceeds the cap or omits
   early-write; they do not throw. This layer is **structural + visible**, not an absolute
   block.

**Commands — the one runnable home.** The enforce-skills point HERE for the exact commands
instead of re-spelling bare script names (which are not on PATH and live in two different
dirs — a copy-paste trap). Both scripts need a `python3 <path>` prefix:

```bash
# resolve the cross-cutting group cap for N distinct concerns (top-level scripts dir)
python3 harness/scripts/orchestration_config.py --group-cap <N>
# size + score the fan-out (skill-local script — full path, it is NOT on PATH)
python3 harness/plugins/hs/skills/workflow-orchestrate/scripts/plan_orchestration.py \
    --run-id <slug> --groups <k:n,...> --reason "…" --strategy "…" --scope "…" [--group-cap <n>]
# a PANEL instead of hand-sized groups: N independent producers + one separate reader
python3 harness/plugins/hs/skills/workflow-orchestrate/scripts/plan_orchestration.py \
    --run-id <slug> {--ultra [N] | --debate} --reason "…"
```

A panel is the seam ANY skill calls when several answers are defensible and nothing on
disk separates them — it replaces `--groups` and refuses both together. Two peer shapes:
`--ultra` keeps the best of N attempts, `--debate` reconciles N positions. Pick by what
the run needs at the end. Bring the emitted
plan back to `hs:workflow-orchestrate` step 3 for the gate; N candidates at the strongest
tier is precisely the spend that gate holds. A task with one right answer pays N times for
it, so the entry condition is a real fork, never low confidence.

Read `route_depth` from the JSON: `light` → proceed via the base; `agent` → escalate the
`hs:workflow-orchestrator` agent. Pass the resolved cap as `groupCap` + an `earlyWrite:{runId}` to
the base. A caller wanting the full walkthrough opens `hs:workflow-orchestrate` (its step 2).

## Context isolation

- Do NOT pass the full conversation history; summarize ONLY the decisions needed for
  the subtask.
- Give exact file paths instead of "look around the repo" — unless scouting is the task.
- Keep coordination, merge decisions, and human approvals in the controller session.

## Parallel work — safety conditions

Only run in parallel when **file ownership is clear** and integration points are known.
Do not edit in parallel: the same file, a generated artifact, a migration sequence, or
shared config. Ownership is split 1-winner via `harness/scripts/claims.py`. Advisory
subagents (report-only) do NOT mutate plan/code unless explicitly assigned to do so.

## Model discipline when spawning Explore

`Explore` inherits the session model (Opus post-CC-2.1.198), which is expensive for
file-finding — a Haiku-class job. **Every Explore spawn MUST set `model:"haiku"`.** This is
enforced, not just advised: `model_guard` (PreToolUse `Agent|Task`, compliance,
default **block**) blocks a mis-modeled Explore spawn; the posture lives in
`harness/data/model-policy.yaml` (`mode: block|advisory|off`, with a per-agent override, and
a whole-file `HARNESS_MODEL_POLICY` dev override). Genuinely need Opus for a search? Record a
reason via `harness/scripts/model_override.py --grant --session <id> --reason ...` — the gate
consumes that marker and allows the spawn. Do NOT route around the pin with `general-purpose`
(it inherits Opus and the gate cannot see that intent — the honest mitigation is this rule and
the block message, not the exit code). A session-less/AFK spawn cannot use the marker; lower
`mode` instead.

## Model escalation when a subagent hits a hard wall

The opposite direction of the Explore pin: `model_guard` only ever LOWERS a spawn's
model, but a core agent stuck below `fable` may need to RAISE it. The two are opposite
directions and do not conflict.

### When to escalate

When the current session or a subagent runs on a model below `fable` (e.g. `opus`, `sonnet`,
`haiku`) and hits a hard problem — **repeated failed attempts, a high-stakes design fork,
requirements that stay fuzzy after scouting, or a phase boundary whose outcome changed the
downstream risk (a go/no-go the next phase depends on)** — spawn the `escalation-consultant`
agent for counsel instead of switching the session model. The phase-boundary case is a judgment
call, not a mechanical trigger: most phase completions warrant nothing (see the domain's own
Observe checkpoint), reach for it only when the phase's actual outcome — not its mere
completion — changed what "done" means for what follows. It runs autonomously on the strongest
available model and returns full advice in one reply (no interview, no user round-trips). Give
it the task, evidence gathered so far (`file:line`), approaches tried, and the specific
question. It advises only; the caller stays responsible for the implementation.

Two adjacent seams reach the same consultant and are not interchangeable. `hs-run <domain>
next` rewrites its state to `stuck` once the same non-terminal answer repeats
(`advice_escalation` in `harness/data/hs-run-registry.yaml`; `--advice` forces it), which
answers *this run is going in circles*. the panel above answers *there are several good
answers and I need them compared*. The first is a wall, the second is a fork.

Do not escalate on the first stumble. The bar is a genuine wall: stuck AND a repeated failure
(≥N tried) AND not resolvable by more scouting. For interview-driven advisory with user
participation, use `hs:advise` instead — the escalation-consultant never asks back.

### Fallback — catch-error, retry the fallback model

The spawn inherits `fable`. Fable is routed through a dedicated CCS instance; when one account
hits its quota the proxy rotates accounts transparently (the first layer — the caller does
nothing). The catch-error fallback is the backstop for when that layer is exhausted:

- Spawn succeeds and the counsel comes back on `fable` → use it.
- The spawn or its turn **throws** (a quota/entitlement error surfaced as `429` / `401` /
  `402`, or the model is unavailable) → **retry once with an explicit `model: opus`.** This is
  the main fallback path.
- (Secondary, optional) If CCS silently swapped the model, read the model at the transcript
  tail; if it is neither `fable` nor `opus`, consider a single opus retry.

This is not a hard failure: prefer `fable`, catch the error, retry `opus`, continue. The
`escalation-consultant` carries `mode: advisory` in `harness/data/model-policy.yaml`, so the
explicit `opus` retry is nudged, never blocked. The agent's own runtime note also degrades
gracefully to the runtime default when `fable` is unavailable.

## Status protocol

Require each subagent to end with:

```text
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Summary: 1-2 sentences
Concerns/Blockers: optional
```

`BLOCKED` / `NEEDS_CONTEXT` means change context, scope, or approach. Do NOT repeat
the same failing prompt unchanged. Multi-session or team work uses skill `hs:team`
and communicates via `SendMessage`.
