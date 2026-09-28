# Markdown Body Templates

Standard content structures for each markdown document type. See SKILL.md Rule 4 for overview.

## Universal Rules

- Start with `# Title` (H1) — one per file
- Frontmatter (`---`) for metadata when consumed by tools/automation
- Sections ordered: context → content → next steps
- Tables for structured data, lists for sequences
- Sacrifice grammar for concision
- List unresolved questions at end

## Plan (plan.md)

```markdown
---
title: "{Plan Title}"
status: pending | in_progress | completed | cancelled
created: YYYY-MM-DD
---

# {Plan Title}

## Overview
Brief description of what this plan accomplishes.

## Phases

| # | Phase | Status | File |
|---|-------|--------|------|
| 1 | {Phase name} | pending | [phases/phase-1-{name}.md] |
| 2 | {Phase name} | pending | [phases/phase-2-{name}.md] |

## Dependencies
- {dependency 1}
- {dependency 2}

## Success Criteria
- {criterion 1}
- {criterion 2}
```

## Phase (phase-{NN}-{name}.md)

```markdown
# Phase {NN}: {Name}

## Context Links
- Plan: [plan.md](./plan.md)
- Related: {links to reports, docs, code}

## Overview
- **Priority:** high | medium | low
- **Status:** pending | in_progress | completed
- **Description:** {brief description}

## Key Insights
- {finding from research}
- {critical consideration}

## Requirements
### Functional
- {requirement}
### Non-functional
- {requirement}

## Architecture
{system design, component interactions, data flow}

## Related Code Files
- **Modify:** {file paths}
- **Create:** {file paths}
- **Delete:** {file paths}

## Implementation Steps
1. {step with specific instructions}
2. {step}

## Todo
- [ ] {task}
- [ ] {task}

## Success Criteria
- {definition of done}

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|-----------|
| {risk} | {impact} | {mitigation} |

## Next Steps
- {dependency or follow-up}
```

## Report ({type}-report.md)

```markdown
---
type: {scout | researcher | code-reviewer | tester | debugger | brainstorm}
date: YYYY-MM-DD
---

# {Report Type}: {Subject}

## Summary
{2-3 sentence overview of findings}

## Findings
### {Finding 1}
{details, evidence, code references}

### {Finding 2}
{details}

## Recommendations
1. {actionable recommendation}
2. {recommendation}

## Unresolved Questions
- {question that needs further investigation}
```

## Journal (plans/journals/)

```markdown
---
date: YYYY-MM-DD
session: {session identifier or topic}
---

# Journal: {Date} — {Topic}

## Context
{what was being worked on, why}

## What Happened
- {key event/decision/discovery}
- {event}

## Reflection
{honest assessment — what went well, what didn't, emotional state}

## Decisions Made
| Decision | Rationale | Impact |
|----------|-----------|--------|
| {decision} | {why} | {what changes} |

## Next Steps
- {follow-up action}
```

## More templates

General doc templates (Doc, ADR, Changelog, README, Guide, Spec): `markdown-body-templates-general.md`.
