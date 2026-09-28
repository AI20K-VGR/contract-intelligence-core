# Update workflow — update docs after a change

Use when `docs/` exists but the codebase has changed significantly (new feature, refactor, architecture change).

## Phase 1 — Scout codebase

1. Use `hs:scout` to explore the codebase; compute LOC per directory.
2. Skip: `.git`, `__pycache__`, `harness/state/`, `node_modules`, `.cache/`.
3. Merge scout reports into a context summary.

## Phase 1.5 — Read existing docs

**Read before modifying** (required — rule `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md`).

1. Count files: `ls docs/*.md 2>/dev/null | wc -l`
2. Check LOC: `wc -l docs/*.md 2>/dev/null | sort -rn`
3. Parallel read strategy (pin `model:"haiku"` on every `Explore` spawn — it inherits Opus otherwise, wasteful for reading files):
   - 1-3 files: docs-manager reads directly
   - 4-6 files: spawn 2-3 `Explore` agents with `model:"haiku"`
   - 7+ files: spawn 4-5 `Explore` agents with `model:"haiku"` (max 5)
4. Distribute files by LOC (larger files → dedicated agent).
5. Merge results into context for docs-manager.

## Phase 2 — Update docs (docs-manager agent)

Spawn `@docs-manager` agent (Task tool) with merged context + doc readings. Agent updates:

| File | Notes |
|---|---|
| `docs/codebase-summary.md` | always update |
| `docs/system-architecture.md` | when architecture/data flow changes |
| `docs/code-standards.md` | when patterns/conventions change |
| `docs/project-roadmap.md` | when roadmap changes |
| `docs/project-overview-pdr.md` | when scope/requirements change |

**Important for docs-manager:** verify every reference (function, path, env var, API endpoint) actually exists in the current code — remove stale sections instead of leaving "TODO: update".

**Standards docs follow a template.** When updating `docs/system-architecture.md` or `docs/code-standards.md`, keep them conformant to the template SSOT: after editing, run `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/scaffold_standards.py --type <t> --check docs/<t>.md` (exit 0 conform / 1 drift).
Drift (exit 1) lists missing/extra `## ` sections — add the missing ones (with `> TBD` if undecided) or fold the
extra back in. Compare against the canonical headers with `--type <t> --print`. Prose standards pair only — do NOT route through hs:docs-scaffold / hs:docs-standardize (the module-docs template system).

## Phase 3 — Check size

After docs-manager finishes:
```bash
wc -l docs/*.md 2>/dev/null | sort -rn
```
File exceeds 800 LOC → report + ask user: split now or keep as-is?

## Phase 4 — Verify after update

Check manually or with an available script:
- Dates, internal links, and claims match actual changes.
- No remaining references to deleted files/functions.

## Constraints

- Only modify/create files in `docs/` — do not create markdown elsewhere.
- Do not start implementing code.
- Additional arguments are passed to docs-manager via `$ARGUMENTS`.
