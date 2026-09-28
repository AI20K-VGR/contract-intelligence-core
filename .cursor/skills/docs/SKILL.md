---
name: hs:docs
injectable: true
description: Analyze codebase and manage project documentation — init, update, summarize. Use when docs need to be created, refreshed, or audited.
argument-hint: "[init | update | summarize]"
allowed-tools: [Bash, Read, Glob, Grep, Task]
metadata:
  compliance-tier: workflow
---

# hs:docs — project documentation management

Analyzes codebase, creates/updates docs via `@docs-manager`. NOT code; NOT markdown outside `docs/` or `plans/` (hard constraint — CLAUDE.md rule #5).

**Documentation rule** (when to update, which doc) is in `harness/rules/` → read `documentation-management.md` before executing any mode. Read it first — not repeated here. (`references/documentation-management.md` is the same trigger criteria, kept for other skills to load standalone without pulling in this skill's full procedure — see `references/`.)

## Modes

| Mode | When | Procedure |
|---|---|---|
| `init` | first time, no docs yet | scout → docs-manager creates new |
| `update` | after significant code/arch changes | scout → read existing docs → docs-manager updates |
| `summarize` | need a quick codebase-summary | focused scout → update `docs/codebase-summary.md` |

No argument → `AskUserQuestion` asking user to choose a mode.

## General procedure

1. **Parse argument** — determine mode; if missing → ask.
2. **Scout** — use `hs:scout` to explore the codebase (skip `.git`, `__pycache__`, `harness/state/`, `node_modules`); merge reports.
3. **Read existing docs** (`update`/`summarize` mode) — always read before modifying. Include the glossary when present (`glossary_register.py --root . --list`, or `docs/glossary.yaml` SSOT) for settled vocab + term table; skip quietly if none.
4. **Delegate docs-manager** — spawn `@docs-manager` agent with merged context; the agent acts as a Technical Writer — verify actual code before writing.
5. **Check size** — after docs-manager finishes: `wc -l docs/*.md | sort -rn`; file exceeds 800 LOC → warn + ask user whether to split or keep.
6. **Verify** — after update: check that dates, links, and claims match actual changes.

Per-mode details: `references/init-workflow.md` (first-time set from the real codebase) ·
`references/update-workflow.md` (refresh against a diff) · `references/summarize-workflow.md`
(codebase-summary pass).

## HARD-GATE (real wiring)

No dedicated hard gate for docs — but:
- All documentation files must be under `docs/` or `plans/` — creating elsewhere violates CLAUDE.md rule #5 and is caught by the CI invariant.

## Output language

Render reports per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/output-rendering.md`: resolve `language` / `audience` / `humanize` live via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/output_config.py --resolved` (never hand-read the tracked file); the rule holds the register behavior and the evidence-invariant fence.

## Boundaries

- Do NOT write code or modify harness files outside `docs/` and `plans/`.
- Do NOT create markdown elsewhere (root except pre-approved README/CLAUDE/BACKLOG, `harness/` except `harness/rules/` via its own process).
- Docs mirror the real codebase — `@docs-manager` verifies each `functionName()`, file path, and env var before writing. Describing assumed behavior → stop.
- Read the existing doc BEFORE modifying it (rule `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md`).
- On completion: report updated files (absolute paths) + size check result.
