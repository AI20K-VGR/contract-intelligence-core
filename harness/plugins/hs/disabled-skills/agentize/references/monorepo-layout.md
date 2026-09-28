# Monorepo Layout

Standard layout for `--both` mode (Node/TypeScript). Adapt for other ecosystems.

## Tree

```
.
├── packages/
│   ├── core/
│   │   ├── src/
│   │   │   ├── capabilities/       # one file per capability
│   │   │   ├── config/             # config schema + loader
│   │   │   ├── errors.ts           # typed error classes
│   │   │   └── index.ts            # public exports
│   │   ├── test/
│   │   ├── package.json            # private: true (not published)
│   │   └── tsconfig.json
│   ├── cli/
│   │   ├── src/
│   │   │   ├── commands/           # one file per command
│   │   │   ├── credentials.ts      # resolution chain
│   │   │   ├── formatter.ts        # json + text renderers
│   │   │   └── bin.ts              # #!/usr/bin/env node entry
│   │   ├── test/
│   │   ├── package.json            # bin, files, engines, publishConfig
│   │   └── tsconfig.json
│   └── mcp/
│       ├── src/
│       │   ├── tools/              # one file per tool
│       │   ├── transports/
│       │   │   ├── stdio.ts
│       │   │   ├── sse.ts
│       │   │   └── streamable-http.ts
│       │   ├── auth.ts
│       │   └── server.ts           # transport-agnostic server factory
│       ├── test/
│       ├── package.json
│       ├── wrangler.toml           # Cloudflare Workers
│       ├── Dockerfile
│       └── tsconfig.json
├── harness/plugins/hs/skills/<tool-name>/  # companion skill (hs:skill-creator)
├── docs/
│   ├── cli.md
│   ├── mcp.md
│   ├── architecture.md
│   └── contributing.md
├── scripts/
├── .github/workflows/
│   ├── ci.yml
│   └── release.yml
├── package.json                    # workspaces
├── pnpm-workspace.yaml
├── tsconfig.base.json
├── .gitignore
├── LICENSE
└── README.md
```

## Root `package.json`

```json
{
  "name": "<tool-name>-monorepo",
  "private": true,
  "workspaces": ["packages/*"],
  "scripts": {
    "build": "pnpm -r build",
    "test": "pnpm -r test",
    "lint": "pnpm -r lint",
    "typecheck": "pnpm -r typecheck",
    "release": "changeset publish"
  },
  "packageManager": "pnpm@9"
}
```

## `packages/core/package.json`

```json
{
  "name": "@<scope>/<tool-name>-core",
  "private": true,
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc -p .",
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  }
}
```

## `packages/cli/package.json`

```json
{
  "name": "<tool-name>",
  "version": "0.1.0",
  "description": "CLI for <tool-name>",
  "bin": { "<tool-name>": "dist/bin.js" },
  "files": ["dist", "README.md", "LICENSE"],
  "engines": { "node": ">=20" },
  "publishConfig": { "access": "public", "provenance": true },
  "dependencies": {
    "@<scope>/<tool-name>-core": "workspace:*",
    "commander": "^12",
    "dotenv": "^16",
    "keytar": "^7"
  },
  "scripts": {
    "build": "tsc -p . && chmod +x dist/bin.js",
    "prepublishOnly": "pnpm build && pnpm test"
  }
}
```

## `packages/mcp/package.json`

```json
{
  "name": "<tool-name>-mcp",
  "version": "0.1.0",
  "bin": { "<tool-name>-mcp": "dist/bin.js" },
  "files": ["dist", "README.md", "LICENSE"],
  "engines": { "node": ">=20" },
  "publishConfig": { "access": "public", "provenance": true },
  "dependencies": {
    "@<scope>/<tool-name>-core": "workspace:*",
    "@modelcontextprotocol/sdk": "^1",
    "hono": "^4"
  }
}
```

## Core/adapter boundary

`core/` rules:
- No `process.argv`, no `console.log` as control flow, no HTTP server code.
- Receive config via explicit params; return plain data or throw typed errors.
- Pure functions where possible; side-effects isolated into injected clients.

`cli/` and `mcp/` rules:
- Import only from `core/` (plus formatting/transport deps).
- Translate argv / MCP args to core params.
- Translate core results/errors to CLI output / MCP response.
- No business logic.

If business logic is added to an adapter, it belongs in `core/`.

## Single-package fallback (`--cli` or `--mcp` alone)

```
.
├── src/
│   ├── core/           # boundary preserved, not yet a separate package
│   ├── cli/  (or mcp/)
│   └── index.ts
├── package.json
└── tsconfig.json
```

Keep `src/core/` even with only one adapter: adding the other surface later is a file move, not a rewrite.
