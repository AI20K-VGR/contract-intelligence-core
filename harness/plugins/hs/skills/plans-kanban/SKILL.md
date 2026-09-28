---
name: hs:plans-kanban
injectable: false
description: View a file-based kanban board for all plans in plans/ — grouped by status (pending / in-progress / completed), navigate into a plan, check progress. Use for a quick work-status snapshot.
argument-hint: "[--active | --done | --plan <slug> | --filter <tag>]"
allowed-tools: [Bash, Read, Glob, Grep]
metadata:
  compliance-tier: workflow
---

# hs:plans-kanban — file-based plan kanban board

Reads the YAML frontmatter `status` from every `plans/<ts>-<slug>/plan.md` and renders a kanban board directly in the CLI. No server or browser required.

**Cross-ref**: use `hs:project-management` to update status, sync tasks, or generate detailed reports — `hs:plans-kanban` is read-only navigation; it does not write.

## Modes / arguments

| Argument | Effect |
|---|---|
| (empty) | Show full board: 3 columns, all plans |
| `--active` | Only the `in-progress` + `approved` columns (reviewed-and-ready counts as active work) |
| `--done` | Only the `completed` column |
| `--plan <slug>` | Show detail for one plan: title, phases, % done |
| `--filter <tag>` | Filter by tag in frontmatter `tags:` |

## Workflow

1. **Scan** — `find plans/ -name "plan.md" -not -path "*/reports/*"` (excludes `plans/reports/`, `plans/templates/`).
2. **Parse frontmatter** — read the `---...---` YAML block at each file's top; extract: `title`, `status`, `priority`, `tags`, `created`, `branch`.
3. **Normalize then group by status**. First fold variants as the schema does — strip quotes, replace `-` with `_`, fold RETIRED labels `draft`/`awaiting_human_approval` to `pending` (their canonical home). Compare the folded value against the canonical set (`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/plan_status.py:CANONICAL_STATUSES` = `pending, approved, in_progress, completed, cancelled`):

   | Column | Canonical status |
   |---|---|
   | TODO | `pending` (a legacy `draft`/`awaiting_human_approval` folds here) |
   | APPROVED | `approved` (reviewed, not yet cooked) |
   | IN PROGRESS | `in_progress` |
   | DONE | `completed` |
   | (hidden) | `cancelled` — render only under `--filter` |
   | ⚠ DRIFT | any value that is not canonical after folding (e.g. `done`, `implemented`, or a missing field) |

   A DRIFT plan shows in its own row, not silently dropped into the board; the warning names `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/reconcile_plan_status.py` as the fix. A retired `draft`/`awaiting_human_approval` label folds to TODO for display, but `reconcile --fix` migrates it for real (evidence-aware: an APPROVED artifact lifts it to `approved`).

4. **Render board** — print a 4-column table TODO · APPROVED · IN PROGRESS · DONE (markdown table or compact list per width), one row per plan: `priority | slug | title | branch | created`.
5. **Navigate** — print the absolute path to `plan.md` for every IN PROGRESS plan; prompt the user to open it or invoke `hs:project-management status`.
6. **Warn** — a plan missing frontmatter or `status` → warn clearly with the file name; don't crash the board.

## Boundaries

- **READ-ONLY** — never modify any file in `plans/`.
- Do not create markdown outside `plans/` or `docs/` (CLAUDE.md rule #5 — n/a, this skill creates no files).
- Do not write tasks, mark done, or sync — that's `hs:project-management`'s job.
- Source of truth for status: the local `plan.md` file.
- End with board printed + absolute paths for active plans.

## Actual backing (wiring)

This skill reads files — it has no dedicated hard gate. However:
- `plans/*/plan.md` YAML frontmatter `status` = sole data source.
- To update status: use `hs:project-management sync`, then re-run `hs:plans-kanban` for the updated board.

## Example output (compact)

```
TODO (1)
  P2 | 260615-1430-search-filter | add search filter | main

APPROVED (1)
  P1 | 260615-1000-export-csv | csv export | feature/export-csv

IN PROGRESS (2)
  P1 | 260614-0900-auth-refresh | refresh login token | feature/auth-refresh
  P1 | 260613-1100-cache-layer  | query cache layer   | main

DONE (2)
  P1 | 260612-1600-payment-webhook | payment webhook | main
  P1 | 260611-1400-onboarding-flow | onboarding flow | main
```
