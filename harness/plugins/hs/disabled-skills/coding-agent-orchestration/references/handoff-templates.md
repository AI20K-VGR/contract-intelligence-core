# Handoff templates

Copy-ready templates for assigning, briefing, reviewing, and integrating multi-agent work.
Load this when you need the exact shape of a handoff, not the decision of whether to fan out.

## Agent Assignment Plan

```markdown
## Objective
<done state>

## Execution Shape
single-agent | sequential | parallel | review-loop

## Assignments
| Role | Agent/tool | Scope | Owns files | Evidence |
| --- | --- | --- | --- | --- |
| Planner | <agent> | <scope> | none | plan + risks |

## Coordination Rules
- Source of truth:
- Shared files owner:
- Merge strategy:
- Stop conditions:
```

## Agent Handoff Brief

```markdown
## Task
<specific assignment>

## Context
- Repo/branch:
- Issue/PR/spec:
- Files you may edit:
- Files you must not edit:

## Requirements
- <acceptance criteria>

## Evidence Required
- <commands/checks>

## Return
- Summary
- Files touched
- Tests/checks run
- Risks or blockers
```

## Review Request

```markdown
Review this work against the original objective, changed files, tests, and risk areas.
Focus on correctness, regressions, security, data loss, maintainability, and missing tests.
Return findings by severity with file/line evidence and concrete fixes.
```

## Final Integration Summary

```markdown
## Result
<what changed>

## Agents Used
<who did what>

## Evidence
- <tests/checks>

## Risks
- <remaining risk or none>

## Follow-ups
- <only if needed>
```
