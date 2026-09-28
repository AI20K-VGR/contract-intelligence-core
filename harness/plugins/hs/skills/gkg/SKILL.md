---
name: hs:gkg
injectable: true
description: Semantic code analysis with GitLab Knowledge Graph. Use for go-to-definition, find-usages, impact analysis, architecture visualization. Supports Ruby, Java, Kotlin, Python, TypeScript/JavaScript.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep]
argument-hint: "[symbol or query]"
metadata:
  compliance-tier: knowledge
---

# GitLab Knowledge Graph (GKG)

Semantic code analysis engine using AST parsing and KuzuDB graph database. Enables IDE-like code navigation for AI assistants.

**Status**: Public beta | **Requires**: Git repository | **Storage**: `~/.gkg/`

## When to Use

- Find all usages of a function/class across codebase
- Go-to-definition for symbols
- Impact analysis before refactoring
- Generate architecture diagrams
- RAG-enhanced code understanding

**Use repomix instead** for: quick context dumps, any-language support, remote repos, token counting.

## Quick Start

```bash
# Check installation
gkg --version

# Index current repo
gkg index

# Start server (for API/MCP)
gkg server start

# Stop before re-indexing
gkg server stop
```

Install once per machine: `references/cli-commands.md` (Installation section).

## Core Workflows

### Index and Query
```bash
gkg index /path/to/project --stats
gkg server start
# Query via HTTP API at http://localhost:27495
```

### Find Symbol Usages
1. Index project: `gkg index`
2. Start server: `gkg server start`
3. Use MCP tool `get_references` (no HTTP equivalent; `/api/graph/search` is definitions-by-pattern, not usages)

### Impact Analysis
1. Index affected repos
2. Query `get_references` for changed symbols
3. Review all call sites before refactoring

## Language Support

| Language | Cross-file Refs |
|----------|-----------------|
| Ruby | ✅ Full |
| Java | ✅ Full |
| Kotlin | ✅ Full |
| Python | 🚧 In progress |
| TypeScript | 🚧 In progress |
| JavaScript | 🚧 In progress |

## References

- [CLI Commands](./references/cli-commands.md) - `gkg index`, `gkg server`, `gkg remove`, `gkg clean`
- [MCP Tools](./references/mcp-tools.md) - 7 tools for AI integration
- [HTTP API](./references/http-api.md) - REST endpoints for querying
- [Language Details](./references/language-support.md) - Supported features per language

## Key Constraints

- Must stop server before re-indexing
- Requires initialized Git repository
- Languages not connected across repos (yet)
- TS/JS/Python cross-file refs incomplete
