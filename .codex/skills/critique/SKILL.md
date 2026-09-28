---
name: hs:critique
injectable: true
description: Multi-lens adversarial critique — fan independent lenses at an artifact, consolidate into one ranked verdict. Advisory by default; gate mode writes a machine verdict; optional --loop refute cycle.
argument-hint: "<artifact path / idea> [--gate] [--advisory] [--loop] [--lenses a,b,c]"
allowed-tools: [Bash, Read, Write, Glob, Grep, Task]
metadata:
  compliance-tier: workflow
---

# hs:critique — multi-lens critique -> consolidated verdict

Input: an artifact to challenge — a plan, a decision, a design, a code diff, or a stated approach. No input -> `AskUserQuestion`: what is under critique, where it lives, what "done" looks like.

Fans SEVERAL independent lenses at one artifact; merges findings into one ranked verdict. Does not replace single-lens `hs:brainstorm --critique` (one advisor, one pass); use `hs:critique` when one perspective isn't enough and lenses must not see each other's reasoning. Tone stays neutral/professional — lenses attack the artifact, never the author.

## Modes and flags

| Flag | Effect | When to use |
|---|---|---|
| _(default)_ | advisory: lens fan-out -> consolidate -> report. Never blocks. | challenge an artifact before committing to it |
| `--gate` | also write `critique-consensus.json` (verdict PASS / PASS_WITH_RISK / BLOCKED) | a downstream stage opts into the critique gate (see Boundaries) |
| `--advisory` | force report-only for this run, even if `critique.yaml` says `mode: gate` | override config once |
| `--loop` | bounded critique -> refute -> consolidate cycle | a contested verdict where a defense pass may change the outcome. Detail -> `references/refute-loop.md` |
| `--lenses a,b,c` | override the lens set from `critique.yaml` | unusual artifact, or a specific perspective set is wanted |

Default mode comes from `"${HARNESS_BIN_ROOT:-.}"/harness/data/critique.yaml` (`mode:`, default advisory). `--gate`/`--advisory` override it for one run.

## Process

1. **Frame + classify**: read artifact + nearby context; classify type (plan/decision/design/code/diff); pick lens set from `"${HARNESS_BIN_ROOT:-.}"/harness/data/critique.yaml` (`lenses:` by type; unknown -> `default`). `--lenses` overrides. Summarize scope in 3-6 bullets.

2. **Fan out the lenses**: each lens runs read-only and returns its own report AND the normalized JSON finding contract; lenses do not see each other's output.
   - **Route first through `hs:workflow-orchestrate`** (before any spawn) — state `reason` (why this
     critique fan-out), `strategy` (mode + base + lens→count), `scope` (artifact surface + fixed lens
     count). This lens set is **config-fixed**, so the route is the cheap challenge layer: consume
     `route_depth` — `light` → proceed via the base below; `agent` → escalate the
     `@workflow-orchestrator` agent before spawning. The exact sizing commands + the
     `groupCap`/`earlyWrite` handoff live in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`.
   - **ultracode opt-in present** → orchestrate the fan-out (+ mechanical pre-dedup) via the shared
     `Workflow({name:"hs:base-fanout-consolidate", args:{lenses, findingsSchema, dedupKeyFields}})`
     (deterministic fan-out; `scriptPath` if the name is not registered in this install). Lens
     prompts are built as data, not callbacks. Step 3 below still runs for ranking + verdict.
   - **opt-in absent** (mandatory fallback — Workflows are plan-gated) → inline-Task fan-out in
     **batches of ≤2** (respect the 2-subagent-per-turn limit), exactly as today.
   - **Stamp** the path that ran: `Workflow(name)` | `Workflow(scriptPath)` | `inline-Task fallback`.
     Resolve the opt-in per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`.
   - **Give each lens** the artifact (path or content) + the scope label + the finding contract below.
     Do NOT pass other lenses' output, your own running synthesis, or the eventual verdict — lenses
     run blind to each other; a lens reading another's findings would anchor instead of re-deriving.
   - **The finding contract** — every lens ends its report with this normalized JSON array so the
     consolidator does not parse prose:
     ```json
     [
       { "lens": "<agent-name>",
         "anchor": "<file:line | reproduction command | triggering input>",
         "finding": "<neutral one-line statement of the problem>",
         "why_it_matters": "<the consequence if unaddressed>",
         "fix": "<the cheapest fix, or the condition under which it is acceptable>",
         "severity": "blocker | major | minor",
         "status": "proven | suspected",
         "fingerprint": "<optional, sha256[:16] via dismissals_store.fingerprint() -- omit when anchor is not file:line>" }
     ]
     ```
     `finding` stays neutral (no sarcasm/escalation/author remarks); `anchor` is real evidence, never
     invented (no anchor -> not a blocker); `why_it_matters` + `fix` both non-empty or the consolidator
     drops the finding; a lens with nothing reproducible returns `[]` + a short "residual risks" note.
     `fingerprint` is computed by the consolidator (not the lens), best-effort -- see
     `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/agents/critique-consolidator.md`.
   Lens-set rationale by artifact type -> `references/critique-protocol.md` (only needed if the config-driven pick in step 1 needs justifying).

