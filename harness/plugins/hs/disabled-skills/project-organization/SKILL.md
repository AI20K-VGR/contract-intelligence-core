---
name: hs:project-organization
injectable: true
description: Organize files, directories, and content structure in any project. Use when creating files, determining output paths, organizing assets, or standardizing project layout.
argument-hint: "[targets...]"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob]
metadata:
  compliance-tier: workflow
---

# hs:project-organization — project structure organization

Standardize file locations, naming conventions, directory structure, markdown templates — all project types.
**DO NOT** write code; **DO NOT** create markdown outside `docs/` or `plans/` (CLAUDE.md rule 5 — `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md` locks the zone).

## Modes

| Mode | Activated by | Behavior |
|------|-----------|---------|
| **Advisory** | another skill/agent references this skill | return the correct path + name for the requested file type |
| **Organize** | user invokes directly with dirs/files | scan → propose changes → execute after confirmation |

## Rule 1 — Directory classification

| Type | Path | Purpose |
|------|------|----------|
| Source code | `src/` or project root | application code (by language) |
| Documentation | `docs/` | human + AI docs, guides, specs |
| Plans | `plans/` | implementation plans, research, agent reports |
| Tests | `harness/tests/` or `tests/` | test suite (unit, integration, e2e) |
| Scripts | `harness/scripts/` or `scripts/` | build, deploy, utility scripts |
| Assets | `assets/{type}/` | media, branding, design |
| Config | root or `.config/` | dotfiles, config, env |

Detail for each type is in `references/docs-vs-plans-vs-code.md`; the per-category directory layout (what lives under `docs/`, `plans/`, scripts, assets) is in `references/directory-patterns.md`.

## Rule 2 — Naming conventions

All file names: **kebab-case**, self-describing.

| Mode | Pattern | When | Example |
|--------|---------|---------|-------|
| **Timestamped** | `{YYMMDD-HHmm}-{slug}` | time-sensitive: plan, report, journal | `260304-1530-auth-plan` |
| **Evergreen** | `{slug}` | stable docs, config, guides | `system-architecture.md` |
| **Variant** | `{slug}-{variant}.{ext}` | multiple versions of the same asset | `logo-dark.svg` |

**Slug rules:** lowercase, hyphens only, max 50 characters, no leading/trailing hyphens.

**Get a timestamp:**
```bash
date +%y%m%d-%H%M
```

**Code file naming:** kebab-case for JS/TS/Shell/Python; snake_case for Python modules if repo already snake_case; PascalCase for C#/Java/Swift; snake_case for Go/Rust.

Detail in `references/naming-conventions.md`; where one module ends and the next begins is
in `references/module-boundaries.md`.

## Rule 3 — Nesting decisions

| Situation | Pattern | Example |
|-----------|---------|-------|
| Single-file output | flat file in type dir | `plans/journals/260304-session.md` |
| Multi-file output | self-contained directory | `plans/260304-auth-impl/plan.md` + `phases/phase-*.md` |
| Attached to a parent | nested under parent context | `plans/260304-auth-impl/reports/scout-report.md` |
| Standalone report | `plans/reports/` | `plans/reports/general-purpose-260304-1530-auth-report.md` |

**Empty directories:** add `.gitkeep`.

## Rule 4 — Markdown content structure

Every markdown file: start with `# Title` (H1), frontmatter if machine-read, section order: context → content → next steps.

| Type | Required sections |
|------|-----------------|
| **Plan** | frontmatter → overview → phases + status → dependencies → success criteria |
| **Phase** | context link → overview → requirements → implementation steps → checklist → risks |
| **Report** | frontmatter → summary → findings → recommendations → open questions |
| **Journal** | frontmatter → context → what happened → decisions → next steps |
| **Doc** | title → overview → sections → references |

Template structure: `references/docs-vs-plans-vs-code.md` (type-to-section table). Full body templates: `references/markdown-body-templates.md` (SDLC: plan/phase/report/journal), `references/markdown-body-templates-general.md` (general docs).

## Rule 5 — Path decision tree

```
1. Source code? → src/ or project root (by language)
2. Test? → harness/tests/ or tests/ (mirror source)
3. Plan or agent output?
   → Plan: plans/{date-slug}/
   → Report attached to plan: plans/{date-slug}/reports/
   → Standalone report: plans/reports/
   → Research: plans/{date-slug}/research/ or plans/research/
4. Human/AI documentation?
   → Journal: plans/journals/{date-slug}.md
   → Evergreen doc: docs/{slug}.md
5. Media/design/brand asset? → assets/{type}/{naming-rule-2}
6. Utility script? → harness/scripts/{slug}.py or scripts/{slug}.sh
7. Config? → root or .config/ (by ecosystem)
```

## Organize mode

When invoked as `/hs:project-organization [targets]`:

1. **Scan** — list files in target dirs, classify by type
2. **Analyze** — detect bad names, misplaced files, inconsistencies
3. **Propose** — migration table (from → to) presented to user
4. **Confirm** — ask user before moving
5. **Execute** — move/rename files, create missing directories
6. **Verify** — list final structure, flag remaining issues

**Safety:** do not overwrite existing files (ask on conflict); do not touch `.git/`, `node_modules/`, `harness/state/`, `.env`; respect `.gitignore`.

## Wiring with harness

This skill is the **single source of truth** for file paths — other skills reference it for output paths:

- `hs:plan` / `hs:brainstorm` → `plans/` structure
- `hs:docs` / `@docs-manager` agent → `docs/` structure
- `hs:scout` / `hs:research` → `plans/reports/` or `plans/{plan}/research/`
- `hs:cook` / `hs:fix` → source code path (by language)
- `hs:project-management` → `docs/` + `plans/`

## HARD-GATE (real wiring)

`"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md`: markdown ONLY in `docs/` or `plans/` (root README/CLAUDE/BACKLOG are individually approved exceptions) — CLAUDE.md rule 5.
This markdown zone is **advisory only** (no CI invariant test enforces it), NOT enforced by `write_guard` either. `write_guard.py` guards specific config/code files (GUARD_LIST) and contains no markdown paths.

## Boundaries

- DO NOT write code or edit files outside organizational scope (plan/doc/asset paths).
- DO NOT create markdown outside `docs/` or `plans/` (root README/CLAUDE/BACKLOG are individually approved).
- Stack-neutral: do not prescribe framework-specific structure (Next.js app/, Rails app/, etc.) — follow the language/framework convention of the project.
- On exit: report files moved/created (absolute paths) + flag remaining issues.
