# Validate gate — critical-questions interview (on-demand)

Runs AFTER red-team. Goal: every decision the plan is currently SELF-ASSUMING must be explicitly finalized by the user before cook invests effort in the wrong direction.

## Two axes decide how this step runs — do not conflate them

**Axis 1 — can this run ask at all?** An environment fact, not a setting: the main thread has a TTY, a subagent does not.

| Lane | Behavior |
|---|---|
| has a TTY (main thread) | ask the user via AskUserQuestion (see Asking rules) |
| no TTY (subagent/headless) | Do NOT ask: EMIT a table "Validation Questions + suggested defaults" into `## Validation Log` (one row per question: `VL-n \| question \| suggested default \| reason`), then continue with the defaults. A later interactive session or cook can read the table and override. |

**Axis 2 — how much does policy require?** Read it, do not assume it: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/skill_config.py --resolved` → `plan.validation.{mode,minQuestions,maxQuestions,focusAreas}`.

| `mode` | Behavior |
|---|---|
| `prompt` (default) | ask |
| `auto` | answer from the plan and the repo; record each answer in the Validation Log |
| `strict` | every question must be answered before the step closes — no defaults |
| `none` | skip the validate step |

The vocabulary is CLOSED — `prompt`, `auto`, `strict`, `none`. `skill_config.py` rejects anything else, so a mode invented in prose never reaches this file's behavior; it fails the load.

The axes compose: `mode: prompt` on a lane with no TTY still cannot ask, and falls to the Validation Log table above. `mode: none` skips regardless of lane.

## Verification pass (before asking or emitting)

Re-read the plan + red-team disposition and collect: decisions with no owner (who finalizes? when?), assumptions without evidence, unweighed trade-offs, invented thresholds, **and every `[ASSUMED]` tag** (plus any load-bearing `[PRIOR]`) left by the planner (two-way Evidence Filter — rule verification-mechanism).
Each item becomes ONE question — merge duplicates, drop questions answerable by reading the repo (Scout First).

To make the scan systematic, sweep the plan text for these keyword triggers and bucket each hit into a question category — the keyword is the tell that a decision is implicit:

| Category | Keywords that flag an implicit decision |
|---|---|
| **Architecture** | "approach", "pattern", "design", "structure", "database", "API" |
| **Assumptions** | "assume", "expect", "should", "will", "must", "default" |
| **Trade-offs** | "tradeoff", "vs", "alternative", "option", "either/or" |
| **Risks** | "risk", "might", "could fail", "dependency", "blocker", "concern" |
| **Scope** | "phase", "MVP", "future", "out of scope", "nice to have" |

Tag each question with its category in the Validation Log so phase propagation knows the target section (Architecture→Architecture, Scope→Implementation Steps, Risk→Risk, etc.).

**Escalation (Architecture / Trade-offs):** when a flagged decision is *load-bearing*, *costly to reverse*, AND the alternatives differ on a MEASURABLE axis, do not just ask the user to guess — propose `hs:bakeoff` (build cheap probes, decide by numbers) and lock the plan on the winning direction. Only when no mechanical metric exists does this stay a judgment question.

## Phase-graph check (the `plan-graph.yaml` sidecar is MANDATORY)

The sidecar is authored in step 5 for every plan; if `plan_graph.py` reports `error: no plan-graph.yaml`, the plan is incomplete — author the sidecar, then re-run. Run `plan_graph.py <plan-dir>` and read its findings: dependency **cycles**, **ordering hazards** (a prereq touches a file a later phase only creates), **parallel batches** (topological antichains), and **shared-file conflicts**
(two same-batch phases own the same path → must serialize). This is **read-only / detection only** — surface the findings to the planner; never auto-edit the plan (red line: no AI rewrite after approval). A cycle or a shared-file conflict is a question for the user, not a silent fix.

## Decision-consistency check (phase spec vs recorded decisions) — MANDATORY

Cross-check every phase spec against the plan's OWN recorded decisions (the `## Validation Log` + any DEC the plan cites). A phase instruction that CONTRADICTS a finalized decision is the exact gap that ships a plan whose code will violate a choice the user already made — the keyword sweep above never catches it, because each side reads fine in isolation.
For each recorded decision, scan every phase file for an instruction that breaks its promise (worked example: a decision says "on Windows, writes still work but unlocked" while a phase spec says the lock helper "raises" on Windows and every writer is wrapped in it → every write command crashes on Windows, violating the decision).
Read-only / detection only: surface a contradiction as a BLOCKING question, never auto-edit. A found contradiction is Failed > 0 — resolve before the plan is ready.

## Consistency sweep (runs after red-team, and AGAIN here)

Re-read `plan.md` and EVERY phase file end to end — not the diff, the whole thing. Hunt three classes:

- **stale terms** — a name the plan used before a decision reversed it, still sitting in a later phase.
- **reversed decisions** — an early phase that assumes what a later decision overturned.
- **name-honesty / SRP** — does each new file/module/function name describe its real responsibility accurately AND completely? A name that covers half of what the thing does is how the next reader is misled, and a name that covers more than it does is how a second responsibility gets smuggled in.

A new load-bearing term is REGISTERED, not hand-written: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/glossary_register.py --root . --add` (SSOT `docs/glossary.yaml`). Never hand-edit the rendered view — the register stamps it.

Pass condition: **0 unresolved contradictions** before the plan is recommended for cook.

## Present before asking (MANDATORY)

Before the first question, output a brief visible recap in the response: the plan's phases, the key decisions, and the assumptions/risks this interview will probe (5–10 bullets). The interview often runs in a fresh session where the user has not seen the plan body — a question referencing unseen plan content appears to come from nowhere. Extended-thinking reasoning is invisible; externalize it
first.

Write each question and option to stand alone: name the plan section or decision it refers to instead of assuming earlier turn text is still on screen.

## Asking rules

1. Ask via AskUserQuestion; place the recommended option FIRST and mark it "(Recommended)". When the question is about *approving a plan/artifact* (not choosing config), offer `Direct Review (Plannotator)` first (rule `"${HARNESS_BIN_ROOT:-.}"/harness/rules/plannotator-review-gates.md`): `annotate` on `plan.md`, and annotations return as decisions.
2. At most 4 questions per round; open a new round if more remain. A long interview is fine — a wrong decision is costly.
3. User overriding the recommended option is normal: record it, do NOT argue back unless there is new evidence (rule `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`, "User decision").

## Recording results

- **Validation Log in plan.md, verbatim decisions** (table: VL-n | topic
  | decision | record DEC?): the log is the source of truth when context is compressed.
- Architecture decisions -> DEC via `decision_register.py --append-alloc` immediately. Example:
  arming the axis-selection + diff-attest gates on a coverage-grid (`plan/references/grid-mode.md`)
  is an architecture-level decision recorded as a DEC here at validate, not embedded in code.
- Propagate every decision into the affected phase files (mark as updated).
- Gate pass condition: **Failed: 0** — no blocking question remains open. Unresolved non-blocking items may stay; record clearly which wave will resolve them.
