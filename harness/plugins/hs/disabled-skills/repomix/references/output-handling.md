# output-handling — token management and artifact handling for hs:repomix

Load this file when you need to estimate tokens, choose a format, or handle a large digest before loading it into an LLM.

## Estimating tokens before packing

```bash
# View token distribution for the entire repo (no file written)
repomix --token-count-tree

# Show only nodes >1000 tokens
repomix --token-count-tree 1000

# Pack + view summary (token count printed to stderr/stdout)
repomix --include "src/**" --style xml -o /tmp/check.xml
# -> last summary line: "Total tokens: X"
```

Reference thresholds (context budget):

| Model | Safe threshold |
|---|---|
| Claude Sonnet (200K) | <= 150K tokens (keep ~25% for response) |
| GPT-4 (128K) | <= 90K tokens |
| Smaller models | <= 12K tokens |

> Use `hs:context-engineering` to check the remaining budget before loading a digest.

## Choosing a format

| Format | When | Token overhead |
|---|---|---|
| `xml` (default) | LLM consumption, structured analysis | medium (has tags) |
| `markdown` | review, docs, human sharing | low (readable) |
| `plain` | minimal analysis, tight token budget | lowest |
| `json` | tool/script reading digest programmatically | highest (escaped) |

Recommendation: `xml` for LLM, `markdown` for humans + review.

## Reducing tokens when over budget

Apply in order (progressive cuts):

1. `--remove-comments` — typically saves 10-30%
2. `--no-line-numbers` — saves an additional 5-15%
3. Narrow `--include` to the required subtree
4. Add `-i` to exclude tests, dist, coverage
5. Split into multiple small packs (pack per module, load in parts)

```bash
# Example: maximum token savings
repomix \
  --include "src/core/**,src/api/**" \
  -i "**/*.test.*,**/__pycache__/,dist/" \
  --remove-comments \
  --no-line-numbers \
  --style xml \
  -o /tmp/compact-context.xml
```

## Artifact handling (no commit)

The digest is a **temporary build artifact** — never goes into git.

Safe path options:

| Path | Reason |
|---|---|
| `/tmp/` | Cleaned on reboot; unrelated to repo |
| `harness/state/` | In harness `.gitignore`; safe |
| `~/.repomix/` | Home directory; outside repo |

Do not write to: repo root, `plans/`, `docs/`, `harness/` (except `state/`).

Clean up artifacts after use:

```bash
rm /tmp/context-*.xml /tmp/context-*.md 2>/dev/null || true
```

## Security warnings

Secretlint scan runs by default. If warnings appear:

1. Read the flagged file — determine whether it is a real secret.
2. If real: do not use the digest; fix the secret in the code first.
3. If a confirmed false positive: add the file to `.repomixignore`.
4. Only use `--no-security-check` when the user explicitly confirms it.

```bash
# Confirmed false positive
echo "fixtures/mock-keys.json" >> .repomixignore
repomix --include "src/**" -o /tmp/context.xml
```

## Loading a large digest into an LLM in parts

When the digest exceeds the remaining budget, split it:

```bash
# Pack each layer separately
repomix --include "harness/hooks/**" -o /tmp/hooks.xml
repomix --include "harness/scripts/**" -o /tmp/scripts.xml
repomix --include "harness/schemas/**" -o /tmp/schemas.xml
```

Load them sequentially; use `hs:context-engineering` after each load to check the remaining budget.

## Decision flow summary

```
scope determined?
  └─ no  -> ask user / run hs:scout first
  └─ yes -> estimate tokens (--token-count-tree)
             └─ within budget -> pack, return digest
             └─ over budget   -> narrow scope or split
                                 └─ still large -> hs:context-engineering
```