3. **Consolidate**: hand all lens findings + any prior critique reports + the scope to the `hs:critique-consolidator` agent. It dedups across lenses, ranks by severity, attaches repeat-offense metadata, flags DEC-worthy items, and proposes one verdict.
   Read `"${HARNESS_BIN_ROOT:-.}"/harness/rules/scoring-rigor-contract.md` before ranking -- every severity/verdict label pins to an existing scale (finding `blocker|major|minor`, plan red-team `C/H/M/L`, gate verdict `PASS|PASS_WITH_RISK|BLOCKED`), never a 4th vocabulary.
   Detail -> `references/consolidation-contract.md`.

4. **Refute (only with `--loop`)**: give the surviving blockers a defense pass that tries to rebut each with evidence, re-consolidate, and stop on convergence or `loop.max_rounds`. Detail -> `references/refute-loop.md`.

5. **Report**: write the consolidated critique to `plans/reports/<slug>-critique-report.md`.

6. **Gate artifact (only in gate mode)**: write the consolidator's verdict to
   `plans/<active-plan>/artifacts/critique-consensus.json` (schema
   `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-critique-consensus.json`). Enforcement ships OFF: shipped
   `stage-policy.yaml` lists `critique-consensus` at no stage → spine-only install never blocked. An org opts in
   by adding `critique-consensus` to a stage's
   `requires:` (verdict must then be `PASS`). Skill itself never blocks — `stage-policy.yaml` does.

7. **DEC-worthy**: for each flagged item, `AskUserQuestion` (Keep / Change / Hybrid). On a confirmed architecture decision -> `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py --append-alloc ...`.

## Backing

- `"${HARNESS_BIN_ROOT:-.}"/harness/data/critique.yaml` (mode, lens sets by artifact type, loop bound, verdict taxonomy).
- `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-critique-consensus.json` (gate-mode verdict shape).
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` (row: `hs:critique -> artifact (critique-consensus.json)`).
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` (Evidence Filter the lenses and consolidator obey).
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md` (lens fan-out / batching).
- `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py` (record a DEC in step 7).
- Component agents: `@red-teamer`, `@independent-revalidator`, `@code-reviewer`, `@brainstormer` (lenses), `hs:critique-consolidator` (merge). Referenced by name; never imported.

## Output language

Render reports per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/output-rendering.md`: resolve `language` / `audience` / `humanize` live via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/output_config.py --resolved` (never hand-read the tracked file); the rule holds the register behavior and the evidence-invariant fence.
Tone stays neutral and professional — no escalating register, no remarks about the author.

## Boundaries

- Lenses + consolidator are READ-ONLY advisory agents: attack/report only, never edit code/plans/artifacts. Skill controller writes the report + (gate mode) the artifact.
- Respect the 2-subagent-per-turn limit: fan lenses in batches, never spawn the whole set at once.
- Skill never blocks directly: writes `critique-consensus.json`; stage policy enforces. Enforcement ships OFF — shipped policy lists `critique-consensus` at no stage; opt in via a stage's `requires:` in `stage-policy.yaml` (write-guarded, edit outside session) → verdict must then be `PASS`.
- Only output = the critique report (markdown in `plans/reports/`) plus, in gate mode, the verdict artifact. Do NOT implement fixes here.
- Scope creep (a fix worth doing) -> note it in the report and record via `backlog_register.py add`; do not start building.
- On completion: absolute path to the report + the verdict + any DEC-worthy items.

## Observe checkpoint (end-of-work)

When critique is done, emit at most ONE closed-vocab signal — valid terms here:
`thin-evidence`, `red-team-reopened`, `gate-repeat-block`. Most runs emit nothing.

Shared contract (when to emit, when to stay silent, the invocation, the two-output nudge):
`"${HARNESS_BIN_ROOT:-.}"/harness/rules/observation-signal-emit.md`.

## References (load on demand)

| Drawer | Content | When to load |
|---|---|---|
| `references/critique-protocol.md` | Why each lens set is recommended per artifact type (rationale behind `critique.yaml`) | Only if the config-driven lens pick needs justifying |
| `references/consolidation-contract.md` | Consolidator inputs/outputs, dedup, severity, repeat-offense, verdict rule | When consolidating (step 3) |
| `references/refute-loop.md` | The `--loop` critique -> refute -> consolidate cycle and its convergence rule | Only with `--loop` (step 4) |
| `references/grid-consume.md` | Fold a coverage-grid `reject` into one consolidation finding (advisory; grid never forces the verdict) | When a `coverage-grid` artifact exists for the target |

