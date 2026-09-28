# Strategy decision — subagents (A) vs workflow (B) vs agent teams (C)

The mode is derived, not chosen by feel. `plan_orchestration.py` applies the rules below; this drawer is the human-readable version + the override cases the script cannot judge.

## Decision rules (what the script encodes)

Pick **Mode C (agent teams)** FIRST when BOTH hold (the narrow case):

- **Mid-flight coordination** (`--coordinate`) — the workers must message/challenge each other WHILE running, not just report at the end (adversarial debug, cross-layer build where slices negotiate).
- **Long-lived** (`--long-lived`) — the work spans a long build/research, not a one-shot fan-out.

Both required, or it is not a team job. Agent Teams is CLI-only + **experimental** (gated by `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`), so the script always returns `exec.gate = confirm_required` for C — it is never auto-launched. A plain wide fan-out is B, not C.

Else pick **Mode B (Workflow)** if ANY hold:

- **Multi-stage** — the work is stages that hand off (research → consolidate → critique → recommend).
- **Barrier** — a stage genuinely needs ALL prior results before it can start (dedup across the full set, early-exit on zero, "compare against the other findings"). If no stage needs the whole prior set, it is NOT a barrier — model it as a pipeline, not a synchronized fan-out.
- **Determinism** — the control flow (loops, conditionals, budget-scaled fan-out) must be reproducible and not model-driven.
- **Width** — ≥6 subs. Beyond that, hand-driven inline batches cost more attention than they save.

Otherwise **Mode A (subagents)** — a single-stage inline `Task` fan-out in batches of ≤2.

## Execution gate — how the chosen mode actually runs (`exec` block)

See SKILL.md's "Execution-gate policy" table for the mode × ultracode → `auto`/`confirm_required` matrix and the `no_silent_downgrade` rule — this reference does not repeat it.

## Rubric: reason / strategy / scope + the advisory assessment

The caller states three fields before routing; the script REFLECTS them verbatim under `inputs` and derives an `assessment`. This is the **challenge layer** — a hollow field set scores low and routes to the `hs:workflow-orchestrator` agent; a concrete one earns the cheap `light` bypass. The score never blocks (D2): it is a signal the model reads, then decides.

**The three fields:**

- `reason` — the concrete, citable trigger for this fan-out (name the skill / effort / a count — `hs:critique`, `high`, `12 files`). A vague "just do it" scores zero on evidence.
- `strategy` — the mode + base template + group→count (e.g. `subagents base-fanout-consolidate a:1,b:1`). Must NAME a mode AND a template to count.
- `scope` — the file-surface / SCALE + variable-vs-fixed count. Must be **bounded** (a number or a path); `all` / `everything` is unbounded and scores zero.

**`complexity` (0..6 count)** — one point each: `stages>1`, `barrier`, `sub_count>=6`, `over_cap` (sub_count over the pre-resolved group cap), variable scope (scope not bounded), a write-lane strategy (subs mutate files). Higher = more reason to escalate.

**`confidence` (0..4 count)** — one point each: reason has a cite-token, strategy names a mode AND a template, scope is bounded, and the red-flag set is empty. Content-derived, not presence-derived — three present-but-hollow fields still score low (red-team I2).

**`route_depth`** — `light` when `complexity<=2` AND `confidence>=3` AND all three fields are present; otherwise `agent` (the three conditions are jointly necessary and sufficient). `light` proceeds via the base template below; `agent` escalates the `hs:workflow-orchestrator` agent before spawning.

**Red flags (`flags[]`, each blocks `light`):** `missing-fields`, `over-cap`, `one-sub-per-finding` (groups == sub_count and sub_count large), `unbounded-scope`, `no-evidence` (reason present but no cite-token).

**`cap` / `over_cap`** — the group cap is PRE-RESOLVED by the caller via `orchestration_config.py --group-cap <concerns>` and passed in with `--group-cap <int>`; the clamp formula lives in that one config module, never here. Absent `--group-cap` → `cap:null`, `over_cap:false` (the cap scoring is off — full back-compat).

## Token-budget-aware sizing (`--token-budget`)

This is the token/cost axis (how many output tokens the fan-out will burn), NOT the Layer-1b spawn-COUNT budget the provenance guard enforces — two separate things. A fan-out sized only by concern is blind to how much token budget is left — 30 subs on a near-empty budget is the classic own-goal. Pass `--token-budget <tokens>` and the plan gains a `token_budget` block:

