---
name: hs:graphify
injectable: true
description: Build a queryable knowledge graph from code, docs, and media — architecture analysis, cross-file relationship discovery, token-efficient navigation. Use before hs:plan on unfamiliar codebases.
argument-hint: "[path] [--watch]"
allowed-tools: [Bash, Read, Write]
metadata:
  compliance-tier: knowledge
---

# hs:graphify — knowledge graph builder

Turns any dir of code/docs/media into a queryable knowledge graph. Uses tree-sitter AST for code (20 languages), Whisper for audio/video, and LLM subagents for documents.

**Efficiency:** far fewer tokens than a raw file dump — replaces manual grep across large codebases.

## When to use

- Understand the architecture of an unfamiliar codebase before planning
- Find "god nodes" (most-connected concepts) in a large project
- Discover cross-file relationships and dependency chains
- Navigate by structure instead of grepping individual files

## Installation

```bash
# Basic install
pip install graphifyy          # PyPI: graphifyy (two y's)

# With MCP server
pip install 'graphifyy[mcp]'

# Full (MCP + PDF + video + Leiden community detection)
pip install 'graphifyy[all]'
```

Requires: Python 3.10+

## Quick start

```bash
# Build graph from current directory
graphify .

# Build from a specific path
graphify /path/to/project

# Watch mode — auto-rebuild when files change
graphify . --watch
```

## Output

| File | Purpose |
|------|---------|
| `graphify-out/graph.html` | Interactive visualization with search + community filter |
| `graphify-out/GRAPH_REPORT.md` | God nodes, unexpected connections, suggested questions |
| `graphify-out/graph.json` | Persistent graph for multi-session querying |
| `graphify-out/cache/` | Incremental cache by SHA256 |

**MUST**: build a plan (`hs:plan`) only on EXTRACTED edges; treat INFERRED edges as confidence-scored and AMBIGUOUS edges as unverified — check the confidence score, verify manually, or tag `[ASSUMED]` in the report before feeding either into a plan.

Architecture details, confidence tagging, and MCP server -> `references/graph-analysis-guide.md`.

## Workflow integration

```bash
# Before planning: read GRAPH_REPORT.md -> understand architecture -> better plan
graphify .
# Combined: graph for overall structure, hs:scout for specific files
```

When SVG/diagram layout must be publish-grade, use hs:tech-graph instead of graph.html.

## MCP server mode

```bash
python -m graphify.serve graphify-out/graph.json
```

Add to MCP config:
```json
{
  "mcpServers": {
    "graphify": {
      "command": "python",
      "args": ["-m", "graphify.serve", "graphify-out/graph.json"]
    }
  }
}
```

MCP tools: `query_graph`, `get_node`, `get_neighbors`, `shortest_path`.

## Privacy

- **Code:** Processed locally via tree-sitter AST. No file content leaves the machine.
- **Audio/Video:** Transcribed locally via Whisper.
- **Docs/Images:** Sent to the configured model provider for semantic extraction.

## Limitations

- First build on a large codebase may be slow (AST parsing + LLM calls)
- Semantic extraction quality depends on the model
- Neo4j integration: `pip install 'graphifyy[neo4j]'`

## Position in workflow

**Before:** hs:plan (understand architecture before planning)
**Alongside:** hs:scout (fast file lookup), hs:repomix (full context dump), hs:understand (overall codebase map)

## Boundaries

- For static publish-grade diagrams (SVG/PNG with layout rules), use `hs:tech-graph`.
- For inline markdown diagrams, use `hs:mermaidjs`.
- For branded stencils (AWS/Azure/GCP/Cisco/K8s/UML/ER) or draw.io-native editing, use `hs:drawio`.
