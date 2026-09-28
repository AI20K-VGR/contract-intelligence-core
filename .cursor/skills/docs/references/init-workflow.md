# Init workflow — first-time documentation setup

Use when `docs/` does not exist or is nearly empty. Creates an initial doc set from the real codebase.

## Phase 1 — Scout codebase

1. Use `hs:scout` to explore the codebase; compute LOC per directory.
2. Skip: `.git`, `__pycache__`, `harness/state/`, `node_modules`, `.cache/`.
3. Merge scout reports into a context summary.

## Phase 2 — Create docs (docs-manager agent)

Spawn `@docs-manager` agent (Task tool) with merged context. Agent creates:

| File | Content |
|---|---|
| `docs/codebase-summary.md` | codebase overview |
| `docs/system-architecture.md` | architecture + data flow |
| `docs/code-standards.md` | code standards, naming, patterns |
| `docs/project-roadmap.md` | development roadmap |
| `docs/project-overview-pdr.md` | project overview + PDR |
| `docs/deployment-guide.md` *(optional)* | deployment guide |

**Important for docs-manager:** verify every `functionName()`, file path, and env var actually exists in the code before writing — do not describe assumed behavior.

**Standards docs follow a template.** `docs/system-architecture.md` and `docs/code-standards.md` are free-form prose; section-set fixed by a template SSOT. Before writing either, seed section headers from it —
`python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/scaffold_standards.py --type <system-architecture|code-standards> --print` — and conform to those `## ` sections, leaving `> TBD` for anything undecided. After writing, verify with
`python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/scaffold_standards.py --type <t> --check docs/<t>.md` (exit 1 lists missing/extra sections; add or drop to match). This is the prose standards pair only — do NOT route it through hs:docs-scaffold / hs:docs-standardize (a different, frontmatter+graph template system for module docs).

## Phase 3 — Check size

After docs-manager finishes:
```bash
wc -l docs/*.md 2>/dev/null | sort -rn
```
File exceeds 800 LOC → report + ask user: split now or keep as-is?

## Constraints

- Only create files in `docs/` — do not create markdown elsewhere.
- Do not start implementing code.
