# MCP Transports

An MCP server must support **stdio**, **SSE**, and **Streamable HTTP**. One `Server` instance, three transport adapters.

## Selecting a transport

Entry (`bin.ts`):

```ts
const transport = process.env.MCP_TRANSPORT ?? flag("--transport") ?? "stdio";
switch (transport) {
  case "stdio": await startStdio(server); break;
  case "sse":   await startSse(server, { port }); break;
  case "http":  await startStreamableHttp(server, { port }); break;
  default: die(`unknown transport: ${transport}`);
}
```

## stdio

Default for local agent processes (Claude Code, Cursor, etc.).

```ts
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
const t = new StdioServerTransport();
await server.connect(t);
```

- No auth at the transport layer: trust the parent process.
- Do not write non-protocol bytes to stdout; logs go to stderr.
- Credentials from env + config files (same chain as the CLI).

## SSE (legacy)

Kept for compatibility with older clients; document Streamable HTTP as preferred.

```ts
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
app.get("/sse", async (c) => {
  const t = new SSEServerTransport("/messages", c.res);
  await server.connect(t);
});
app.post("/messages", (c) => t.handlePostMessage(c.req, c.res));
```

- Per-connection transport instance.
- Bearer token auth before upgrade.
- Heartbeats to prevent proxies from idling the connection.

## Streamable HTTP (preferred remote)

The modern transport. Required for Cloudflare Workers and most PaaS platforms.

```ts
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
app.all("/mcp", async (c) => {
  const t = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => crypto.randomUUID(),
  });
  await server.connect(t);
  return t.handleRequest(c.req.raw, c.res);
});
```

- Single endpoint: POST (requests) + GET (stream).
- The `mcp-session-id` header maps to server state.
- Works behind standard HTTP load balancers.
- Supports resumable streams.

## Session state

- Local (stdio): in-memory per process.
- Remote (SSE, HTTP): keyed by session ID.
  - Cloudflare Workers: use **Durable Objects** for per-session state.
  - Docker/Node: Redis or in-memory + sticky sessions.

## Auth

Applies to SSE + HTTP only. stdio trusts the parent process.

```
Authorization: Bearer <token>
```

Reject early with `401` + MCP-level error on the first request. Do not leak whether a token exists. Rate-limit by token.

Token sources by deploy target:
- Cloudflare: Workers Secrets (`wrangler secret put MCP_TOKEN`)
- Docker: env var from a secret manager; do not bake into the image.
- Self-host: env var; `.env` only when the host filesystem is trusted.

## Tool schema

Register tools once on the `Server`: every transport exposes the same tool set.

```ts
server.tool(
  "list_projects",
  "List all projects. Returns concise records (id, name, status). Use format: detailed for full data.",
  {
    format: z.enum(["concise", "detailed"]).default("concise"),
    limit: z.number().int().min(1).max(100).default(25),
  },
  async (args, ctx) => core.listProjects({ ...args, auth: ctx.auth }),
);
```

## Health and observability

Expose on HTTP transports:
- `GET /healthz` — 200 when the server is up and core dependencies are reachable.
- `GET /readyz` — 200 when ready to serve.
- Structured logs (JSON) to stderr with `trace_id`, `session_id`, `tool_name`,
  `duration_ms` — do not log args.

Do not expose metrics without auth. Prometheus if needed: mount on a separate internal port.
