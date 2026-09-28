# token-budget — estimating token cost before loading

Load when estimating whether a task fits within the context window, or when weighing single-agent vs multi-agent.

## Typical context budget (200K window)

| Component | Typical tokens | Notes |
|---|---|---|
| System prompt / SKILL.md | 500-2,000 | Stable, cacheable |
| Tool definitions | 100-500 / tool | Keep < 20 tools |
| Files loaded | 1,000-5,000 / file | Load only what is needed |
| Message history | Accumulates | Compact at 70% |
| Response buffer | 10-20% (~20-40K) | Required reserve |

**Thumb rule**: 1 Python file ~200 lines ~= 1,500 tokens. 1 Markdown file ~100 lines ~= 800 tokens.

## Quick estimate before loading

```
estimated_tokens = sum(file_lines * 7.5)  # ~7.5 tokens/line average
if (current_context + estimated_tokens) > 160K -> consider delegating
```

160K = 80% of 200K — safe threshold before compaction becomes mandatory.

## Context component analysis

Tool output accounts for the largest share (measured at ~83.9% of typical context):
- Search results -> summarize instead of pasting full output
- Large file reads -> read with offset/limit, not the entire file
- Same output read multiple times -> cache, read only once

## Single vs multi-agent decision

| Condition | Decision |
|---|---|
| Task estimated <= 100K tokens | Single agent |
| Task 100-160K, subtasks can be cleanly separated | Consider delegating subagents |
| Task > 160K or parallel | Multi-agent (~15x token cost) |
| Overlapping files between subtasks | Serialize even if cost is higher |

Accept 15x token cost for multi-agent only when isolation is truly necessary — not to "look parallel."

## Token-saving strategies

| Strategy | Savings | When to apply |
|---|---|---|
| Read with offset/limit instead of full file | 60-90% | File > 200 lines |
| hs:scout -> get path first | Avoids reading wrong files | Always |
| hs:repomix pack module | More compact than separate file loads | Module > 5 files |
| Observation masking of tool output | 60-80% | Verbose output > 2K tokens |
| Write intermediate state to file | Frees up history | Long output needed later |

## Action thresholds (repeated from SKILL.md)

- **< 70%**: normal
- **70-80%**: plan compaction
- **80-90%**: execute compaction
- **> 90%**: compact immediately or delegate, do not load more

## Quick self-check

Before loading a large file or spawning a subagent, ask:
1. Do I actually need the entire file, or just one section?
2. Is this information already in context (from a previous turn)?
3. If delegating, does the subagent have the minimal context needed to work independently?
