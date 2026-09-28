# Agent Teams -- Controls, Display Modes & Task Management

> **Source:** https://code.claude.com/docs/en/agent-teams
> **Version captured:** Claude Code v2.1.80 (March 2026)

## Display Modes

- **In-process** (default fallback): all teammates in one terminal. `Shift+Up/Down` to navigate. Works in any terminal.
- **Split panes**: each teammate gets own pane. Requires tmux or iTerm2.

Default is `"auto"` -- uses split panes if already inside a tmux session, otherwise in-process. The `"tmux"` setting enables split-pane mode and auto-detects tmux vs iTerm2.

```json
{ "teammateMode": "in-process" }
```

Per-session override: `claude --teammate-mode in-process`

Split panes NOT supported in: VS Code terminal, Windows Terminal, Ghostty.

**tmux setup:** install via system package manager.
**iTerm2 setup:** install `it2` CLI, enable Python API in iTerm2 > Settings > General > Magic.

## Model Selection (per-teammate)

Each teammate's model is chosen at spawn — **mixed-model teams ARE supported** (e.g. Sonnet for devs, Opus for a reviewer). Say it in the spawn prompt: "Spawn 4 teammates... Use Sonnet for each."

- Teammates do NOT inherit the lead's `/model` by default.
- When a spawn omits a model, the fallback is the **Default teammate model** in `/config` (pick "Default (leader's model)" to follow the lead's current model).
- A teammate's model + fast mode are **fixed at spawn**: `/model` and `/fast` typed while viewing a teammate only change the lead. `/effort` DOES apply to the viewed teammate's later turns — teammates follow the lead's effort level (split-pane: from v2.1.186).

> The old "all teammates must run Opus" hard constraint was **removed in CC v2.1.178**.
> Source: https://code.claude.com/docs/en/agent-teams (Specify teammates and models).

## Plan Approval

Require teammates to plan before implementing:

```
Spawn an architect teammate to refactor the auth module.
Require plan approval before they make any changes.
```

**Flow:**
1. Teammate works in read-only plan mode
2. Teammate finishes planning -> sends `plan_approval_request` to lead
3. Lead reviews -> approves via `SendMessage(type: "plan_approval_response", approve: true)`
4. If rejected: teammate stays in plan mode, revises based on feedback, resubmits
5. Once approved: teammate exits plan mode, begins implementation

**Influence criteria:** "only approve plans that include test coverage" or "reject plans that modify the database schema"

## Delegate Mode

Restricts lead to coordination-only tools: spawning, messaging, shutting down teammates, and managing tasks. No code editing.

Useful when lead should focus entirely on orchestration -- breaking down work, assigning tasks, synthesizing results.

**Enable:** Press `Shift+Tab` after team creation to cycle into delegate mode.

## Direct Teammate Interaction

- **In-process**: `Shift+Up/Down` select teammate, type to message. `Enter` view session. `Escape` interrupt current turn. `Ctrl+T` toggle task list.
- **Split panes**: click into pane to interact directly. Each teammate has full terminal view.

## Task Assignment & Claiming

Three states: **pending** -> **in_progress** -> **completed**. Tasks can have dependencies -- blocked until dependencies resolve.

- **Lead assigns**: tell lead which task -> which teammate
- **Self-claim**: after finishing, teammate picks next unassigned, unblocked task automatically
- **Auto-unblock**: completing a blocking task automatically unblocks dependents

File locking prevents race conditions on simultaneous claiming.

## Worktree Isolation for Implementation

When spawning developer teammates, use `isolation: "worktree"` on the Agent tool:

```
Agent(
  subagent_type: "hs:developer",
  model: "opus",
  isolation: "worktree",
  run_in_background: true,
  prompt: "Implement auth module..."
)
```

Each dev gets own worktree + branch. No file conflicts during parallel work. Lead merges branches after all devs complete.

**When to use:** Always for cook/implementation templates. Not needed for research/review (read-only).

## Background Spawning

Use `run_in_background: true` on the Agent tool to spawn teammates non-blocking:

- Lead continues orchestration while teammates work
- Teammates message the lead when they complete or block
- Use TaskList after 60s or when a teammate messages completion
- Do not rely on custom team hook handlers; they are not shipped by default

## Shutdown

```
Ask the researcher teammate to shut down
```

Teammate can approve (exit) or reject with explanation. Teammates finish current request/tool call before shutting down -- can be slow.

## Cleanup

There is no teardown call. The team is implicit and session-scoped — after all teammates approve `shutdown_request`, ending the session releases the shared team resources (`~/.claude/teams/` and `~/.claude/tasks/` entries). `TeamDelete` was removed in CC v2.1.178 — do not look for it.

## Monitoring

1. Lead creates tasks and spawns teammates (with `run_in_background: true`)
2. Teammates mark tasks with `TaskUpdate` and send concise completion messages
3. Lead checks TaskList after 60s or after each completion message
4. Lead acts on verified task state (spawn tester, shut down, reassign)
5. If a task appears stale, message the owner before changing status

Claude Code exposes platform Agent Teams events; the harness ships no custom handlers for them by default. Keep orchestration explicit until a live harness validates any hook-based flow.
