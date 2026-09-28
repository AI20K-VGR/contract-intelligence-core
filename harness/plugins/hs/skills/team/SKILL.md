---
name: hs:team
injectable: true
description: "Orchestrate parallel Agent Teams — research, cook, review, debug with multiple independent teammates."
argument-hint: "<template> <context> [--devs|--researchers|--reviewers N] [--delegate]"
allowed-tools: [Bash, Read, Write, Glob, Grep, Task]
metadata:
  compliance-tier: workflow
---

# hs:team — Agent Teams orchestration

Run multiple independent Claude Code sessions. Each teammate has its own context window, reads the project CLAUDE.md + skills, and coordinates through a shared task list and messaging.

**Requirement:** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (or the `--agent-teams` flag), plus the server gate `tengu_amber_flint` (default on). Experimental research preview, CLI-only; the Python `claude-agent-sdk` exposes no team primitives.
**Requirement:** CLI terminal — the team task board (`TaskCreate`/`TaskUpdate`/`TaskGet`/ `TaskList`) is disabled in the VSCode extension.
**API note (CC v2.1.178+):** the team is **implicit — one per session, session-derived name**. No `TeamCreate`/`TeamDelete` (removed, filtered out of the tool surface). A teammate is spawned by passing a `name` to the `Agent` tool — that `name` parameter only appears when the Agent Teams gate is on; omit it and you get a plain subagent.
**Model:** Per-teammate — the lead picks a model for each teammate at spawn (e.g. Sonnet for devs, Opus for a reviewer). Teammates do NOT inherit the lead's `/model` by default; an omitted model falls back to the **Default teammate model** in `/config` (set it to "leader's model" to follow the lead). Mixed-model teams are supported. Teammates inherit the lead's **effort** level.
(The old Opus-only lock was removed in CC v2.1.178.)

## Syntax

```
/hs:team <template> <context> [flags]
```

**Templates:** `research`, `cook`, `review`, `debug`

| Flag | Meaning |
|---|---|
| `--devs N` / `--researchers N` / `--reviewers N` / `--debuggers N` | team size |
| `--plan-approval` / `--no-plan-approval` | plan approval gate (default: on for cook) |
| `--delegate` | lead coordinates only, does not touch code |
| `--worktree` | git worktree isolation for devs (default: on for cook) |

## Pre-flight (REQUIRED — before the first teammate spawn)

1. The team is implicit — there is nothing to "create". Preflight the **gate** instead: confirm `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (or `--agent-teams`) is in effect.
2. The tell is the tool schema: with the gate ON, the `Agent` tool accepts a `name` parameter (named spawn = teammate). If a named `Agent(...)` spawn is rejected or `name` is not honored: **STOP. Inform user:** "Agent Teams requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (and the `tengu_amber_flint` server gate)."
3. DO NOT fall back to plain subagents. `hs:team` must use Agent Teams or cancel.

When activated, IMMEDIATELY execute the matching template below. No confirmation, no explanation. Call tools in order. Report progress after each major step.

## Quick tool reference

Task board: `TaskCreate` · `TaskUpdate` · `TaskGet` · `TaskList`. Coordination: `SendMessage`. No `TeamCreate`/`TeamDelete` (removed CC v2.1.178) — team implicit, one per session; teammates end with the session or on `shutdown_request`.

SendMessage types: `message` (DM — requires `recipient`) · `broadcast` (use sparingly) · `shutdown_request` · `shutdown_response` (requires `request_id`) · `plan_approval_response` (requires `request_id`).

Spawn teammate: `Agent(name: "…", subagent_type: "…", model: "opus", run_in_background: true, isolation: "worktree")`. `name` is what makes it a teammate, not a one-shot subagent.

## Harness Context Block (inject into every teammate prompt)

```
Harness Context: work dir={CWD} · reports=plans/reports/ · plans=plans/ · branch={current}
Commits: conventional. Address teammates by NAME. Read first:
  "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/team/references/roles-and-ownership.md
  "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/team/references/messaging-protocol.md
