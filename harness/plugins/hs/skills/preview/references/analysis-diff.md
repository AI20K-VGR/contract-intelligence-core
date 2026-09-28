# `--diff [ref]` — visual diff review (structured-analysis report)

Structured-analysis Markdown report on a change set (Mermaid + review cards; not a single diagram). Output to plans/ or docs/ per save-location rule — no HTML renderer.

## Scope auto-detect

Resolve diff scope from `[ref]`, in order: explicit branch name, commit hash, `HEAD`, PR number, commit range (`a..b`); default `main`.

## Data to gather

- `git diff --stat` and `git diff --name-status` for the scope
- changed files + the new public API surface they introduce
- `CHANGELOG` entry for the range (if present)

## Output sections

- executive summary (what changed, why it matters)
- KPI dashboard (files changed, insertions/deletions, test delta)
- module architecture (Mermaid) — components touched and their links
- feature comparisons (side-by-side before/after)
- flow diagrams for changed control paths
- file map (which files, grouped by module)
- test coverage delta
- code review cards: **Good / Bad / Ugly / Questions**
- decision log + re-entry context (what a returning reader needs)
