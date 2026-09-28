# compaction-guide — context compression guide

Load when context >= 70%. Goal: reduce tokens by 50-70%, lose < 5% quality.

## Method: anchored iterative (recommended)

Update the existing summary incrementally — do NOT regenerate from scratch.

```
## Session goal
Original goal: [keep as-is]

## Files edited
- path/file.py: [description of change]

## Finalized decisions
- [decision + brief rationale]

## Current state
[progress in 1-3 sentences]

## Next steps
1. [next action]
```

## Drop order (drop these first)

1. Old tool output (especially file reads and completed search results)
2. Rounds of debate that have been finalized
3. Docs that were loaded and fully summarized
4. **KEEP**: system prompt, open decisions, files currently being edited, next steps

## Activation thresholds

| Context % | Action |
|---|---|
| 70-80% | Plan compaction — identify what can be dropped |
| 80-90% | Execute compaction; write artifacts to file |
| > 90% | Compact immediately + delegate remaining tasks to subagent |

## Artifact trail (weakest point — requires attention)

After compaction, keep track of:
- Files created / edited / read (exact names)
- Function/variable/error names being tracked
- All `[ASSUMED]` items not yet resolved

## Evaluating compaction

After compression, probe with 3 questions:
1. "Which files were edited?" -> check artifact trail
2. "Which decisions were finalized?" -> check decision retention
3. "What is the next step?" -> check continuity
