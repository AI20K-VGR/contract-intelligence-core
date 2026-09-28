# subagent-delegation — fragmenting tasks via subagents

Load when designing multi-agent systems or when a heavy task requires context isolation.

## Core principle

Subagents exist to **isolate context**, not to play a role. Each subagent receives minimal context — question + specific files + acceptance criteria — not the full controller history.

## When to delegate

| Condition | Action |
|---|---|
| Parallel tasks with clear file ownership | Spawn in parallel |
| Controller context >= 70%, task still long | Delegate to free up context |
| Scope > 5 independent sources (research) | hs:research --delegate |
| Shared files between subtasks | Serialize, do not parallelize |

## Multi-agent token cost

| Architecture | Multiplier | Use when |
|---|---|---|
| Single agent | 1x | Simple task |
| Single + tools | ~4x | Moderate complexity |
| Multi-agent | ~15x | Context isolation is truly necessary |

Accept 15x only when isolation benefits are clear — do not spawn subagents for simple tasks that can be done in one pass.

## Subagent prompt — required checklist

Every subagent prompt must include:

```
- Task: [specific question/work]
- Files to read: [absolute paths]
- Files may modify: [or "none — research only"]
- Acceptance criteria: [done condition]
- Constraints: [scope limits]
- Reports path: plans/reports/
```

**Do NOT** paste conversation history. Summarize only the decisions needed for the subtask.

## Returning results to the controller

Subagent returns:
- Summary in 1-2 sentences
- Absolute path to output file (report / artifact)
- Status: `DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT`

Controller reads summary + file — does not re-read the full subagent output.

## Harness orchestration rule

Full rules at `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` — read when complex choreography is needed (plan->cook handoff, multi-session, team mode).

Hard invariants from harness-contract:
- Advisory subagents must not mutate plan/code
- Parallelism only when file ownership does not overlap

## Failure handling

| Failure | Handling |
|---|---|
| BLOCKED | Change context/scope, do not retry the same prompt |
| NEEDS_CONTEXT | Provide the missing information then resume |
| File conflict | Serialize instead of parallelizing |