- `capacity = token_budget // per_sub` (default `per_sub` = 100k output tokens, matching the Workflow tool's own `budget.total / 100_000` heuristic; override with `--per-sub-cost`).
- `within_budget` = does the requested `sub_count` fit under `capacity`.
- `trim_advice` (only when over) = a concrete fitted map: floor 1 sub/group, remainder handed out widest-original-first so wide groups stay wide; if `capacity` can't seat one sub per group the tail groups are dropped by name; if it affords zero, every group is dropped with a raise-the-budget note.

The trim is **advisory + non-destructive** — the emitted `groups`/`sub_count` keep the original ask. Present the requested map AND the trimmed map; the user confirms the cut. Silently shrinking the fan-out to dodge the ask is the same violation as silently downgrading the mode.

**`plan_orchestration.py` only SIZES the fan-out — it does NOT mint the spawn-budget token.** This `token_budget` block is the token/cost axis; the Layer-1b spawn-COUNT budget the provenance guard blocks on is a different thing. Running this script leaves the guard's budget at the
un-ticketed session threshold (`threshold` in `"${HARNESS_BIN_ROOT:-.}"/harness/data/spawn-provenance.yaml`, the SSOT); the wider spawn budget is minted separately in SKILL.md's Step 3, on approval. Do not read "strategy recorded" here as "budget widened."

Which lane actually blocks: only the Workflow one. `spawn_provenance_workflow_guard` reads
the width a single Workflow call declares in its own script and blocks on that. The Agent|Task
session-window twin is gone — it counted spawns on a sliding wall clock, which over-blocked
legitimate sequential fan-out. So a block today is about ONE call being too wide, never about
how many agents the session has already spawned.

For a deep task, hand the framing to the `@workflow-orchestrator` agent instead — same structured plan, repo-read behind it.

## Overrides the script cannot see

- **Force A even when wide**: the subs are truly independent one-offs and you want their raw text back in THIS context (no consolidation stage). Pass `--mode subagents`.
- **Force B even when narrow**: you want the run journaled + resumable (long, expensive subs where a crash mid-run must not lose the completed ones). Pass `--mode workflow`.
- **Worktree isolation**: when subs mutate files in parallel and would collide, run them with `isolation:"worktree"` (Workflow `agent()` opt) or hand each a `hs:worktree`. Expensive (~200–500ms + disk per agent) — only when writes actually conflict. Read-only research never needs it.

## Shape within Mode B: fan-out→dedup vs find→verify (a reasoning step, not a flag)

`plan_orchestration.py` sizes the spawn; it does NOT decide whether your findings need verifying. That call is yours, and it is the one most easily skipped:

- **fan-out→dedup** (`base-fanout-consolidate`) — N lenses find, then a mechanical JS dedup. The output is a RAW, unvalidated finding set. Correct for a **survey you will read** and judge yourself. It is NOT apply-ready.
- **find→verify** (`base-pipeline-verify`) — each finding is re-checked by an adversarial verify pass before it counts. Use this **whenever a verdict, an edit, or a `--fix`/`--fix-auto` will act on the findings**. Unverified findings driving an auto-fix ship false positives into the code.

Decision rule: *"will anything ACT on these findings?"* Yes → find→verify (or verify each finding yourself in the main loop before acting). No → fan-out→dedup. `route_depth:light` answers "how big is the spawn", never "may I skip verification".

## Anti-patterns (why this skill exists)

- **One sub per finding (the FIND stage).** A finding is an *output*, not a *unit of work*. Do not spawn one sub per expected finding to PRODUCE them — group by concern/dimension; each sub produces many findings. 12 findings ≠ 12 finder subs. (This is distinct from the verify stage below.)
- **An UNCAPPED verify wave (the VERIFY stage).** Verifying each finding with its own adversarial agent is the *intended* pattern (`base-pipeline-verify` does exactly this — find → verify-each), NOT the anti-pattern above. The only risk is unbounded WIDTH: a lens that returns 100 findings spawns 100 verify agents. The base emits a `WARN verify-cap` log when a lens's findings exceed the cap —
  heed it and regroup the finders so the wave stays bounded. Per-finding verify is correct; a runaway count is the thing to cap.
- **Unverified findings into a fix.** Picking fan-out→dedup for a task that then `--fix`es its findings auto-applies raw, unverified output. Match the shape to whether anything acts on the findings (above).
- **Barrier by reflex.** `parallel()` between every stage wastes the fast subs' idle time. Default to `pipeline()`; use a barrier only for a real cross-item dependency (see above).
- **Consolidate-all-at-once.** One giant merge Write stalls at ~180s idle. Consolidate per group.
- **Spawn before approval.** The plan is cheap; a wrong 12-sub fan-out is not. Present, then spawn.
