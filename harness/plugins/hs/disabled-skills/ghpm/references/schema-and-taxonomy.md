# Schema And Taxonomy

Use when bootstrapping/auditing GitHub as project SSOT.

## Minimal Label Set

Inspect first:

```bash
gh label list --limit 200
```

Add only missing labels. Recommended prefixes:

| Prefix | Examples | Purpose |
| --- | --- | --- |
| `type:` | `type:bug`, `type:feature`, `type:task`, `type:decision`, `type:research` | Work kind |
| `priority:` | `priority:p0`, `priority:p1`, `priority:p2`, `priority:p3` | Scheduling pressure |
| `status:` | `status:triage`, `status:ready`, `status:in-progress`, `status:blocked`, `status:review`, `status:done` | Fallback state if no Project |
| `area:` | `area:api`, `area:web`, `area:ops`, `area:docs`, `area:release` | Ownership/routing |
| `agent:` | `agent:ai-ok`, `agent:human-needed`, `agent:needs-context` | AI/human routing |
| `risk:` | `risk:security`, `risk:data-loss`, `risk:breaking-change` | Review escalation |
| `size:` | `size:s`, `size:m`, `size:l` | Planning granularity |

Status labels must be mutually exclusive. Before applying a status label, remove other `status:*` labels.

## Project Fields

Prefer GitHub Projects fields for live board state:

| Field | Type | Values |
| --- | --- | --- |
| `Status` | single select | Triage, Ready, In Progress, Blocked, Review, Done |
| `Owner` | assignees or text | Human/agent accountable owner |
| `Lane` | single select | Human, AI, Pair, Automation |
| `Priority` | single select | P0, P1, P2, P3 |
| `Iteration` | iteration | Sprint/week/cycle |
| `Target` | date | Expected completion |
| `Risk` | labels or single select | Security, Data Loss, Breaking Change, Low |
| `Next Action` | text | One-line handoff action |

## Issue Body Template

Extends SKILL.md Task Contract: adds optional `Dependencies`/`Evidence` sections (bootstrap use). `Handoff Summary` replaces Task Contract's `Handoff Log` name — see Handoff below for why.

```markdown
## Outcome

## Context
- Repo:
- Branch:
- Related files:
- Links:

## Acceptance Criteria
- [ ] 

## Dependencies
- Blocked by:
- Blocks:

## Handoff Summary
- Last known state, evidence, next action (overwrite, not append — see Handoff Comment Template below for chronological entries).

## Skill Chain

## Evidence
- Commands:
- Checks:
- PRs:
```

## Handoff Comment Template

```markdown
### Handoff
- State: ready | in-progress | blocked | review | done
- Owner: @user or agent name
- Last verified:
- Evidence:
- Next command:
- Blocker:
- Unresolved questions:
```

## Bootstrap Commands

```bash
gh label create "type:task" --color "5319E7" --description "Generic project task"
gh label create "status:ready" --color "0E8A16" --description "Ready to start"
gh label create "status:blocked" --color "B60205" --description "Blocked by explicit dependency"
gh label create "agent:ai-ok" --color "1D76DB" --description "AI agent can execute with current context"
gh label create "agent:human-needed" --color "D93F0B" --description "Needs human decision or access"
```

Use organization colors if already established.

## Done Criteria

Do not mark Done until:

- Acceptance criteria checked.
- PR/check/test evidence linked.
- Handoff log states no remaining owner action.
- Follow-up issues created for real deferred work.
