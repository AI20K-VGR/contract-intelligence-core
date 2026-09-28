# Source triangulation — gathering multiple sources (on-demand)

Run in step 2, before synthesis. Goal: don't conclude from one source; triangulate >=2 independent sources per important claim before treating it settled. (The `[ASSUMED]` tag threshold itself is the single 1-anchor rule in SKILL.md step 3 — triangulation here is the confidence practice, not a second gate.)

## Source priority order

1. **Official docs** — framework/library homepage, API reference, changelog
2. **Maintainer blog / release post** — from the author; prefer if recent
3. **Production case study** — article from a company using it in practice (Stripe, Shopify, Netflix eng blog...)
4. **Peer-reviewed / conference paper** — for academic topics
5. **Recognised community blog** — CSS-Tricks, web.dev, Kent C. Dodds, Julia Evans...
6. **Tutorial / Stack Overflow** — use to reproduce, NOT as the sole source

## Search strategy (breadth mode)

Run up to 5 WebSearch calls in parallel with different keywords:
- `"<topic>" site:docs.<domain>.com`
- `"<topic>" best practices 2025`
- `"<topic>" production OR benchmark OR case study`
- `"<topic>" security OR vulnerability`
- `"<topic>" alternatives OR comparison`

Pin results: write `[source N: <URL>, <date>]` next to the claim — serves as the evidence anchor.

## Drill strategy (depth mode)

Once the primary source is identified:
1. Read the full changelog / migration guide (find breaking changes, version range)
2. Find related GitHub issues (open + closed) — real bug patterns
3. Fetch each important URL directly with WebFetch; do not use WebSearch summaries as final claims

## Existence checks (a file, path, repo, or API)

To confirm whether a repo file or path EXISTS, query the authenticated API, not a web search. Use `gh api repos/{owner}/{repo}/contents/{path}` (or the project's API with a token). An unauthenticated code search returns a "sign in to search" page, `0 results`, or HTTP 429 — none of which mean the file is absent. Absence of a search result is not evidence of absence. Never conclude "the
feature/file does not exist" from an empty or rate-limited unauthenticated search.

## Signs of a weak source (drop or deprioritize)

- No publish date, or older than 2 years on a fast-moving topic
- No author / anonymous wiki
- Cross-posted marketing / vendor blog with no technical depth
- Claims without code examples or real benchmark numbers

## Output per source

Write into the notes section of the report:
```
[N] <URL> | <author/org> | <date> | credibility: [high|medium|low] | note: <1 line>
```

If fewer than 2 independent sources exist for an important claim, note the confidence gap; add an open question at report end — apply SKILL.md step 3's 1-anchor rule to decide whether the claim gets tagged `[ASSUMED]` (or `[PRIOR]` if it rests on training knowledge).
