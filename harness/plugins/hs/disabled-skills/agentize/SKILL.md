---
name: hs:agentize
injectable: true
description: Convert a codebase, feature, or module into an AI-agent-friendly npm CLI and/or MCP server. Use to expose existing capabilities as a reusable CLI tool or MCP server.
argument-hint: "[feature-or-module] [--both|--mcp|--cli] [--auto|--ask] [--ultra [N] | --debate]"
allowed-tools: [Bash, Read, Write, Edit, MultiEdit, Grep, Glob, Task, WebFetch]
metadata:
  compliance-tier: workflow
---

# hs:agentize — package code as an agent-friendly CLI + MCP server

Convert existing code into: **CLI** (npm, credential-aware, scriptable) + **MCP server** (stdio/SSE/Streamable HTTP, Cloudflare/Docker) + **companion skill** (`harness/plugins/hs/skills/<tool>/`).

Not for: building a server from scratch (hs:mcp-builder), scaffolding a plain npm package, or publishing before there is an agent-use story.

## Modes

| Output | Meaning |
|---|---|
| `--both` *(default)* | monorepo: shared `core/`, `cli/` package, `mcp/` package |
| `--mcp` | MCP server only |
| `--cli` | CLI only |

| Interaction | Meaning |
|---|---|
| `--auto` *(default)* | analyze, decide, and implement without asking |
| `--ask` | after analysis, interview the user before scaffolding |

No argument: `AskUserQuestion` — which module/feature, which mode, deploy target.

## Workflow

```
[0. Track] → [1. Scout] → [2. Analyze] → [3. Decide] → [4. Scaffold] → [5. Wrap] → [6. Harden] → [7. Package]
```

### 0. Track (required)

Call `hs:project-management` before touching code. Create a plan dir under `plans/`, register the Scout-to-Package checklist, and write mode flags + target into `plan.md`. Do not proceed without a plan dir.

### 1. Scout (required)

Call `hs:scout`. Collect: entry points + public API + existing CLI; 5-15 operations worth exposing; input/output shapes, side effects; config + credential surface; language/runtime + dependencies + existing tests. Narrow scout scope -> better tools. Do not invent behavior you have not read.

### 2. Analyze

Build an **Agentization Map** (markdown table):

| Capability | Entry point | Inputs | Outputs | Side effects | Auth? | Agent value | CLI value |
|---|---|---|---|---|---|---|---|

Design rules: workflow over endpoint-mirror, concise response, actionable errors, human-readable IDs, idempotency + dry-run. Details: `references/agent-centric-design.md`. Cut a capability when both Agent value and CLI value are Low.

### 3. Decide

Choose output mode and the list of tools/commands.

`--auto`: record each decision in the plan with a one-line justification.

`--ask`: load `references/challenge-framework.md`, ask at least 7 questions (v1 capabilities, read/write split, credential source, deploy target, package name, license, maintenance owner). Challenge vague answers.

Output: `plans/reports/agentize-decisions-<slug>.md` with mode, capability list, tool names, transports, deploy targets, package metadata.

### 4. Scaffold

Default `--both` layout (pnpm/npm workspaces): `packages/core/`, `packages/cli/`, `packages/mcp/`, `docs/`, `.github/workflows/`. Full details + `package.json` shapes: `references/monorepo-layout.md`.

`--cli` or `--mcp` alone: single-package, still keep a `src/core/` folder. TypeScript by default for JS/TS targets; non-JS targets use their idiomatic toolchain.

### 5. Wrap

Extract `core/` first — pure functions, no CLI/MCP concerns imported.

**CLI** (`packages/cli/`): commander or cac; `--help`, `--version`, `--json`; consistent exit codes (0 ok / 1 user / 2 auth / 3 network / 4 runtime); `NO_COLOR` / `--quiet` / `--verbose`; never print secrets.