```

---

## ON `/hs:team research <topic>` [--researchers N]

*Wraps hs:research — scope, gather, analyze, report.*

1. Derive N angles from `<topic>` (N defaults to 3): (1) Architecture/patterns; (2) Alternatives/trade-offs; (3) Risks/failure modes. If N>3, derive additional angles from the topic.
2. **CALL** `TaskCreate` x N — one per angle: Subject `Research: <angle>`; description: investigate + save report to `plans/reports/researcher-{N}-{slug}.md` + notify lead when done. (The session team is implicit — no create call.)
3. **Route+size first** via `hs:workflow-orchestrate` — team fan-out is the costliest, always sized before spawning: state `reason`/`strategy`/`scope` (+ the `<angles>` groups) and consume `route_depth` (`agent` → escalate the `@workflow-orchestrator` agent);
   the commands live in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`. Then **SPAWN** x N researchers: `Agent(name: "researcher-{N}",
   subagent_type: "researcher", model: "opus", run_in_background: true)` — the first named spawn establishes the session team.
4. **MONITOR** TaskList after 60s or when a teammate signals completion. If stuck > 5 minutes, message directly.
5. **READ** all reports from `plans/reports/`.
6. **SYNTHESIZE** → `plans/reports/research-summary-{slug}.md` (exec summary, findings, recommendations, open questions).
7. **SHUTDOWN** `SendMessage(type: "shutdown_request")` to each teammate (the implicit team ends with the session — no TeamDelete).
8. **REPORT** to user: `Research done. Summary: {path}. {N} reports.`

---

## ON `/hs:team cook <plan-path|description>` [--devs N]

*Wraps hs:cook — plan, code, test, review, finalize.*

1. **READ** the plan (if a path is given) OR spawn `Agent(subagent_type: "planner")` to create a plan first. Divide tasks into N independent groups with clear file ownership.
2. **CALL** `TaskCreate` x (N devs + 1 tester): dev tasks record `File ownership: <glob>`; tester task uses `addBlockedBy` on all dev task IDs. (Implicit session team — no create call.)
3. **Route+size first** via `hs:workflow-orchestrate` — team fan-out is the costliest, always sized before spawning: state `reason`/`strategy`/`scope` (+ the `<dev-slices>` groups) and consume `route_depth` (`agent` → escalate the `@workflow-orchestrator` agent);
   the commands live in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`. Then **SPAWN** N devs: `Agent(name: "dev-{N}", subagent_type:
   "developer", model: "opus", isolation: "worktree", run_in_background: true)`. With `--plan-approval`: devs plan first, wait for approval via `plan_approval_response`.
4. **MONITOR** TaskList until dev tasks complete → spawn tester: `Agent(name: "tester", subagent_type: "tester", model: "opus")`.
5. **MERGE** worktree branches: `git merge <dev-branch> --no-ff` sequentially. Conflict → resolve manually → `git merge --continue`. Clean up with `git worktree remove <path>`.
6. **DOCS EVAL** (required with cook): `Docs impact: [none|minor|major]` / `Action: [no update|updated <page>|separate PR]`.
7. **SHUTDOWN** `SendMessage(type: "shutdown_request")` to each teammate (implicit team ends with the session — no TeamDelete).
8. **REPORT** to user: what was cooked, test results, docs impact.

---

## ON `/hs:team review <scope>` [--reviewers N]

*Wraps hs:code-review — scout, review, synthesize with evidence gates.*

1. Derive N focus areas (N=3): Security, Performance, Test coverage. If N>3, add: architecture, DX, accessibility.
2. **CALL** `TaskCreate` x N: one task per focus; findings format `[CRITICAL|IMPORTANT|MODERATE] <finding> — <evidence> — <recommendation>`; save to `plans/reports/reviewer-{N}-{slug}.md`. (Implicit session team — no create call.)
3. **Route+size first** via `hs:workflow-orchestrate` — team fan-out is the costliest, always sized before spawning: state `reason`/`strategy`/`scope` (+ the `<focus-areas>` groups) and consume `route_depth` (`agent` → escalate the `@workflow-orchestrator` agent);
   the commands live in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`. Then **SPAWN** x N: `Agent(name: "reviewer-{N}", subagent_type:
   "code-reviewer", model: "opus", run_in_background: true)`.
