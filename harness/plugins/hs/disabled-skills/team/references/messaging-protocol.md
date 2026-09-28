# Messaging Protocol and Task Claiming

> Load this file when you need detail on SendMessage types, task claiming, and plan approval flow within an Agent Team.

## SendMessage Types

| Type | When to use | Required parameters |
|---|---|---|
| `message` | DM to one specific teammate | `recipient` (name, not agent ID) |
| `broadcast` | Blocking issue affecting the whole team | — |
| `shutdown_request` | Request a teammate to exit gracefully | — |
| `shutdown_response` | Teammate approves or rejects shutdown | `request_id` (extracted from JSON request) |
| `plan_approval_response` | Lead approves or rejects a teammate's plan | `request_id` |

- `broadcast` is used very sparingly — only for a genuine blocking issue.
- Do not send structured JSON status in the message body — use plain text.
- Always address teammates by NAME (e.g. `researcher-1`, `dev-2`), not by agent ID.
- Messages must contain actionable content, not just "I'm done".

**Gate scope:** the plain `message` DM does NOT require the Agent-Teams gate — only the structured protocol types (`shutdown_request`/`shutdown_response`/`plan_approval_response`) do. `SendMessage` plus the task tools stay available to a teammate even when its `tools` allowlist restricts everything else.

**Name→ID validation (CC v2.1.199+):** a DM is rejected if the recipient name was reassigned to a different agent; the send error reports which agent the name now reaches. Re-read the name before resending.

**Delivery timing (verified empirically):** a message to a busy recipient is **queued and delivered at its next tool-round boundary** — the recipient's in-flight tool call finishes first, then the message enters as a new user turn (it does NOT cut into a running tool call). A message to an idle recipient wakes it. This holds for a plain background subagent too (`SendMessage(to:
<agentId>)`), not only Agent-Teams teammates. To **preempt immediately** instead of queueing: in
the terminal select the teammate and press `Escape` (interrupt turn) / `x` (stop); for a subagent, `TaskStop`.

## Task Claiming — Order of operations

1. Claim the lowest-numbered unblocked task first (earlier tasks provide context for later ones).
2. `TaskUpdate` status → `in_progress` BEFORE starting work.
3. After completion: `TaskUpdate` → `completed` BEFORE sending a message to the lead.
4. Check `TaskList` after each task to discover newly unblocked tasks.
5. If all tasks are blocked: notify the lead and request help unblocking.

## Harness Backing — Race-Free Claims

Harness provides single-winner claim primitives via `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py`:

```
# Acquire claim (O_CREAT|O_EXCL — race-free, 1 winner)
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py acquire <task_id> [--lease-s N]

# Release when done (rename into .done/, do not delete)
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py release <task_id> --claim-id <id>

# Check state (UNCLAIMED | CLAIMED | STALE)
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py status <task_id>

# Reclaim a STALE claim from another teammate (atomic rename-consume)
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py reclaim <task_id>
```

Lease duration comes from the `HARNESS_CLAIM_LEASE_S` env var (default 14400s / 4h) — see `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py`.
Audit trail: every acquire/release/reclaim appends an event to the trace log.

## Plan Approval Flow

When `--plan-approval` or `plan_mode_required` is set in the task:

1. Teammate works read-only (no file edits) — research and plan the approach.
2. Teammate sends `plan_approval_request` to the lead via ExitPlanMode.
3. Lead reviews → `SendMessage(type: "plan_approval_response", approve: true/false, request_id: <id>)`.
4. Reject: teammate stays in plan mode, revises based on feedback, resubmits.
5. Approve: teammate exits plan mode and begins implementing.

Suggested lead criteria: approve only plans that include test coverage; reject plans that modify a schema without a migration.

## Monitor Pattern

```
1. Lead spawns teammates (run_in_background: true)
2. Teammates TaskUpdate → completed + notify lead
3. Lead checks TaskList after 60s or after each completion message
4. Lead acts on verified task state (spawn tester, shutdown, reassign)
5. Task status lag → message the owner directly before changing status
```

Idle is NOT a completion signal — check task status before drawing conclusions.
