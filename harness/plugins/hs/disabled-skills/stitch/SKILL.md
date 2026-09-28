---
name: hs:stitch
injectable: true
description: "AI design generation with Google Stitch. Generate UI designs from text prompts, export Tailwind/HTML/DESIGN.md, orchestrate design-to-code pipeline. Use for rapid prototyping, UI generation, design exploration."
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob]
argument-hint: "[design prompt or action]"
metadata:
  compliance-tier: workflow
---

# Google Stitch — AI Design Generation

Generate high-fidelity UI designs from text prompts via Google Stitch. Export Tailwind/HTML, orchestrate design-to-code pipelines with existing UI skills.

**Free tier:** 400 credits/day + 15 redesign credits/day. Resets at midnight UTC.

## Setup

### 1. API Key

Get an API key at https://stitch.withgoogle.com → Settings → API Keys.

Add `STITCH_API_KEY=sk_...` to your environment — `~/.claude/.env`, or a `.env` beside the scripts.

### 2. Install SDK

```bash
cd "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/stitch/scripts && npm install
```

### 3. Optional

```bash
# In ~/.claude/.env
STITCH_PROJECT_ID="my-project"    # Default project (auto-creates "harness-default" if unset)
STITCH_QUOTA_LIMIT="200"          # Override daily limit
```

### 4. MCP Server (optional)

Add to `~/.claude/.mcp.json` for native design context in Claude Code:

```json
{
  "mcpServers": {
    "stitch": {
      "command": "npx",
      "args": ["@_davideast/stitch-mcp", "proxy"],
      "env": { "STITCH_API_KEY": "${STITCH_API_KEY}" }
    }
  }
}
```

See `references/stitch-mcp-setup.md` for alternative options (gcloud, auto-installer).

## Quick Start

```bash
# Check quota
npx tsx "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/stitch/scripts/stitch-quota.ts check

# Generate design
npx tsx "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/stitch/scripts/stitch-generate.ts "A checkout page with payment form and cart summary"

# Export as HTML + DESIGN.md
npx tsx "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/stitch/scripts/stitch-export.ts <screen-id> --format all --output ./stitch-exports/
```

## Actions

`generate`, `export`, `quota`, `edit`, and per-repo project isolation — full command flags, outputs, project-ID resolution order in [references/actions.md](references/actions.md).

## Orchestration Pipeline

### Design-to-Code Flow

1. **Check quota** — Run `stitch-quota.ts check`. If exhausted, suggest `hs:ui-ux` fallback.
2. **Generate** — Run `stitch-generate.ts` with user's design prompt. If a plan is active, pass `--project-name "{repo}/{plan-slug}"` for isolation.
3. **Review** — Show generated design image to user for feedback
4. **Variants** (optional) — Generate alternatives if user wants exploration
5. **Export** — Run `stitch-export.ts --format all` to get HTML + DESIGN.md
6. **Implement** — Hand off exported artifacts to the right implementation skill; routing table in `references/design-to-code-pipeline.md` § Skill Routing
7. **Track quota** — Run `stitch-quota.ts increment`

### Handoff Protocol

- Export creates `DESIGN.md` in project root or plan directory
- Paste `DESIGN.md` contents (or path) into the handoff instruction to the implementation skill — no automatic detection exists
- DESIGN.md takes precedence over text descriptions when explicitly handed off
- If no DESIGN.md exists, skills fall back to normal text-based design flow

See `references/design-to-code-pipeline.md` for detailed patterns and examples.

## Quota Management

- 400 credits/day + 15 redesign/day, resets at midnight UTC
- Local tracking via `~/.sdlc-harness/.stitch-quota.json`
- Warns when remaining credits < 20%
- **Fallback:** When exhausted, use `hs:ui-ux` for text-based design generation

See `references/quota-management.md` for strategies.

## Limitations

- **No React export** — HTML/Tailwind only; Claude converts to React/Vue components
- **Non-responsive layouts** — Must add breakpoints manually during implementation
- **No animations** — Static designs only; add micro-interactions in code
- **Single-user** — No multiplayer/collaboration features
- **Hard daily quota** — No paid tier to increase limits
- **Generic output risk** — Combine with style guides for differentiation

## References

| Topic | File |
|-------|------|
| Actions | `references/actions.md` |
| SDK API | `references/stitch-sdk-api.md` |
| MCP Setup | `references/stitch-mcp-setup.md` |
| Pipeline Patterns | `references/design-to-code-pipeline.md` |
| Quota Strategy | `references/quota-management.md` |

## See also

- For hi-fi HTML production (clickable prototypes, animated films, HTML decks, MP4/PPTX), see the
  **huashu-design** pointer (and the wider external design-skill catalog) in `hs:ui-ux`.