4. **MONITOR** TaskList after 60s or when a reviewer signals completion.
5. **SYNTHESIZE** → `plans/reports/review-{scope-slug}.md` — deduplicate, rank by severity, create action items.
6. **SHUTDOWN** `SendMessage(type: "shutdown_request")` to each teammate (implicit team ends with the session — no TeamDelete).
7. **REPORT** `Review done. {X} findings ({Y} critical). Report: {path}.`

---

## ON `/hs:team debug <issue>` [--debuggers N]

*Wraps hs:debug — root-cause-first, adversarial hypotheses, convergence.*

1. Generate N independent hypotheses from `<issue>` (N=3): each hypothesis is independently testable and predicts different symptoms.
2. **CALL** `TaskCreate` x N: one task per hypothesis; require ADVERSARIAL mode — actively refute other hypotheses; save to `plans/reports/debugger-{N}-{slug}.md`. (Implicit session team — no create call.)
3. **Route+size first** via `hs:workflow-orchestrate` — team fan-out is the costliest, always sized before spawning: state `reason`/`strategy`/`scope` (+ the `<hypotheses>` groups) and consume `route_depth` (`agent` → escalate the `@workflow-orchestrator` agent);
   the commands live in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`. Then **SPAWN** x N: `Agent(name: "debugger-{N}", subagent_type:
   "debugger", model: "opus", run_in_background: true)`. Let debuggers message each other to converge.
4. **MONITOR** TaskList + messages. Stuck > 5 minutes → intervene.
5. **READ** all reports, identify the surviving hypothesis as root cause.
6. **WRITE** `plans/reports/debug-{issue-slug}.md`: root cause, evidence chain, eliminated hypotheses, proposed fix.
7. **SHUTDOWN** `SendMessage(type: "shutdown_request")` to each teammate (implicit team ends with the session — no TeamDelete).
8. **REPORT** `Debug done. Root cause: <summary>. Report: {path}.`

---

## Boundaries

- `hs:team` requires Agent Teams — do not fall back to plain subagents.
- The lead's runtime control loop (spawn→monitor→stall-detect→recover→merge): `references/coordination-loop.md`.
- File ownership decisions: `references/roles-and-ownership.md`.
- Messaging + task claiming: `references/messaging-protocol.md`.
- Shutdown + cleanup: `references/lifecycle-and-shutdown.md`.
- Lease claim TTL: `HARNESS_CLAIM_LEASE_S` env (default 14400s) — see `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py`.
- Race-free task ownership: `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py` (acquire → release → reclaim; audit trail → trace_log).

## References (load-on-demand)

| Drawer | Contents |
|---|---|
| `references/coordination-loop.md` | The lead's runtime loop: spawn→assign→monitor→classify→recover→merge barrier→shutdown, with stall detection + the recovery ladder |
| `references/roles-and-ownership.md` | File ownership, git safety, conflict resolution |
| `references/messaging-protocol.md` | Task claiming, SendMessage types, plan approval flow |
| `references/lifecycle-and-shutdown.md` | Shutdown protocol (`shutdown_request`), idle state, session-scoped implicit team, error recovery |
| `references/agent-teams-official-docs.md` | Native subagent/team model: how the platform spawns and isolates agents |
| `references/agent-teams-examples-and-best-practices.md` | Worked team patterns + when to fan out vs stay solo |
| `references/agent-teams-controls-and-modes.md` | Coordination controls, run modes, and their trade-offs |

## See also

- `hs:workflow-orchestrate` — the delegation planner. It decides *which* orchestration mode a fan-out wants (subagents vs Workflow vs Agent Teams) and, when the answer is Agent Teams, hands the sized plan here. Reach for it upstream when you are unsure a job is a Teams job at all. Soft pointer — not a co-install dependency.

  **When invoked from a wo plan** (`mode:"team"`): consume the plan JSON directly — one named teammate + `TaskCreate` per `groups[].key`, reuse its `report_dir` as the shared noticeboard, and honor its `exec.gate` (always `confirm_required` for a team). Derive the file-ownership globs here (`references/roles-and-ownership.md`) — the plan carries group identity + count, not globs. Don't
  re-slice work the planner already sized; then run `references/coordination-loop.md`.

