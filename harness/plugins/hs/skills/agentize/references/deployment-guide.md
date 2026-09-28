# Deployment Guide (MCP)

Three main deploy targets. Choose one (or ship all three) based on the Phase 3 decision.

## Cloudflare Workers

Best for: global edge, low ops, per-session state via Durable Objects.

`wrangler.toml`:

```toml
name = "<tool>-mcp"
main = "dist/worker.js"
compatibility_date = "2025-01-01"
compatibility_flags = ["nodejs_compat"]

[[durable_objects.bindings]]
name = "MCP_SESSION"
class_name = "McpSession"

[[migrations]]
tag = "v1"
new_classes = ["McpSession"]

[vars]
MCP_TRANSPORT = "http"
```

The worker entry wires Streamable HTTP to `/mcp` and routes to the `McpSession` Durable Object keyed by `mcp-session-id`. Secrets via `wrangler secret put MCP_TOKEN`.

Deploy: `wrangler deploy`.

Notes:
- SSE works but Streamable HTTP is preferred.
- stdio does not run on Workers: build + test locally, skip for this target.
- Do not import Node-only modules; use `nodejs_compat` sparingly and prefer web APIs.

## Docker

Best for: self-host, air-gapped, or full control.

`Dockerfile`:

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm i --frozen-lockfile
COPY . .
RUN pnpm -C packages/mcp build

FROM node:20-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /app/packages/mcp/dist ./dist
COPY --from=build --chown=app:app /app/packages/mcp/package.json ./
COPY --from=build --chown=app:app /app/node_modules ./node_modules
USER app
EXPOSE 8080
ENV MCP_TRANSPORT=http PORT=8080
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
CMD ["node", "dist/bin.js"]
```

`docker-compose.yml`: env file, port, restart policy. Document passing `MCP_TOKEN` via a secrets manager; do not hardcode it in compose.

Publish the image to GHCR (`ghcr.io/<org>/<tool>-mcp`) from `release.yml`.

## PaaS (Fly.io, Railway, Render)

Any Node-capable PaaS works with the Streamable HTTP transport.

- **Fly.io**: `fly launch` with Dockerfile; set secrets via `fly secrets set`.
- **Railway**: connect repo, set `MCP_TRANSPORT=http`, inject secrets as env vars.
- **Render**: Web Service, Docker runtime, health check path `/healthz`.

All targets: bind `0.0.0.0`, read `PORT` from env, emit logs to stdout/stderr, do not write to the local filesystem.

## Cross-cutting

- **TLS**: terminate at the PaaS or reverse proxy; do not ship TLS inside the app.
- **Rate limits**: at the app layer (per token), regardless of PaaS rate limits.
- **Session storage**: Cloudflare: Durable Objects; Docker/PaaS: in-memory + sticky sessions or Redis when scaling horizontally.
- **Config hot-reload**: not required; prefer redeploy.
- **Secrets rotation**: support at least 2 valid tokens in the rotation window (`MCP_TOKEN`, `MCP_TOKEN_PREV`).

## Local dev

```bash
pnpm -C packages/mcp dev                              # stdio, for Claude Code
pnpm -C packages/mcp dev -- --transport http --port 8080
```

Add an `mcp.json` example in `docs/mcp.md` to guide registration of the server in Claude Code, Cursor, and similar clients.
