---
name: hs:research
injectable: true
description: Verified technical research — pose a question, gather multiple sources, verify evidence, synthesize a report. Use before implementing or when evaluating technology or architecture.
argument-hint: "[breadth|depth] [--delegate] [topic] [--ultra [N] | --debate]"
allowed-tools: [Bash, Read, Write, Grep, Glob, Task, WebFetch, WebSearch]
metadata:
  compliance-tier: workflow
---

# hs:research — verified research

Collect, triangulate, synthesize technical information into an evidence-anchored report. **No code writing.** Output = report in `plans/reports/`.

**Evidence rule** (verified-vs-assumed, two-way Evidence Filter) in
`"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` — read first. Not repeated here.

**Probe-first ★** (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/agent-operational-discipline.md` — the priority discipline): for a load-bearing claim about how a tool/API/SDK behaves, a doc / maintainer blog / `--help` / wiki is a *hypothesis*, NOT a probe — never launder reading as "verified". When the claim is load-bearing AND measurable, escalate paper-compare → `hs:bakeoff` (a real run) rather
than ranking by argument. An unrun claim is `[ASSUMED]` (`[PRIOR]` if training knowledge), never OBSERVED.

## Modes

| Mode | When | Depth |
|---|---|---|
| `breadth` (default) | quick survey, compare multiple options | <=5 sources, parallel search |
| `depth` | deep study of one topic, implementation detail needed | <=10 sources, sequential drill |

No argument -> `AskUserQuestion`: topic, mode, max sources, deadline.

Flag `--delegate`: spawn a `@researcher` agent for multi-source work when scope is complex or user requests autonomous operation.

## Process (hard)

1. **Pose the research question** — define clearly: central question, evaluation criteria (performance / security / maturity / fit), boundary (what is NOT in scope). No question -> stop and ask.

2. **Gather multiple sources** — load `references/source-triangulation.md`; run WebSearch in parallel (<=5 times); priority order: official docs -> maintainer blog -> production case study -> tutorial. Do not build conclusions from a single source.

3. **Verify evidence** — apply the Evidence Filter: every claim must have a `URL` or `file:line` anchor. Unanchored claim -> tag `[ASSUMED]` (or `[PRIOR]` if it rests on training knowledge). Load `references/evidence-standard.md` when a detailed quality bar is needed.

4. **Synthesize + rank** — load `references/depth-modes.md` for the active mode; compare options using a trade-off matrix; give a ranked recommendation (not a flat list). **Escalation:** when the top trade-off is MEASURABLE and the choice is load-bearing, a paper matrix is weaker than a run — recommend escalating from paper-compare to `hs:bakeoff` (empirical probes) rather than ranking by
   argument alone.

5. **Generate the report** — load `references/report-format.md`; save to `plans/reports/<slug>-research-<date>.md`; end with open questions (if any). Return the absolute path.

6. **Delegate when needed** — scope > 5 independent sources or `--delegate` flag:
   - **Route+size FIRST, before any spawn:** fanning beyond a single `@researcher` (multiple angles in
     parallel) **MUST** route through `hs:workflow-orchestrate` — state `reason`/`strategy`/`scope`;
     `route_depth: light` → proceed, `agent` → escalate `@workflow-orchestrator` first. Full sizing +
     early-write commands live in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`.
   - Spawn a `@researcher` agent with full context (question, criteria, report path) — it does not
     write code, and returns the report + absolute path to the controller.

7. **Route-all (gemini partner lane, opt-in)** — before a Claude fan-out, check the partner lane: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/gemini_partner_config.py --should-route research`.
   - `route` (mode=route-all AND research ∈ `route_all_surface`) → run the sweep
     through the single chokepoint instead of a native Claude pass:
     `python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/gemini_companion.py research -p "<question>"`
     and consume its JSON (provenance-stamped).
   - `claude` (factory default — mode=partner, branch dormant) → spawn Claude as above.
   - If the companion returns `degraded`/`inert` → record **"degraded to claude"**
     LOUDLY in the report and fall back to the Claude sweep — never a silent swap.

## HARD-GATE (real wiring)

- **Evidence Filter** (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`): unanchored claim = `ASSUMED` — subsequent steps must not build on it (invariant #2).
- **Output boundary**: reports must live in `plans/reports/` (CLAUDE.md rule #3); markdown elsewhere violates the CI invariant.
- `@researcher` agent (delegate): `harness/plugins/hs/agents/researcher.md` — must exist before spawning; if missing -> fall back to self-research, record `[NO_AGENT_DELEGATE]` in the report.

## Output language

Render reports per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/output-rendering.md`: resolve `language` / `audience` / `humanize` live via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/output_config.py --resolved` (never hand-read the tracked file); the rule holds the register behavior and the evidence-invariant fence.

## Boundaries

- Do NOT write code, do NOT edit files outside `plans/reports/`.
- Do not invent facts — all information needs a source or an `[ASSUMED]`/`[PRIOR]` tag.
- When scope is too broad for one pass: prefer `--delegate` over cutting depth.
- On completion: absolute report path + list of open questions + suggested next step (implement / hs:plan / more depth).
- `--ultra [N]`/`--debate`: call `hs:workflow-orchestrate --ultra [N]|--debate --run-id <slug>` to size + drive N independent research passes over the SAME question (no shared context); `hs:escalation-consultant` synthesizes the report, and only that synthesized report ships. Approval gate is `hs:workflow-orchestrate`'s own.

