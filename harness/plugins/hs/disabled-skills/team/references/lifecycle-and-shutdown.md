# Lifecycle and Shutdown

> Load this file when you need detail on the shutdown protocol, idle state, teardown, error recovery, and abort.

## Team lifecycle

```
TaskCreate x N → spawn named teammates (Agent name=…) → monitor → synthesize → shutdown all
```

The team is **implicit — one per session, session-derived name**. No `TeamCreate` (removed CC v2.1.178) — the first named `Agent(...)` spawn establishes the session team. No `TeamDelete` either — teammates end on `shutdown_request` or session end.

## Shutdown Protocol (teammate receiving shutdown_request)

1. Approve shutdown UNLESS currently in the middle of a critical operation.
2. If work is complete: `TaskUpdate` → `completed` BEFORE approving.
3. If work is unfinished: keep the task status as-is (or set `blocked` with a brief handoff note) BEFORE approving or rejecting.
4. Reject: explain briefly why.
5. Extract `requestId` from the JSON shutdown request → pass it into `shutdown_response`.

Shutdown may be slow — a teammate finishes its current request before exiting.

## Idle State — Normal behavior

- Idle after sending a message is NORMAL — not an error.
- Idle = waiting for input, not a lost connection.
- Sending a message to an idle teammate will wake it up.
- **Do not** treat an idle notification as a completion signal — check task status instead.

## Team teardown

There is no teardown call — the implicit team is session-scoped. After all teammates approve `shutdown_request`, the team is done; ending the session releases everything. Do NOT look for a `TeamDelete` tool (removed CC v2.1.178) — it is not in the tool surface.

## Display Modes

| Mode | When to use |
|---|---|
| `auto` (default) | split panes if inside tmux, otherwise in-process |
| `in-process` | single terminal — `Shift+Up/Down` to navigate, `Ctrl+T` for task list |
| `tmux/split` | one pane per teammate — requires tmux or iTerm2 |

Split panes are NOT supported in: VS Code terminal.

## Error Recovery

Check status first: `Shift+Up/Down` (in-process) or click pane (split). The recovery ladder itself (redirect → replace → reassign, with the claims.py reclaim + ownership-overlap detail) is canonical in `coordination-loop.md` § Step 5 — read it there.

## Abort Team

```
1. SendMessage(type: "shutdown_request") to each teammate
2. (no teardown call — the implicit team ends with the session)
```

No response: close the terminal or kill the session.
Orphaned tmux: `tmux ls` → `tmux kill-session -t <name>`.

## Known Limitations

| Limitation | Detail |
|---|---|
| One team per session | Implicit + session-scoped; you cannot create a second (server returns "one team per session") |
| No background subagents from in-process teammates | A teammate's own subagent runs foreground; `run_in_background`/`background:true` from a teammate errors (can't outlive the lead's process) |
| No resume | `/resume` and `/rewind` do not restore in-process teammates |
| Task status lag | A teammate may not have updated yet; check manually if in doubt |
| No nested teams | Only the lead manages the team; teammates cannot create sub-teams |
| VSCode unsupported | Agent Teams requires a CLI terminal |

## Token Budget Reference

| Template | Estimated tokens | Notes |
|---|---|---|
| research (3) | ~150K-300K | Read-only, moderate |
| cook (4) | ~400K-800K | Highest — code generation |
| review (3) | ~100K-200K | Read-only, moderate |
| debug (3) | ~200K-400K | Mixed read/execute |

Agent Teams consume more tokens than subagents — each teammate is a separate full Claude session with its own context window (not a model lock; model is per-teammate — see `agent-teams-controls-and-modes.md`). Use when parallel exploration and real discussion add genuine value. Single task → single subagent is more efficient.

## When to use Agent Teams vs Subagents

| Situation | Subagents | Agent Teams |
|---|---|---|
| Focused task (test, lint, single review) | Preferred | Overkill |
| Sequential pipeline (plan → code → test) | Preferred | No |
| 3+ independent parallel workstreams | Possible | Preferred |
| Adversarial hypothesis debugging | No | Preferred |
| Cross-layer work (FE + BE + test) | Possible | Preferred |
| Workers who need to discuss and challenge each other | No | Preferred |
| Tight token budget | Preferred | No |
