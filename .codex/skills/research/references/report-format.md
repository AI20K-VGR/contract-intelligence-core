# Report format — research report structure (on-demand)

Run in step 5. Research output saved to `plans/reports/<slug>-research-<YYMMDD>.md`.

## Required structure

```markdown
# Research: <Central question>

**Mode**: breadth | depth  
**Date**: YYYY-MM-DD  
**Sources reviewed**: N  

## Summary (<=5 lines)
<Key findings + priority recommendation>

## Options / Comparison
<Trade-off matrix or detailed description (depth mode)>

| Option | Pros | Cons | Project fit |
|---|---|---|---|
| A | ... | ... | [+/-/~] |

## Recommendation
**Priority 1**: <name> — <brief rationale, with conditions>  
**Fallback**: <name> — <when to choose>

## Evidence and references
[N] <URL> | <author/org> | <date> | <VERIFIED|ASSUMED>

## Open questions
- [ASSUMED] <claim> — source needed: <suggested direction>
- <question outside current scope>
```

## Writing rules

- **Sacrifice grammar for concision**: short sentences, bullets, no filler prose.
- No "equal-weight listing" recommendations — must rank.
- Code snippets must include: language, version, source.
- Benchmark numbers: only from vendor-independent sources; state measurement conditions.
- an `[ASSUMED]`/`[PRIOR]` tag must appear both in the body and in "Open questions".

## File naming

Pattern: `plans/reports/<slug>-research-<YYMMDD>.md` Slug = kebab-case from the main topic (<=4 words). Examples:
- `plans/reports/realtime-sync-options-research-260615.md`
- `plans/reports/auth-lib-biometric-research-260615.md`

Do not use generic names: `research.md`, `report.md`, `notes.md`.

## When delegating to the researcher agent

Agent additionally receives:
- absolute output path
- central question identified in step 1
- evaluation criteria
- mode (breadth / depth)
- max sources

Agent returns: absolute path to the saved file. Controller does not rewrite output — only relays path + summary to the user.
