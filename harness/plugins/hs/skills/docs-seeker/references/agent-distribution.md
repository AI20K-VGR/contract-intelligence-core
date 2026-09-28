# Agent Distribution — processing llms.txt results

## Distribution rules by URL count

| URLs in llms.txt | Strategy |
|---|---|
| 1-3 | Read directly with WebFetch, process sequentially |
| 4-10 | Multiple subagents in parallel; group URLs into balanced batches |
| 11-20 | Split into phases: critical URLs first, important URLs second |
| 21+ | Phase 1 — critical; Phase 2 — important; skip supplementary unless requested |

## Classifying URLs in llms.txt

Classify by name/path:

- **Critical**: `getting-started`, `installation`, `api`, `reference`, `overview`, `readme`
- **Important**: `guide`, `tutorial`, `configuration`, `examples`, `cookbook`
- **Supplementary**: `changelog`, `migration`, `faq`, `troubleshooting`, `blog`

## Scaling fan-out

Size subagent count to the work — balance URLs across batches so no agent is starved/overloaded. For 11+ URLs, prioritize critical first and ask the user before reading additional phases.

## Distribution examples

**4-10 URLs (Astro framework):**
```
llms.txt → 8 URLs

Single phase, 2 agents in parallel:
  Agent 1: getting-started, installation, core-concepts (3 URLs)
  Agent 2: components, configuration, api-reference (3 URLs)
  Sequential: layouts, integrations (remaining 2 URLs)
```

**11+ URLs (Next.js full docs):**
```
llms.txt → 15 URLs

Phase 1 — critical (2 agents):
  Agent 1: getting-started, routing, rendering
  Agent 2: data-fetching, api-reference

Phase 2 — important (ask user first):
  7 URLs remaining; ask user whether they are needed.
```

## Synthesizing results

After collection, present in this order:
1. Installation / requirements
2. Core concepts
3. API / configuration
4. Practical examples
5. Open questions + suggested next steps
