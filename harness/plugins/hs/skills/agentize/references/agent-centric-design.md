# Agent-Centric Design Rules

Rules for selecting and shaping capabilities when wrapping code as a CLI + MCP server for AI agents.

## Selecting capabilities

Keep a capability if **at least one** is true:
- An agent uses it to complete a user task.
- It is a workflow step that is hard or error-prone to express in prose.
- It is idempotent or easy to make idempotent.

Cut a capability if **all** are true:
- It is a thin passthrough of another capability.
- It is purely internal plumbing.
- Its output is too large to be useful in context.

## Consolidate workflows

Bad: `list_items`, `get_item`, `check_quota`, `create_item` (4 tools; the agent must orchestrate).

Good: `create_item(name, …)` — checks quota internally, deduplicates by name, returns the created record.

**Rule**: if the README says "first call X, then Y, then Z" that is 1 tool, not 3.

## Optimize for context

- Default response is **concise**: ID + name + status, not the full payload.
- Offer `format: "detailed"` / `--detailed` as opt-in.
- Paginate; keep the default page size small (10-25).
- Prefer names over IDs: `{ "project": "acme-web" }` > `{ "project_id": "prj_7f3c2…" }`.
- Truncate long fields with a `…` marker + length hint.

## Actionable errors

Every error must answer: what failed, why, and what to try next.

Bad:
```
Error: 400 Bad Request
```

Good:
```
Error: rate_limited
Message: Exceeded 60 requests/minute. Retry after 12s, or pass --concurrency 2.
```

Always include an `error_code` machine field for agent branching.

## Safe vs. mutating

- Read-only tools: no confirmation needed, safe to call speculatively.
- Mutating tools: describe the mutation in `description`; prefer `dry_run: true`; return a diff/preview when dry-run is set.
- Destructive tools (`delete_*`): require `confirm: true` or a token from a preceding `plan_*` tool.

## Naming

- Tools: `verb_noun`, snake_case: `list_projects`, `create_project`, `search_logs`.
- CLI commands: `noun verb` or `verb`, kebab-case: `project list`, `project create`.
- Flags: long-form kebab-case, short-form single-letter for universal flags (`-v`, `-h`).

## Idempotency

- Creates accept a client-supplied idempotency key.
- Updates are PATCH-shaped (send only changed fields).
- Deletes succeed when the target is already absent.

## Output shape

JSON output (when `--json` or MCP structured content):

```json
{
  "ok": true,
  "data": { "…": "…" },
  "warnings": [],
  "next_actions": ["optional hints for the agent"]
}
```

Errors:

```json
{
  "ok": false,
  "error": { "code": "rate_limited", "message": "…", "retry_after_s": 12 }
}
```
