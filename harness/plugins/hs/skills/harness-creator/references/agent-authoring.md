# Agent authoring — role-prompt convention

## When to create an agent

An agent (`harness/plugins/hs/agents/*.md`) is a **tuned role-prompt** for a specific role in the harness workflow. Create an agent when:

- A specialized role is needed that will be spawned by an orchestrator or skill (planner, reviewer, debugger, ...).
- The role has its own behavioral checklist that does not fit in SKILL.md.
- Concerns should be separated: skill = workflow directive, agent = persona/behavior.

Do not create an agent when a script or rule is sufficient — an agent is prose for an LLM, not runtime code.

## Standard format

```markdown
---
name: <slug>
tools: Glob, Grep, Read, Bash, ...   # explicit tool list
description: >-
  <third-person description, with trigger phrase, <=200 chars>
  Examples:
  - <example>
      Context: ...
      user: "..."
      assistant: "..."
      <commentary>...</commentary>
    </example>
---

You are a **<Role>** ...

## Behavioral Checklist
- [ ] <check 1>
- [ ] <check 2>

## Core Principles
...

## Your Process
1. ...
2. ...

## Team Mode (when spawned as a teammate)
...
```

## Rules for writing a role-prompt

- **English is fine** for the role-prompt body (an English role-prompt for an agent is acceptable — the agent system prompt is not a skill directive).
- **Explicit tool list**: only declare tools the agent actually needs — do not add extras.
- **Behavioral checklist**: before ending the session, the agent verifies each item. Prevents missing steps.
- **Team Mode section is required** if the agent may be spawned by `hs:team`: TaskList -> claim -> TaskGet -> work -> TaskUpdate(completed) -> SendMessage.
- **No runtime coupling**: the agent must not import or reference harness runtime code — only cite tool/skill/gate names in prose.

## Commonly used tools

| Tool group | When to declare |
|---|---|
| `Glob, Grep, Read` | Agent needs to read the codebase |
| `Bash` | Agent needs to run commands |
| `Write, Edit` | Agent needs to edit or create files |
| `TaskCreate, TaskGet, TaskUpdate, TaskList` | Agent participates in team workflow |
| `SendMessage` | Agent needs to communicate with peers in a team |
| `WebFetch, WebSearch` | Agent needs to research outside the repo |

## Real examples

```
harness/plugins/hs/agents/brainstormer.md
harness/plugins/hs/agents/planner.md
harness/plugins/hs/agents/code-reviewer.md
harness/plugins/hs/agents/debugger.md
```

## Boundaries: agent vs skill

| | Agent | Skill |
|---|---|---|
| File | `agents/<name>.md` | `skills/<name>/SKILL.md` |
| Invoked by | orchestrator spawn / `hs:team` | User or skill chain |
| Content | Role-prompt, behavioral checklist | Workflow directive, backing-or-cut |
| Language | English OK | English, imperative |
| Catalog | Not in `load_catalog()` owned | Must have `name: hs:*` -> owned |
| Runtime code | None | Backing must be a real gate/script/rule |
