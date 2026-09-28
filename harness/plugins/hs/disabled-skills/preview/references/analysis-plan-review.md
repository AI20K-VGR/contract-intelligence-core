# `--plan-review [plan-file]` — plan vs codebase comparison (structured-analysis report)

Structured-analysis Markdown report comparing a plan against the real codebase (Mermaid + review cards). Output to plans/ or docs/ — no HTML renderer.

## Input

Plan file path, or detect from active plan context.

## Data to gather

- read the plan
- read every file the plan references
- map the blast radius (what the plan will touch)
- cross-reference the plan's assumptions against the current code

## Output sections

- plan summary
- impact dashboard
- current vs planned architecture (paired Mermaid diagrams)
- change breakdown (side-by-side)
- dependency analysis
- risk assessment
- review cards
- understanding gaps (where the plan assumes something the code does not show)

## Visual language

- blue = current state
- green = planned state
- amber = concern
- red = gap