Credential resolution order (details: `references/auth-resolution-chain.md`):
1. Explicit flag (`--api-key`) 2. Env var 3. dotenv files 4. User config JSON
5. Project config JSON 6. OS keychain (`keytar`)

**MCP** (`packages/mcp/`): official MCP SDK; 3 transports: stdio (default local), SSE (legacy), Streamable HTTP (preferred remote). Tool name: `verb_noun` snake_case; each tool has a rich description + JSON Schema. Details: `references/mcp-transports.md`.

### 6. Harden

Run in order, do not skip:
1. **Tests** (`hs:test`): unit `core/` (happy + 2 error paths); CLI integration; MCP round-trip + auth reject; coverage ≥80% `core/`.
2. **CI** (`.github/workflows/`): `ci.yml` test+lint+typecheck; `release.yml` npm publish + Docker push + Cloudflare deploy on tag.
3. **Docs** (`hs:docs`): README, `docs/cli.md`, `docs/mcp.md`, `docs/architecture.md`.
4. **Companion skill** (`hs:skill-creator`): create skill at
   `harness/plugins/hs/skills/<tool>/SKILL.md` — trigger phrases, 3-5 workflows, concrete CLI + MCP examples. Do not create it manually.
   - **Discoverability** (generated tool advertises its companion skill; resolve skill name once from tool slug, reuse in CLI help, MCP metadata, README, docs):
     - CLI `--help` prints an `Agent Skill: <skill-name> — activate/read before non-trivial use.` hint.
     - MCP server exposes a `skill://<skill-name>` resource + `use-<tool>-skill` prompt when supported; else fold hint into tool descriptions + `docs/mcp.md`. Server description names `Companion Agent Skill: <skill-name>`.
     - README carries an agent-facing note: `For AI agents: companion Agent Skill <skill-name>; activate/read before non-trivial CLI/MCP use.`
     - Add a test/fixture proving the generated CLI `--help` and MCP metadata include the companion-skill hint.
5. **Security pass**: dep audit, secret scan, redaction tests, MCP auth tests, Docker non-root check. Deploy recipes: `references/deployment-guide.md`.

### 7. Package

Deliver: monorepo ready-to-publish, `docs/` complete, CI green, companion skill at `harness/plugins/hs/skills/<tool>/`, decision record at `plans/reports/agentize-decisions-<slug>.md`. Write a handoff summary with absolute paths. Next step: `/hs:cook <plan-path>` to execute remaining implementation.

## Output language

Render reports per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/output-rendering.md`: resolve `language` / `audience` / `humanize` live via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/output_config.py --resolved` (never hand-read the tracked file); the rule holds the register behavior and the evidence-invariant fence.

## Boundaries

- Do NOT build a server from scratch: use `hs:mcp-builder`.
- Do NOT create agent primitives directly: use `hs:harness-creator` (agent type).
- Do NOT create new harness skills directly: use `hs:skill-creator`.
- Step 0 is required: no plan, no scaffold.
- `--ultra [N]`/`--debate`: call `hs:workflow-orchestrate --ultra [N]|--debate --run-id <slug>` to size + drive N independent productization designs (CLI/MCP shape) over the SAME feature (no shared context); `hs:escalation-consultant` synthesizes ONE design, and only that design gets scaffolded below. Approval gate is `hs:workflow-orchestrate`'s own.

## Quick reference

| Content | Drawer |
|---|---|
| Tool/command design rules, agent-centric principles | `references/agent-centric-design.md` |
| Monorepo tree + package.json shapes | `references/monorepo-layout.md` |
| stdio / SSE / Streamable HTTP wiring | `references/mcp-transports.md` |
| Resolution chain, keychain, redaction | `references/auth-resolution-chain.md` |
| Cloudflare Workers, Docker, PaaS recipes | `references/deployment-guide.md` |
| `--ask` interview prompts, decision matrix | `references/challenge-framework.md` |
| Failure mode → action recovery table | `references/error-recovery.md` |
