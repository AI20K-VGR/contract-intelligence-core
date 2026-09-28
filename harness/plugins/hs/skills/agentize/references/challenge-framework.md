# Challenge Framework (`--ask` mode)

Used after scout + analyze, before scaffolding. Goal: pressure-test assumptions, surface constraints, and cut scope.

## Core questions (always ask)

1. **Why agentize this?** What is unlocked when an AI agent (not a human) calls these operations? If the answer is "it'd be cool" — stop.
2. **Who is the primary consumer?** AI agent, human via CLI, or both? This determines output shape, error messages, and verbosity.
3. **What is v1?** Name 3-5 capabilities shipping in week 1. Everything else is v2.
4. **Read vs. write split.** Which capabilities are read-only? Which mutate? Which are destructive? (Affects auth, confirmation, and MCP tool design.)
5. **Where do values come from today?** Env? Vault? Hardcoded? This pins the defaults in the resolution chain.
6. **Deploy target.** Local-only (stdio + CLI), remote (Cloudflare), self-host (Docker), or all? Cost and ops implications differ.
7. **Package name and scope.** `@org/tool`? Public npm scope? License?
8. **Maintenance.** Who owns it after release? Release cadence? Deprecation policy?

## Architectural challenges

| Question | Red flag | Green flag |
|---|---|---|
| Core extractable? | Business logic tangled with HTTP/CLI | Clear function boundaries |
| Side effects localized? | Scattered across modules | Isolated into clients |
| Async/long-running ops? | Calls 30+ seconds, no cancel | Quick calls or streaming progress |
| Auth complexity? | Multi-step OAuth dance per call | Static token or one-time login |
| Large outputs? | Megabyte responses typical | Pageable, filterable |
| Stateful workflows? | Requires client-side state machine | Each call self-contained |

## Cut-scope challenges

Ask for each proposed capability:
- Can an agent accomplish the user's goal without this capability?
- Does another capability already cover 80% of this one?
- Does this capability leak internal model details the agent does not need?
- Is this a debug/admin operation that should not be on the public surface?

## Design challenges

- Are we mirroring HTTP endpoints instead of designing workflows?
- Is the concise response actually concise (< 1 KB typical)?
- Do errors tell the agent what to do next, not just what broke?
- Are identifiers agent-friendly (names) or DB-friendly (UUIDs)?
- If a human reads the tool description, do they know when to use it?

## Decision matrix template

```markdown
| # | Decision            | Option A       | Option B       | Chosen | Why |
| - | ------------------- | -------------- | -------------- | ------ | --- |
| 1 | Transport           | stdio only     | all three      | all    | remote deploy planned |
| 2 | Credential storage  | env only       | keychain+env   | both   | dev UX + prod safety |
| 3 | CLI framework       | commander      | cac            | commander | wider adoption |
| 4 | Test runner         | vitest         | jest           | vitest | speed + TS native |
| 5 | Deploy target v1    | Cloudflare     | Docker         | both   | CI cost is low |
```

## Stop conditions

Abort and suggest an alternative if:
- Core cannot be extracted without significant refactoring that is outside the user's scope.
- No capability survives the "cut scope" pass.
- Legal/compliance blocks publishing (licensing of upstream deps, etc.).
- The credentials model requires interactive OAuth that cannot run inside MCP transports.
