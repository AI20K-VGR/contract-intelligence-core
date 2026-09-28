---
name: hs:use-mcp
injectable: true
description: "Discover and execute MCP server tools. Two execution paths: LLM CLI (gemini + GEMINI_API_KEY primary for headless/CI, agy an independent OAuth/Antigravity path) or direct scripts (deterministic, specific tool/server). Use for MCP integrations, tool execution, capability discovery, persistent tool catalog."
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep]
argument-hint: "[task]"
metadata:
  compliance-tier: workflow
---

# MCP Tool Discovery & Execution

Two execution paths for the Model Context Protocol (MCP):

| Path | When | Trade-off |
|------|------|-----------|
| **LLM CLI** | Default. LLM picks the right tool from natural language. | Non-deterministic; needs `gemini` (or `agy`) installed. |
| **Direct Scripts** | Specific tool, specific server, scripted/CI workflows, no CLI available. | Deterministic; you must know the tool name + arg shape. |

Both paths read MCP servers from `.claude/.mcp.json` and preserve main-context budget — the LLM never loads every tool definition.

## Path 1: LLM CLI (gemini primary for headless/CI · agy independent OAuth/Antigravity path)

The primary CLI for headless/CI is **`gemini` + `GEMINI_API_KEY`** — keyed auth survived the 2026-06-18 OAuth-tier cut and runs headless; full story: `references/llm-cli-integration.md`.
`agy` (Antigravity) is an **independent** OAuth/Antigravity path — its own lane for interactive/Antigravity-workspace use (loads `AGENTS.md`, needs one-time sign-in), not a fallback bolted onto gemini.
Neither CLI auto-loads a system-prompt file, so prepend the JSON proxy contract
(`references/mcp-proxy-contract.md`) into the piped prompt.

```bash
export GEMINI_API_KEY="your-ai-studio-key"   # headless auth; unaffected by the 2026-06-18 change
# Model id comes from the single-source resolver (data/models.yaml); $GEMINI_MODEL overrides.
MODEL=$(python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/resolve_model.py)
# Read the contract text (between the markers) from mcp-proxy-contract.md before piping:
CONTRACT=$(sed -n '/---BEGIN CONTRACT---/,/---END CONTRACT---/p' references/mcp-proxy-contract.md | sed '1d;$d')
# PRIMARY — gemini (headless, key-based):
printf '%s\n\nTASK: %s' "$CONTRACT" "$ARGUMENTS" | gemini -y -m "$MODEL" -p
# INDEPENDENT PATH — agy (OAuth/Antigravity; requires prior sign-in):
#   which gemini || printf '%s\n\nTASK: %s' "$CONTRACT" "$ARGUMENTS" | agy --dangerously-skip-permissions --model "$MODEL" -p
```

The prepended contract enforces structured JSON responses:

```json
{"server":"name","tool":"name","success":true,"result":<data>,"error":null}
```

**Error detection.** Treat as failure when:
- CLI exit code != 0
- Output contains `GaxiosError` / `RESOURCE_EXHAUSTED` / `MODEL_CAPACITY_EXHAUSTED` / `PERMISSION_DENIED` / `UNAUTHENTICATED`

**Model resolution order** (all model ids live in `data/models.yaml` — never hardcode):
1. `resolve_model.py` → the `default` model (`$GEMINI_MODEL` overrides).
2. On failure, `resolve_model.py --fallback` → the `fallback` model.
3. Still failing → `resolve_model.py --list` and let the LLM pick a model from `available`.

**Transport fallback** (orthogonal to model): on `gemini` failure → try `agy`; if that is unavailable or also fails → fall through to Path 2.

**Setup.** Both CLIs read MCP servers from the global `~/.gemini/config/mcp_config.json` in print mode (neither reads `.gemini/settings.json`). Merge the project's `.claude/.mcp.json` servers into that global file — see the integration guide.

See [`references/llm-cli-integration.md`](references/llm-cli-integration.md) for the full integration guide, auth, and error-marker reference.

## Path 2: Direct Scripts (fallback / scripted workflows)

The `scripts/` directory ships a self-contained MCP client built on `@modelcontextprotocol/sdk`. Use when no LLM CLI is available, or you need deterministic invocation of a specific tool/args (CI scripts, debugging, reproducible runs).

