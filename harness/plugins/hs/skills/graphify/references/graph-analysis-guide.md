# Graph analysis guide — architecture, tagging, and MCP (on-demand)

Technical details of hs:graphify. Read for deep pipeline understanding or MCP server setup.

## Three-pass architecture

### Pass 1 — AST extraction (local, no API calls)

tree-sitter parses code across 20 languages deterministically. No file content leaves the machine during this pass.

**Supported languages:**
Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, C#, Kotlin, Scala, PHP, Swift, Lua, Zig, PowerShell, Elixir, Objective-C, Julia

AST extracts directly:
- Import/dependency declarations
- Function and method call chains
- Class inheritance and interface implementation
- Module boundary relationships

### Pass 2 — Audio/video transcription (local)

Whisper runs on-device for audio and video files. No API key required. Transcripts are indexed into the graph as text nodes.

### Pass 3 — Semantic extraction (calls model provider)

LLM subagents process in parallel: docs, papers, images. This is the only pass that sends data externally — to the configured model provider (Claude, OpenAI, etc.).

Result quality depends on the model. For sensitive documents, consider a local model or skipping pass 3 (build from code + audio only).

## Confidence tagging

Every relationship in the graph has a provenance tag:

| Tag | Meaning |
|-----|---------|
| `EXTRACTED` | Directly from AST (imports, function calls, class inheritance) — high confidence |
| `INFERRED` | LLM-derived with a confidence score — review before trusting |
| `AMBIGUOUS` | Uncertain — requires human verification before building further |

**Usage rule:** Build plans only on `EXTRACTED` relationships. For `INFERRED`, check the confidence score; for `AMBIGUOUS`, verify manually or tag `[ASSUMED]` in the report.

## Incremental cache

The cache at `graphify-out/cache/` stores the SHA256 of each file. Rebuild only reprocesses changed files — significant savings on large codebases.

```bash
# Force full rebuild (ignore cache)
graphify . --no-cache

# View cache stats
graphify . --stats
```

## MCP server — query tools

After building the graph, expose it via MCP for direct querying:

```bash
python -m graphify.serve graphify-out/graph.json
```

### Tool reference

| Tool | Parameters | Use when |
|------|------------|---------|
| `query_graph` | `query: str` | Find concepts and relationships by keyword |
| `get_node` | `node_id: str` | View details of a specific node |
| `get_neighbors` | `node_id: str, depth: int` | Find related concepts (N hops) |
| `shortest_path` | `from_id: str, to_id: str` | Find the connection path between 2 concepts |

### Example query workflow

```
# 1. Find authentication-related concepts
query_graph("authentication")

# 2. View auth middleware node details
get_node("auth_middleware")

# 3. Find all code that depends on auth_middleware (2 hops)
get_neighbors("auth_middleware", depth=2)

# 4. Find path from user controller to database layer
shortest_path("UserController", "DatabaseAdapter")
```

## Installation variants

| Extra | Command | Use when |
|-------|---------|---------|
| MCP server | `pip install 'graphifyy[mcp]'` | Need to query directly from Claude |
| PDF support | `pip install 'graphifyy[pdf]'` | PDF documents |
| Video | `pip install 'graphifyy[video]'` | Media files |
| Neo4j | `pip install 'graphifyy[neo4j]'` | External graph database (production) |
| Leiden | `pip install 'graphifyy[leiden]'` | Advanced community detection |
| Full | `pip install 'graphifyy[all]'` | All extras above |

## God nodes — finding architectural bottlenecks

`GRAPH_REPORT.md` lists god nodes: the most-connected concepts in the graph. A god node is a potential architectural bottleneck or an important shared abstraction.

Read GRAPH_REPORT.md before opening any file — it tells you where to start understanding and which connections are most surprising.

## Integration with hs:* workflow

```
hs:graphify .          -> GRAPH_REPORT.md (architecture overview)
hs:scout "auth"        -> specific files in the auth module
hs:repomix --include   -> full context for identified files
hs:understand          -> synthesized codebase map
hs:plan                -> plan with full context
```

When a publish-grade diagram is needed from graph data, hs:tech-graph accepts JSON/relationship data and renders SVG/PNG with a proper layout.
