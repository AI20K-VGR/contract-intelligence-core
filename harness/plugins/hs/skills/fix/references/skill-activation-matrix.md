# Skill Activation Matrix

When to activate each skill and tool during fixing workflows.

> **Deps vs advisory activation.** Only `hs:fix`'s declared deps — `scout`, `debug`, `brainstorm`,
> `remember` (`"${HARNESS_BIN_ROOT:-.}"/harness/data/skill-deps.yaml`) — are guaranteed co-installed. Every other skill named
> below (`sequential-thinking`, `problem-solving`, `project-management`, `journal`,
> `context-engineering`, `ai-multimodal`, and the researcher/planner agents…) is
> **activate-when-available/relevant**, not a hard requirement: if it is OFF, route via
> `/hs:use <name>` or skip it. The "Always / Mandatory" labels below mean "reach for it by default
> when present," not "the fix cannot proceed without it" — SKILL.md's Standard procedure is the real
> critical path.

## Reach for by default (most workflows)

| Skill/Tool | Step | Reason |
|------------|------|--------|
| `hs:scout` OR parallel `Explore` | Step 1 | Understand codebase context before diagnosing |
| `hs:debug` | Step 2 | Systematic root cause investigation |
| `hs:sequential-thinking` | Step 2 | Structured hypothesis formation — NO guessing |
| `/hs:project-management` | Step 6 | Sync-back + progress tracking when the fix is part of a plan |

## Task Orchestration (Moderate+ Only)

| Tool | Activate When |
|------|---------------|
| `TaskCreate` | After complexity assessment, create all phase tasks upfront |
| `TaskUpdate` | At start/completion of each phase |
| `TaskList` | Check available unblocked work, coordinate parallel agents |
| `TaskGet` | Retrieve full task details before starting work |

Skip Tasks for Quick workflow (< 3 steps).

## Auto-Triggered Activation

| Skill | Auto-Trigger Condition |
|-------|------------------------|
| `hs:problem-solving` | 2+ hypotheses REFUTED in Step 2 diagnosis |
| `hs:sequential-thinking` | Always in Step 2 (mandatory for hypothesis formation) |

## Conditional Activation

| Skill | Activate When |
|-------|---------------|
| `hs:brainstorm` | Multiple valid fix approaches, architecture decision (Deep only) |
| `hs:context-engineering` | Fixing AI/LLM/agent code, context window issues |
| `hs:ai-multimodal` | UI issues, screenshots provided, visual bugs |

## Subagent Usage

> Spawn every `Explore` below with `model:"haiku"` — it inherits the session's Opus
> otherwise, wasteful for file-finding.

| Subagent | Activate When |
|----------|---------------|
| `@debugger` | Root cause unclear, need deep investigation (Step 2) |
| `Explore` (parallel) | Scout multiple areas simultaneously (Step 1), test hypotheses (Step 2) |
| `Bash` (parallel) | Verify implementation: typecheck, lint, build, test (Step 5) |
| `hs:researcher` | External docs needed, latest best practices (Deep only) |
| `hs:planner` | Complex fix needs breakdown, multiple phases (Deep only) |
| `@tester` | After implementation, verify fix works (Step 5) |
| `hs:code-review` | After fix, verify quality and security (Step 5) |
| `@git-manager` | After approval, commit changes (Step 6) |
| `@docs-manager` | API/behavior changes need doc updates (Step 6) |
| `hs:developer` | Parallel independent issues (each gets own agent) |

## Parallel Patterns

Parallel exploration: spawn read-only scouts per `hs:scout` (the orchestration-protocol rule governs fan-out).

| When | Parallel Strategy |
|------|-------------------|
| Scouting (Step 1) | 2-3 `Explore` agents on different areas |
| Testing hypotheses (Step 2) | 2-3 `Explore` agents per hypothesis |
| Multi-module fix | `Explore` each module in parallel |
| After implementation (Step 5) | `Bash` agents: typecheck + lint + build + test |
| 2+ independent issues | Task trees + `hs:developer` agents per issue |

## Workflow → Skills Map

| Workflow | Skills Activated |
|----------|------------------|
| Quick | `hs:scout` (minimal), `hs:debug`, `hs:sequential-thinking`, `hs:code-review`, `/hs:project-management`, parallel `Bash` verification |
| Standard | Above + Tasks, `hs:problem-solving` (auto), `hs:project-management`, `@tester`, parallel `Explore` |
| Deep | All above + `hs:brainstorm`, `hs:context-engineering`, `hs:researcher`, `hs:planner` |
| Parallel | Per-issue Task trees + `hs:project-management` + `hs:developer` agents + coordination via `TaskList` |

## Step → Skills Chain (matches SKILL.md step order)

| Step | Chain |
|------|----------------|
| Step 0: Mode | `AskUserQuestion` (unless auto/quick detected) |
| Step 1: Scout | `hs:scout` OR 2-3 parallel `Explore` → map files, deps, tests |
| Step 2: Diagnose | Capture pre-fix state → `@debugger` → (`hs:sequential-thinking` if reasoning tangles) → parallel `Explore` hypotheses → (`hs:problem-solving` if 2+ fail) |
| Step 3: Fix | Minimal-scope change → follow root cause (create Tasks for moderate+ multi-issue work) |
| Step 4: Red→green test | Regression test RED → fix → GREEN → full suite |
| Step 5: Review | `@code-reviewer` (root cause resolved + blast-radius sweep) → parallel `Bash` verify → re-verify any delegated slice's test |
| Step 6: Gate + finalize | HARD-GATE-NO-SIDE-EFFECTS sweep → report → (`hs:project-management` if plan active) → `@docs-manager` → `@git-manager` → `/hs:remember` (optional) |

## Detection Triggers

| Keyword/Pattern | Skill to Consider |
|-----------------|-------------------|
| "AI", "LLM", "agent", "context" | `hs:context-engineering` |
| "stuck", "tried everything" | `hs:problem-solving` |
| "complex", "multi-step" | `hs:sequential-thinking` |
| "which approach", "options" | `hs:brainstorm` |
| "latest docs", "best practice" | `hs:researcher` subagent |
| Screenshot attached | `hs:ai-multimodal` |
