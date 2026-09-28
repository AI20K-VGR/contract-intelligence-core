# `--recap [timeframe]` — project context snapshot (structured-analysis report)

Structured-analysis Markdown report re-establishing project context after time away (Mermaid + KPI cards). Output to plans/ or docs/ — no HTML renderer.

## Time window

Shorthand `2w` / `30d` / `3m`, or default `2w`.

## Data to gather

- project identity (name, purpose, stack)
- `git log` over the window
- `git status`
- decision context (recent DECs / decisions)
- architecture scan

## Output sections

- project identity
- architecture snapshot (Mermaid)
- recent activity (commits, merges over the window)
- decision log
- state KPI cards
- mental-model essentials (what a returning developer must hold in head)
- cognitive-debt hotspots
- next steps
