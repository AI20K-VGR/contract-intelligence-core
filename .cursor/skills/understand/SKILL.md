---
name: hs:understand
injectable: true
description: Orchestrate codebase comprehension before touching code — chain hs:repomix, hs:scout, hs:context-engineering to build a codebase map. Use before hs:plan on unfamiliar areas.
allowed-tools: [Bash, Read, Write, Grep, Glob, Task]
metadata:
  compliance-tier: workflow
argument-hint: "[path-or-subtree] [--persist] [--budget <token-limit>]"
---

# hs:understand — comprehend a codebase before touching it

Orchestrator READ-ONLY: explore a codebase/subsystem, synthesize a
**codebase map** (markdown), hand off to hs:plan or hs:triage. No code writes, no plan, no commit.

## Execution steps

0. **Preflight** — read `harness/LESSONS.md` (past failure modes shape comprehension, not rediscovery). Also read the glossary (`glossary_register.py --root . --list`, or `docs/glossary.yaml` SSOT — `GLOSSARY.md` is its view) so the map uses settled vocabulary, not parallel terms.

1. **Determine scope** — accept path/subtree from the argument or ask via `AskUserQuestion`; if missing, ask first, do not guess.

2. **Pack snapshot** — call `hs:repomix` with the confirmed scope: `--style markdown`, output to `harness/state/` (do not commit). On a default-off install repomix is stashed — run it once via `/hs:use repomix` (the on-demand door loads it for that call without enabling it every session). Estimate tokens first — if the budget is tight, narrow scope or use `--remove-comments`. Details:
   `references/chain-orchestration.md`.

3. **Scout file-key** — call `hs:scout` in parallel if the codebase is large enough (SCALE >= 3); for smaller codebases use Grep/Glob directly (avoid overhead). Output -> `plans/reports/`.
   Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`.

4. **Budget check** — call `hs:context-engineering` to estimate the tokens needed for loading; apply Select/Compress/Isolate strategy before synthesizing.

5. **Synthesize map** — write the codebase map following the template in
   `references/map-template.md`: module/layer, file-key + responsibility, data/control flow, external boundaries, task entry points, unknowns. Save to `plans/reports/` (default) or `docs/` when `--persist`.

6. **Persist (optional)** — when `--persist` is passed: call `hs:docs` to update or initialize a long-lived doc (e.g. `docs/codebase-summary.md`). Persist only if genuinely long-lived; temporary maps go to `plans/reports/`, not `docs/`.
   Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md`.

7. **Hand off** — return the absolute path of the map, token count, and list of open unknowns. Handoff -> hs:plan (the map is comprehension input, not a plan). Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` §Orchestrator (understand->plan/triage).

## Backing

| Mechanism | File/rule |
|---|---|
| Output path (docs/ or plans/) | `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md` |
| Handoff understand -> hs:plan/hs:triage | `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` |
| Parallel exploration | delegate to `hs:scout` (it routes its own fan-out) |
| Plan a fan-out you run **yourself** (not via a sub-skill) | `hs:workflow-orchestrate` |
| Component skills | hs:repomix, hs:scout, hs:context-engineering, hs:docs |

understand chains sub-skills that self-route (`hs:scout` / `hs:repomix`); it does NOT double-route their fan-out. Only if understand spawns its OWN extra fan-out beyond calling a sub-skill must it route through `hs:workflow-orchestrate`.

## Boundaries

- READ-ONLY: do NOT edit code, do NOT generate a plan, do NOT commit, do NOT gate.
- Out-of-scope findings -> record via `backlog_register.py add`; do not include in the map.
- Map must reside in `plans/reports/` or `docs/` (CLAUDE.md rule #5; `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md`).
- Finish: absolute path of the map + token count + list of open unknowns.

## References (load when needed)

| Drawer | Content | When to load |
|---|---|---|
| `references/map-template.md` | Codebase map template, required sections | When starting synthesis |
| `references/chain-orchestration.md` | Details of calling hs:repomix/scout/context-engineering | When coordinating the chain |
