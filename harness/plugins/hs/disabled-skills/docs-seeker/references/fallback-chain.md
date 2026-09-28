# Fallback chain — when llms.txt is unavailable

## Topic-specific query

```
1. WebFetch topic URL
   context7.com/{lib}/llms.txt?topic={keyword}
   ↓ 404 / empty
2. WebFetch general URL
   context7.com/{lib}/llms.txt
   ↓ 404
3. WebFetch official site
   {official-domain}/llms.txt  (see url-patterns.md)
   ↓ not found
4. WebSearch
   "[library] llms.txt site:[official-domain]"
   ↓ not found
5. Repo analysis — hs:repomix
   (see section below)
```

## General library query

```
1. WebFetch context7.com/{lib}/llms.txt
   ↓ 404
2. WebSearch "[library] llms.txt"
   ↓ not found
3. hs:repomix on GitHub repo
   ↓ no repo
4. hs:research with multiple web sources
   (docs / blog / README / tutorials)
```

## Repo analysis via hs:repomix

Use when llms.txt is fully absent:

1. WebSearch `"[library] github repository"` — confirm the official repo is active.
2. Call `hs:repomix` with the repo URL — returns a single-source XML file.
3. From the output, read in order: `README.md`, `docs/`, `examples/`, `src/`.
4. **Required**: clearly state the source in results: `[Source: repo analysis — not official docs]`.

## Conflicting information

When multiple sources disagree:
- Priority: official docs (latest) > versioned docs > GitHub README > tutorials.
- Present both versions with context; recommend latest official source.
- State conflict reason (version diff, deprecated API, etc.).

## Specific error handling

| Error | Action |
|---|---|
| 404 topic URL | Try general URL |
| 404 general URL | Try official site, then WebSearch |
| llms.txt empty (0 URLs) | Note it; try repo analysis |
| WebFetch timeout | Do not retry — move to next step immediately |
| Library too new / docs incomplete | State the status clearly; use `tests/` and `examples/` in the repo; mark as `[INFERRED FROM CODE]` |
