# Summarize workflow — quick codebase summary

Use when a quick update to `docs/codebase-summary.md` is needed without a full docs update.

## Arguments

- `$1`: focus topic (default: everything)
- `$2`: whether to scan the full codebase (`true`/`false`, default: `false`)

## Procedure

1. Use `hs:scout` to analyze the codebase — scope to `$1` if provided.
2. If `$2 = false`: scout only recently changed directories (git diff).
3. If `$2 = true`: scout the full codebase (skip `.git`, `__pycache__`, `harness/state/`, `node_modules`).
4. Update `docs/codebase-summary.md` with the scout results.
5. Return a concise summary report.

## Constraints

- Only modify `docs/codebase-summary.md` (and at most 1-2 clearly related doc files).
- Do not scan the full codebase unless the user explicitly requests it.
- Do not start implementing code.
- Read the current `docs/codebase-summary.md` BEFORE overwriting it.
