---
name: hs:docs-seeker
injectable: true
description: Look up library/framework documentation via llms.txt (context7.com) — API docs, GitHub repo analysis, latest features. Use when current official docs for a library are needed.
argument-hint: "[<library> [topic] [version]]"
allowed-tools: [Read, Bash, WebFetch, WebSearch]
metadata:
  compliance-tier: knowledge
---

# hs:docs-seeker — library documentation lookup

Locates/retrieves authoritative docs from official sources. No code/file writes. Results stay in-session or hand off to `hs:research` for deeper synthesis.

No argument: `AskUserQuestion` — library name, specific topic (if any), target version (default: latest).

## Process (hard)

1. **Classify the query** — determine: (a) topic-specific ("caching in Next.js") or general ("all Astro docs"); (b) library name; (c) version. `scripts/detect-topic.js` classifies this internally on the same raw query — already wired into step 2, no separate call needed.

2. **Fetch llms.txt** — run `node scripts/fetch-docs.js "<user query>"`; it builds the context7.com URL and applies the fallback order internally (topic-specific → general → official-site on 404) per `references/url-patterns.md`. Optional: set `CONTEXT7_API_KEY` (skill `.env` or repo `.env`) to raise context7.com rate limits.
   - Manual URLs (only if the script is unavailable): `https://context7.com/{org}/{repo}/llms.txt?topic={keyword}` (topic) or `https://context7.com/{org}/{repo}/llms.txt` (general).

3. **Process results** — pipe fetch-docs.js's output into `node scripts/analyze-llms-txt.js -` (categorizes URLs critical/important/supplementary; recommends distribution: 1-3 read directly, 4-10 → up to 5 parallel agents, 11+ → phased). See `references/agent-distribution.md` for the manual fallback if scripts are unavailable.

   ```bash
   node scripts/fetch-docs.js "<user query>" | node -e "process.stdout.write(JSON.parse(require('fs').readFileSync(0,'utf8')).content||'')" | node scripts/analyze-llms-txt.js -
   ```

4. **Fallback when llms.txt is absent** — load `references/fallback-chain.md`; try WebSearch, then repo analysis via `hs:repomix`, then `hs:research` with multiple web sources.

5. **Present results** — summarize: source, version, key points (installation / API / examples). Mark info inferred from code/prior knowledge (not official docs) as `[ASSUMED]`/`[PRIOR]`. Suggest next steps: `hs:docs` (write internal docs) or `hs:research` (comparative research).

## Boundaries

- Do NOT write implementation code: only locate/present docs.
- Do NOT create markdown files: output stays in the session.
- Info inferred from source code (repo analysis) must state its source + caveats.
- Do not assume context7.com is available; always verify before using.

## Session close

Return:
- Documentation sources used (URL or file path).
- List of open questions (if any).
- Suggested next step: `hs:research` (deep evaluation) | `hs:docs` (write internal documentation).
