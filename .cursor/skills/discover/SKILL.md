---
name: hs:discover
injectable: true
description: Shape an ambiguous problem into a discovery brief for hs:plan — research + brainstorm chain -> direction summary, trade-offs, open questions.
argument-hint: "<problem description / feature idea> [--quick]"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob, Task, WebFetch, WebSearch]
metadata:
  compliance-tier: workflow
---

# hs:discover — shape the problem -> discovery brief

Input: a problem description or feature idea (may be very vague). No input ->
`AskUserQuestion`: what is the problem, hard constraints, who is affected, what does done look like.
Apply `"${HARNESS_BIN_ROOT:-.}"/harness/rules/intake-and-interview-discipline.md` (posture ladder + precedence) and
phrase questions per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/plain-language-phrasing.md`.

**Context isolation:** after the brief is complete, `/clear` is RECOMMENDED before calling
`hs:plan` — discovery research and debate carry heavy context that skews planning. Nothing prompts you: the advisory that watched for discover and plan in one session ships disabled, so noticing is yours. Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` section Orchestrator (mirrors handoff #5 isolation pattern).

Flag `--quick`: skip hs:research, run `hs:brainstorm --quick` instead of the full diverge/critique/converge chain. Use when the problem is simple or context is already sufficient.

**Probe-first ★** (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/agent-operational-discipline.md` — the priority discipline): a brief is only as strong as what it OBSERVED —
a load-bearing assumption about the codebase/domain that CAN be checked empirically gets RUN before it shapes the direction, not carried as fact. Reading docs / `--help` / grep is a *hypothesis*, NOT a probe; when ≥2 options split on a
MEASURABLE axis, escalate to `hs:bakeoff` (real probes) rather than guess. An unrun claim is `[ASSUMED]` (`[PRIOR]` if training knowledge), never OBSERVED.

## Process

1. **Scout + frame**: read `docs/` (incl. the canonical shared language — SSOT `docs/glossary.yaml`,
   or `glossary_register.py --root . --list`; `GLOSSARY.md` is its generated view), active `plans/`,
   relevant codebase. Summarize in 3-6 bullets for the user. Ask a scoping question if ambiguity spans
   2+ dimensions. Details -> `references/when-to-discover.md`. **Unfamiliar or large codebase — you
   MUST route to `hs:understand` FIRST** to build a codebase map before framing: discover's own scout
   is deliberately thin and WILL under-read a wide surface, and a brief framed on a mis-read codebase
   poisons every downstream option. Judgment call, not a precomputed number — if you don't already
   recognize the relevant modules, or the surface looks wide enough that a scout pass would fan out
   multiple agents to map it (the SCALE ≥ 3 agents-needed threshold defined in `scout/SKILL.md`), route
   first. On a small/familiar surface, scout in place (do not pay the `hs:understand` orchestrator
   overhead). This is a hard route, not a see-also.

2. **Research** (skip with `--quick`): call `hs:research` — central question = the framed problem; save report to `plans/reports/`. Use the absolute report path as the evidence link in the brief.

3. **Explore options**: call `hs:brainstorm --diverge` -> generate 2-4 approaches.

   Then `hs:brainstorm --critique` -> 2-lens honest attack. Finally `hs:brainstorm --converge` -> recommendation + trade-offs. (With `--quick`: replace with a single `hs:brainstorm --quick` call.)
   **Escalation:** if ≥2 surviving approaches differ on a MEASURABLE axis (latency, size, %pass) and reasoning cannot separate them, escalate to `hs:bakeoff` — build cheap probes and decide by real numbers — instead of guessing the direction in the brief.

4. **Synthesize the brief**: write `plans/<slug>/discovery-brief.md` using the template at `references/brief-template.md`. Required sections: problem framing, evidence summary (link to research report),
   option space, chosen direction + rationale, open questions, risks, explicitly OUT of scope (an empty answer here is a push-back trigger — `"${HARNESS_BIN_ROOT:-.}"/harness/rules/scope-and-contract-discipline.md`).

5. **Grid prep — OPTIONAL, only when the downstream plan will use `--grid`**: an independent
   feature/risk re-derivation, materialized and frozen NOW so `hs:plan`'s pass-2 diff-attest has
   something real to compare against (`plan/references/grid-mode.md` Two-pass macro section).
   (a) spawn `@independent-revalidator` (subagent_type `hs:independent-revalidator`) in a SEALED
   ROOM — its prompt carries **ONLY the original problem statement**, and **NEVER** the brief's
   `§features`, a plan path, or phase files. This is load-bearing prompt hygiene, not a nicety:
   if the revalidator re-reads `§features` instead of re-deriving from the problem, the checklist
   collapses to `§features` and the pass-2 diff goes empty — the exact tautology this independent
   pass exists to avoid. (b) main then runs `feature_checklist.py emit --feature ... --risk ...
   --out plans/<slug>/artifacts/feature-risk-checklist.json` to materialize + FREEZE (a
   `content_sha256` freeze) the re-derived list BEFORE handoff to `hs:plan`. (c) this is OPTIONAL
   input — a plan with no checklist still builds (graceful degrade, `grid-mode.md:99`); the whole
   point is the independence — a different agent, frozen before `§features` exists.

6. **DEC (optional)**: if discovery finalizes an architectural choice -> `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py --append-alloc ...`. Only record architecture-level decisions — not every idea.

7. **Handoff**: return the absolute path to `discovery-brief.md`. Before proposing the next step, assess the scope and route to ONE of three tiers — state the tier you picked in one line, then emit its command:
   - **Complex / multi-step** (multiple phases, wide file surface, several interacting decisions): `/hs:plan --hard --deep --tdd <path>`.
   - **Standard feature/refactor** (a real change touching more than 1-2 files but not sprawling): `/hs:plan --hard --tdd <path>`.
   - **Tiny** (typo, one-line config, pure docs, no testable code): `/hs:plan --fast <path>` (drop `--tdd`).
   Then tell the user: copy the recommended command, run `/clear` to isolate discovery context, and
   paste the command. Write the recommended command and the `/clear` reminder as **inline code** (single backticks), NOT a fenced block — terminal highlights inline `/...` commands but a ``` fence renders flat/uncolored. Tier rationale (why `--deep`/`--tdd` per tier) + chain details ->
   `references/chain-orchestration.md`.

## Backing

- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` (section Orchestrator: discover->plan; brief = "problem description + constraints" enriching handoff #1; isolation mirrors handoff #5).
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md` (brief in `plans/`; CI invariant bans markdown outside `plans/` or `docs/`).
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md` (if fan-out to subagents).
- `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py` (record DEC in step 6).
- `hs:workflow-orchestrate` — discover delegates fan-out to `hs:research` / `hs:brainstorm` (they self-route their own spawns). Route through orchestrate ONLY if discover runs its OWN extra fan-out beyond those sub-skills — at that point you **MUST** route through `hs:workflow-orchestrate` and plan the spawn strategy before spawning.
- Component skills: `hs:research`, `hs:brainstorm`, `hs:plan`, `hs:problem-solving` (when discovery is blocked).

## Output language

Render reports per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/output-rendering.md`: resolve `language` / `audience` / `humanize` live via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/output_config.py --resolved` (never hand-read the tracked file); the rule holds the register behavior and the evidence-invariant fence.

## Boundaries

- Do NOT write code, do NOT edit harness files, do NOT create a plan.
- Only output = discovery brief (markdown in `plans/<slug>/`). The brief is input for hs:plan — not a replacement for the plan.
- NO hard gate — hs:discover does not block any stage. Gates live in hs:plan -> hs:cook downstream.
- Scope creep -> record via `backlog_register.py add`, do not expand the brief.
- **When discovery is BLOCKED, you MUST route to `hs:problem-solving` before continuing — do NOT keep re-running brainstorm on the same frame** (re-running the identical frame is exactly the loop `hs:problem-solving` exists to break). BLOCKED is defined concretely, pick whichever trips first:
  - **2 full brainstorm rounds** (`--diverge -> --critique -> --converge`) leave the option
    space empty OR every surviving option dies at `--critique` (no viable direction after 2 rounds);
  - OR the frame still spans **>= 2 unresolved dimensions** after **1** scoping `AskUserQuestion`;
  - OR the same dead-end premise resurfaces **3 times** across rounds (forced-hypothesis loop).
  On any of these -> call `hs:problem-solving` with a one-line statement of WHERE the block is, take its reframe, then resume the chain from the blocked step. This is a hard route.
- On completion: absolute path to brief + list of open questions + clear next-step recommendation.

## References (load on demand)

| Drawer | Content | When to load |
|---|---|---|
| `references/brief-template.md` | Discovery brief template, required sections, example | When writing the brief in step 4 |
| `references/chain-orchestration.md` | Call order for hs:research / hs:brainstorm, flags, handoff to hs:plan | When chain details are needed |
| `references/when-to-discover.md` | When hs:discover is needed vs skippable; signs the problem is clear enough | When unsure whether discover is needed |

## Interview rigor (voice knobs)

Read three knobs from `"${HARNESS_BIN_ROOT:-.}"/harness/data/terminal-voice.yaml` (resolved by `voice_prefs.py`, injected at session start) and let them shape the discovery interview, not the brief:

- `interview_rigor` (light | standard | **deep**) — at `deep`, challenge the problem framing harder and probe more unknowns / assumptions / success-criteria gaps; at `light`, ask only the blocking questions.
- `action_prompting` (minimal | standard | proactive) — at `proactive`, offer more next-step suggestions at turn boundaries.
- `terminal_voice_level` (0–5) — sizes interview prose + follow-up count too (turn verbosity; the former `detail_level` folds in here). The brief's length stays governed by `output.yaml`.

