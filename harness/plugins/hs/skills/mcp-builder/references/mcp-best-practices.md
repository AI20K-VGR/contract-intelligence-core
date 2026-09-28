# MCP Server Best Practices

Read this file in Phase 1 before designing tools.

---

## Naming conventions

**Python**: `{service}_mcp` — `slack_mcp`, `github_mcp`
**TypeScript**: `{service}-mcp-server` — `slack-mcp-server`, `github-mcp-server`

**Tool names**: snake_case + service prefix + action-oriented verb
- Format: `{service}_{action}_{resource}`
- Examples: `slack_send_message`, `github_create_issue`, `asana_list_tasks`
- Do not use generic names (`send_message`) — conflicts when multiple servers run together.

---

## Tool design principles

### Workflow-first (most important)
Do not just wrap endpoints — build tools for real workflows:
- `schedule_event` = check availability + create event (1 tool, not 2)
- Prefer tools that enable a complete task over individual API calls.

### Context-efficient output
Agents have a limited context window — every token must count:
- High-signal output, do not dump all data
- Default: human-readable name instead of ID (`"John Doe"` not `"U123456"`)
- Support `response_format`: `markdown` (default, human-readable) and `json` (machine-readable)
- Markdown: timestamps as "2024-01-15 10:30 UTC", show name + ID in parentheses, drop excess metadata.

### Actionable errors
Errors must guide the agent toward correct usage:
- Good: `"Try filter='active_only' to reduce results"`
- Bad: `"Too many results"`

### Tool annotations (required)
```
readOnlyHint    — tool does not modify the environment
destructiveHint — tool may delete/overwrite data
idempotentHint  — calling multiple times with the same args produces the same result
openWorldHint   — tool interacts with an external system
```
Annotations are hints, not security guarantees.

---

## Pagination

Tools that return resource lists must support pagination:
- Params: `limit` (default 20-50), `offset`
- Response metadata: `has_more`, `next_offset`, `total_count`
- Do not load all results into memory.

```json
{
  "total": 150,
  "count": 20,
  "offset": 0,
  "items": [...],
  "has_more": true,
  "next_offset": 20
}
```

---

## Character limit & truncation

```python
CHARACTER_LIMIT = 25000  # define at module level

if len(result) > CHARACTER_LIMIT:
    truncated_data = data[:max(1, len(data) // 2)]
    response["truncated"] = True
    response["truncation_message"] = (
        f"Truncated from {len(data)} to {len(truncated_data)} items. "
        "Use 'offset' parameter or add filters to see more."
    )
```

---

## Transport selection

| Transport | When to use |
|-----------|-------------|
| **stdio** | Local tool, CLI, subprocess, single-user |
| **http**  | Web service, multiple concurrent clients |
| **sse**   | Real-time push, streaming data |

Stdio: do NOT log to stdout (breaks the protocol) — use stderr.

---

## Security

**API keys**: env var, never hardcode.
**Input validation**: use Pydantic/Zod — validate paths, URLs, and commands to prevent injection.
**Error exposure**: do not leak internal error details to the client — log server-side, return a useful message without revealing the stack trace.
**Data collection**: collect only what the tool needs; do not collect unnecessary PII.
**HTTPS**: all network calls use HTTPS, validate certificates.

---

## Error handling (MCP protocol)

Tool errors must be in the **result object**, not a protocol-level error — so the LLM can see/handle them:

```python
return types.CallToolResult(
    isError=True,
    content=[types.TextContent(type="text", text=f"Error: {str(error)}")]
)
```

---

## Documentation requirements

Each tool requires:
- A one-line summary of its function
- Full explanation of params + examples
- Return value schema (for dict/JSON)
- When to use / when not to use
- Error handling — how to continue when each type of error occurs