```bash
cd "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/use-mcp/scripts && npm install      # one-time
npx tsx cli.ts list-tools                             # snapshot all tools → assets/tools.json
npx tsx cli.ts list-prompts
npx tsx cli.ts list-resources
npx tsx cli.ts call-tool <server> <tool> '<json-args>'
```

`list-tools` persists the catalog to [`assets/tools.json`](assets/tools.json) with full schemas — useful for offline browsing, version-controlled tool inventories, and LLM-driven selection without a live MCP connection.

**Module layout:**

| File | Role |
|------|------|
| `scripts/mcp-client.ts` | `MCPClientManager` class — config loader, multi-server stdio connector, list/call wrappers, lifecycle cleanup |
| `scripts/cli.ts` | CLI entry: `list-tools`, `list-prompts`, `list-resources`, `call-tool`, plus signal handlers and global timeout (`MCP_TIMEOUT` env, default 120s) |
| `scripts/package.json` | Pinned `@modelcontextprotocol/sdk`, `tsx`, `typescript` |
| `scripts/smoke-test.sh` | End-to-end smoke test (no server required) — `bash claude/skills/use-mcp/scripts/smoke-test.sh` |
| `assets/tools.json` | Persisted tool catalog (regenerated by `list-tools` — backed up + restored by smoke test) |

## Pattern Reference

| Pattern | Use |
|---------|-----|
| **LLM CLI auto-execution** | Default. Natural-language task → gemini (or agy) picks tool → JSON result. |
| **Deterministic invocation** | `cli.ts call-tool <server> <tool> '<json>'` when you know exactly what you want. |
| **LLM-driven selection from catalog** | Run `list-tools` once, then have the main LLM read `assets/tools.json` and pick. Cheaper than re-querying servers. |
| **Multi-server orchestration** | Each tool is tagged with its source server; the client routes calls correctly across N configured servers. |

## Important Notes

- **Stdin piping is mandatory for LLM-CLI MCP tasks.** Inline `-p "..."` is fine for non-MCP tasks (research, analysis) but stdin-piping the contract is more reliable for MCP server init in headless mode (both gemini and agy).
- **The prepended proxy contract is the response-format contract.** Don't bypass it — parseable JSON makes the output usable. See `references/mcp-proxy-contract.md`.
- **Direct scripts are not optional infrastructure.** They are the only path when no LLM CLI is available, when MCP servers are stdio-only and not registered with Claude Code's own MCP layer, or when a task needs deterministic tool selection. Built-in `ListMcpResourcesTool` / `ReadMcpResourceTool` only see servers Claude Code itself has registered — different namespace from
  `.claude/.mcp.json`.
- **Chrome DevTools MCP is profile-blind.** Before using Chrome DevTools MCP navigation, decide whether the task needs a specific real Chrome profile. If not, use the MCP tools normally for generic browser inspection. If it does, invoke `hs:chrome-profile` first. Use `chrome-profile open --json <key> <url>`, select the page whose URL contains the returned `bind_selector`, then use Chrome
  DevTools MCP only to inspect or operate on that selected page. Do not use raw `new_page` or `navigate_page` for profile-scoped work.
- **`mcp-builder` is NOT a fallback for tool execution.** `mcp-builder` builds new MCP servers from templates; it does not consume existing ones. If a needed server is missing entirely, that's when `mcp-builder` applies.

## Anti-Pattern for MCP Tasks

```bash
# AVOID for MCP tasks — inline prompts report MCP init issues in headless mode
gemini -y -m "$MODEL" -p "..."

# Use stdin piping (with the prepended contract) instead
printf '%s\n\nTASK: %s' "$CONTRACT" "..." | gemini -y -m "$MODEL" -p
```

## Technical Details

- [`references/configuration.md`](references/configuration.md) — `.mcp.json` schema, env file lookup order, validation
- [`references/mcp-protocol.md`](references/mcp-protocol.md) — JSON-RPC details, transports (stdio / HTTP+SSE), error codes
- [`references/llm-cli-integration.md`](references/llm-cli-integration.md) — gemini (primary headless/CI) + agy (independent OAuth/Antigravity path) setup, auth, error markers, model-tier guidance
- [`references/mcp-proxy-contract.md`](references/mcp-proxy-contract.md) — the JSON contract prepended to every LLM-CLI MCP call
