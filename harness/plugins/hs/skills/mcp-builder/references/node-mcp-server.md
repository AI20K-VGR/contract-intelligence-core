# Node/TypeScript MCP Server — Implementation Guide

Use together with `mcp-best-practices.md`. Load in Phase 1 + Phase 2.

Fetch full SDK documentation: `https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md`

---

## Quick reference

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import axios, { AxiosError } from "axios";

const server = new McpServer({
  name: "service-mcp-server",   // naming: {service}-mcp-server
  version: "1.0.0"
});

const CHARACTER_LIMIT = 25000;
const API_BASE_URL = "https://api.service.com/v1";
```

---

## Project structure

```
service-mcp-server/
├── src/
│   └── index.ts          # entry point — server + all tools
├── package.json
├── tsconfig.json
└── dist/                 # build output
```

**package.json** (essentials):
```json
{
  "name": "service-mcp-server",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "latest",
    "zod": "^3.0.0",
    "axios": "^1.0.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/node": "^20.0.0"
  }
}
```

**tsconfig.json**:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "./dist",
    "strict": true,
    "noImplicitAny": true,
    "esModuleInterop": true
  },
  "include": ["src/**/*"]
}
```

---

## Tool registration pattern

```typescript
// Input schema with Zod
const SearchInputSchema = z.object({
  query: z.string().min(1).max(200)
    .describe("Search string (e.g. 'john', 'team:marketing')"),
  limit: z.number().int().min(1).max(100).default(20)
    .describe("Max results (default 20)"),
  offset: z.number().int().min(0).default(0)
    .describe("Pagination offset"),
  response_format: z.enum(["markdown", "json"]).default("markdown")
    .describe("Output format")
}).strict();

server.registerTool(
  "service_search_items",
  {
    title: "Search Items",
    description: `Search items in Service by name or filter.

Parameters:
  - query (string): Search string
  - limit (number, optional): Max results 1-100, default 20
  - offset (number, optional): Pagination offset, default 0
  - response_format ("markdown"|"json"): Output format, default "markdown"

Returns: Paginated result {total, count, offset, items, has_more, next_offset}
  or error string.

Use when: finding items by keyword.
Don't use when: you have an ID — use service_get_item instead.`,
    inputSchema: SearchInputSchema,
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: true
    }
  },
  async (params): Promise<{ content: Array<{ type: "text"; text: string }> }> => {
    try {
      const data = await makeApiRequest("items/search", {
        params: { q: params.query, limit: params.limit, offset: params.offset }
      });
      const result = formatPaginated(data, params.offset, params.response_format);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: handleApiError(e) }] };
    }
  }
);
```

---

## Shared utilities

```typescript
// API client
async function makeApiRequest(
  endpoint: string,
  options: { method?: string; params?: Record<string, unknown>; data?: unknown } = {}
): Promise<Record<string, unknown>> {
  const response = await axios({
    method: options.method ?? "GET",
    url: `${API_BASE_URL}/${endpoint}`,
    params: options.params,
    data: options.data,
    timeout: 30000,
    headers: { Authorization: `Bearer ${process.env.SERVICE_API_KEY}` }
  });
  return response.data as Record<string, unknown>;
}

// Error handler
function handleApiError(e: unknown): string {
  if (e instanceof AxiosError) {
    const status = e.response?.status;
    if (status === 404) return "Error: Resource not found. Check the ID is correct.";
    if (status === 403) return "Error: Permission denied.";
    if (status === 429) return "Error: Rate limit exceeded. Wait before retrying.";
    if (e.code === "ECONNABORTED") return "Error: Request timed out. Try again.";
    return `Error: API request failed (${status ?? "unknown"})`;
  }
  return `Error: ${e instanceof Error ? e.message : String(e)}`;
}

// Pagination formatter
function formatPaginated(
  data: Record<string, unknown>,
  offset: number,
  format: string
): string {
  const items = (data.items as unknown[]) ?? [];
  const total = (data.total as number) ?? 0;
  const hasMore = total > offset + items.length;

  const response = {
    total,
    count: items.length,
    offset,
    items,
    has_more: hasMore,
    next_offset: hasMore ? offset + items.length : null
  };

  let result = JSON.stringify(response, null, 2);
  let emitted = items;
  let wasTruncated = false;

  if (result.length > CHARACTER_LIMIT) {
    const half = items.slice(0, Math.max(1, Math.floor(items.length / 2)));
    const truncated = {
      ...response,
      items: half,
      truncated: true,
      truncation_message: `Truncated from ${items.length} to ${half.length} items. Use 'offset' or add filters.`
    };
    result = JSON.stringify(truncated, null, 2);
    emitted = half;
    wasTruncated = true;
  }

  if (format === "markdown") {
    let md = formatMarkdown(emitted);
    if (wasTruncated) {
      md += `\n\n_...truncated from ${items.length} to ${emitted.length} items. Use 'offset' or add filters._`;
    }
    return md;
  }
  return result;
}

function formatMarkdown(items: unknown[]): string {
  const lines: string[] = [];
  for (const item of items as Array<Record<string, unknown>>) {
    lines.push(`## ${item.name} (${item.id})`);
    lines.push(`- **Status**: ${item.status ?? "unknown"}`);
    lines.push("");
  }
  return lines.join("\n");
}
```

---

## Server startup

```typescript
async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // Stdio: do NOT console.log — use console.error for debug output
  console.error("Service MCP Server running");
}

main().catch((e) => {
  console.error("Fatal:", e);
  process.exit(1);
});
```

---

## Testing (do not run directly)

MCP server blocks stdin/stdout. Use:
- `npm run build` — verify TypeScript compiles, check that `dist/index.js` exists
- Run in tmux then test from outside the main process
- Do not run `node dist/index.js` directly in the main session

---

## Hard TypeScript rules

- `strict: true` in tsconfig — required
- Do not use `any` — use `unknown` then narrow
- Explicit `Promise<T>` return type for async functions
- Zod `.strict()` on all input schemas to reject extra fields
- `const` instead of `let` where possible

---

## Quality checklist

**Design**
- [ ] Tools enable complete workflows (not just endpoint wrappers)
- [ ] Service prefix in all tool names (`service_action_resource`)
- [ ] Error messages guide agent toward correct usage

**Implementation**
- [ ] `npm run build` passes without errors
- [ ] Shared utilities extracted (makeApiRequest, handleApiError, formatPaginated)
- [ ] Zod `.strict()` on all input schemas
- [ ] Annotations present on all tools
- [ ] CHARACTER_LIMIT check + truncation with guidance
- [ ] Pagination for tools that return lists
- [ ] Explicit return types on all async functions
- [ ] Tool description complete: summary, params, returns (schema), examples, errors

**Security**
- [ ] API key from `process.env`, never hardcoded
- [ ] No `console.log` to stdout (use `console.error`)
- [ ] No internal error detail leaked to client
