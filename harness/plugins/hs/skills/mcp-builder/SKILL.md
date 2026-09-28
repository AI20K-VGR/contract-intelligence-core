---
name: hs:mcp-builder
injectable: true
description: Build MCP servers for LLM external-service integration — FastMCP (Python), MCP SDK (Node/TypeScript), tool design, API integration, resource providers. Use to create or extend an MCP server.
argument-hint: "(no arguments)"
allowed-tools: [Bash, Read, Write, Edit, MultiEdit, Grep, Glob, WebFetch]
metadata:
  compliance-tier: knowledge
---

# hs:mcp-builder — build high-quality MCP servers

Guide to design/build MCP (Model Context Protocol) servers — the tool surface letting LLMs interact with external services. Quality = how well an agent using the tools completes real tasks.

## When to use

When the user says "build MCP server", "create MCP tool", "integrate [service] into Claude", or needs to expose an API/service as a tool for an LLM.

If information is missing: `AskUserQuestion` to ask for language (Python/TypeScript), the service to integrate, and transport (stdio/http/sse).

## 4 fixed phases

### Phase 1 — Research & planning

1. **Fetch MCP spec**: `https://modelcontextprotocol.io/llms-full.txt`
2. **Load language guide**: `references/python-mcp-server.md` or `references/node-mcp-server.md` based on the chosen language.
3. **Load best practices**: `references/mcp-best-practices.md` — read before designing tools.
4. **Read the full API documentation** for the service being integrated (auth, rate limits, pagination, error codes, data model).
5. **Create a plan**: select the highest-value tools (workflow tools, not pure endpoint wrappers), design shared utilities, define input/output schemas.

### Phase 2 — Implementation

Implement in order:

1. **Shared utilities first**: API client, error handler, response formatter, pagination helper.
2. **Tools one at a time**: input schema (Pydantic/Zod) → full docstring → logic → annotations.
3. **Required tool annotations**: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`.
4. **CHARACTER_LIMIT = 25000** — check + truncate gracefully with filter guidance.

Essential tool design principles (naming, workflow-first, context-efficient output, actionable errors, annotations): see `references/mcp-best-practices.md`.

### Phase 3 — Review & test

- Check DRY, type coverage, error handling, documentation.
- **Do NOT run directly** `python server.py` / `node index.js` — MCP server blocks stdio. Use tmux or `timeout 5s python server.py`.
- Python: `python -m py_compile server.py` to verify syntax.
- TypeScript: `npm run build` — confirm `dist/index.js` exists.
- Load the checklist from the corresponding language guide.
- After review: may route to `hs:code-review` for an independent pass.

### Phase 4 — Verification

Create 10 evaluation questions: read-only, independent, requiring multiple tool calls, with stable and verifiable answers. XML format:

```xml
<evaluation>
  <qa_pair>
    <question>...</question>
    <answer>single verifiable value</answer>
  </qa_pair>
</evaluation>
```

These questions aren't just a checklist — they drive an **automated evaluation run** exercising the built server end-to-end (a model answers each question using only the server's tools; the run scores whether it reached the verifiable answer via real tool calls). That scored run, not a manual read-through, is the finished server's verification gate.

MUST: `ANTHROPIC_API_KEY` must be set in the environment before running `scripts/evaluation.py` — it calls the Anthropic SDK with no explicit key handling, relying on implicit env-var pickup.

Run it with the bundled harness (its runtime deps `anthropic`+`mcp` are in `scripts/requirements.txt`):

```bash
python3 scripts/evaluation.py -t stdio -c python -a my_server.py eval.xml
python3 scripts/evaluation.py -t http -u https://example.com/mcp -m claude-3-7-sonnet-20250219 eval.xml
```

`scripts/connections.py` handles the stdio/sse/http transport; `scripts/example_evaluation.xml` is a worked template. Full method (question design, scoring, worked good/poor examples, runner CLI): `references/evaluation.md` → `references/evaluation-examples.md` → `references/evaluation-running.md`.

## Boundaries

- Do not choose a service unilaterally if it is unclear — ask the user.
- Do not write code until Phase 1 has fetched the MCP spec and API documentation.
- Do not reference any script or harness gate outside this skill.
- On completion: server file path + list of implemented tools + open questions.

## Related skills

- `hs:agentize`: wraps an existing codebase into an MCP server / CLI — reciprocal scope.
