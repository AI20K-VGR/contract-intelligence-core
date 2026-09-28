# what-to-load-when — what to load and when

Load when unsure which files to bring into context. Apply progressive disclosure: metadata -> SKILL.md body -> references/ — in layers, not broadcast everything at once.

## Layered loading decision

```
Need to know what a skill does?
  -> Read the description (metadata, ~100 words) — do NOT open SKILL.md yet

Need workflow / modes / boundaries?
  -> Open SKILL.md body (~1-5k words)

Need specific depth (compaction, delegation, token budget)?
  -> Open the one relevant references/ file
```

## Load map by task

| Task | Load | Skip |
|---|---|---|
| Locate a file or symbol | hs:scout -> result returns path | Do not load files until path is known |
| Implement a feature | SKILL.md plan/cook + phase files | Entire codebase, unrelated files |
| Research | hs:research -> report path | Raw sources (keep the summarized report) |
| Pack module for LLM | hs:repomix -> XML/MD file | Individual files loaded repeatedly |
| Compaction >= 70% | references/compaction-guide.md | Other references |
| Designing multi-agent | references/subagent-delegation.md | -- |
| Estimating tokens | references/token-budget.md | -- |

## Information position in context (U-shape attention)

- **Start of context**: architectural decisions, hard constraints, acceptance criteria
- **End of context**: next steps, open questions, action items
- **Middle of context**: tool output already read, large files — most likely to be lost

-> Place IMPORTANT things at the start or end. Never put constraints only in the middle.

## Signs of loading too much

- Tool output > 80% of context -> apply observation masking (summary + ref-id)
- Loading the entire file when only one function is needed -> read with correct offset/limit
- Reading the same file multiple times -> cache or write a summary to a scratchpad
- Spawning a subagent for a task that fits in a single pass -> keep it as a single agent

## Signs of loading too little

- Guessing file paths instead of knowing them exactly -> use hs:scout first
- Output has many `[ASSUMED]` tags -> more sources needed
- Subagent returns NEEDS_CONTEXT -> prompt is missing specific files

## Write strategy rules

When output is large or will be needed again later:
- Write artifacts to `plans/reports/` (reports, research)
- Write intermediate state to a temporary scratchpad
- Return the absolute path instead of pasting content into the chat
- Controller reads on demand — do not keep everything in the session
