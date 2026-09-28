# The Lead's Coordination Loop

> Load this file for the lead's RUNTIME control loop — the single spine that stitches spawn →
> assign → monitor → stall-detect → recover → merge → shutdown. The detail of each step lives in
> the drawers this file points at; nothing here is re-pasted. Read this first, then open the
> named drawer only for the step you are on.

The lead is a **state machine**, not a fire-and-forget spawner. After it spawns teammates it does not go quiet — it runs the loop below until every task is `completed` (or explicitly abandoned) and every teammate has approved shutdown. Skipping the loop is how teams stall silently: a dead teammate looks identical to a busy one if nobody checks task state.

## The loop (one pass per monitor tick)

```
0. PLAN     TaskCreate x N with dependencies (blocked tasks wait on their blockers)
1. SPAWN    Agent(name=…, run_in_background:true[, isolation:"worktree"]) — one per owned slice
2. ASSIGN   tell each teammate its task, or let them self-claim lowest unblocked
            → claim races are single-winner via "${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py (messaging-protocol.md)
3. MONITOR  wait a tick (60s, or a teammate's completion message), then TaskList
4. CLASSIFY for each in_progress task, decide: PROGRESSING | STALLED | DONE | FAILED
5. RECOVER  act on STALLED/FAILED (redirect → replace → reassign — see below)
6. BARRIER  when all tasks in a dependency layer are DONE, merge that layer before the next
7. LOOP     back to 3 until no pending/in_progress tasks remain
8. SHUTDOWN shutdown_request each teammate; the implicit team ends with the session
```

Steps 0-2 detail: `references/roles-and-ownership.md` (slicing + git safety) and `references/messaging-protocol.md` (claim order, `claims.py` primitives, plan-approval flow). Step 8 detail: `references/lifecycle-and-shutdown.md`.

## Step 4 — classifying a task (the part everyone gets wrong)

**Idle is NOT done.** A teammate goes idle after every message it sends; that is normal, not a completion signal. Never conclude from silence. Classify from *task state + claim state*, not from whether a teammate is talking:

| Signal | Reading |
|---|---|
| `TaskUpdate` → `completed` + a completion message | **DONE** — verify the artifact, then act |
| `in_progress`, claim fresh (`claims.py status` = CLAIMED), teammate messaged recently | PROGRESSING — leave it |
| `in_progress`, claim `STALE` (lease expired), no message since last tick | **STALLED** — recover |
| teammate reported an error / rejected a task / crashed pane | **FAILED** — recover |
| `in_progress` but task status looks lagged | message the owner BEFORE changing status |

Lease length is the `HARNESS_CLAIM_LEASE_S` env var (default 14400s / 4h, see `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py`) — a claim older than its lease with no progress is the definition of STALLED.

## Step 5 — recovery ladder (cheapest move first)

Escalate only when the cheaper move fails. This is the canonical ladder — `lifecycle-and-shutdown.md` § Error Recovery points back here.

1. **Redirect** — `SendMessage` the teammate adjusted instructions. Waking an idle teammate with a message is often all it needs. No task-state change.
2. **Replace** — teammate is genuinely stuck/dead: `shutdown_request` it, reset its task `TaskUpdate → pending` (releasing the STALE claim via `claims.py reclaim`), spawn a fresh teammate with the SAME name for the same slice. Ownership stays put; the worktree is re-handed.
3. **Reassign** — the task is fine but the owner cannot finish: `TaskUpdate` the task to another teammate to unblock its dependents. Use when a whole slice is blocking the critical path.

Order matters: redirect is free, replace costs a re-spawn + lost partial work, reassign risks ownership collisions if the new owner's globs overlap. Never reassign into overlapping file ownership — that reintroduces the write-conflict the worktree isolation was there to prevent.

## Step 6 — the merge barrier

Worktree-isolated devs each land on their own branch; the lead is the ONLY merger. Barrier rule:
**do not merge a layer until every task in it is DONE and verified.** Merge in dependency order (a layer's blockers first) so a downstream branch never rebases onto an unmerged upstream. A single failed task in a layer holds the whole layer's merge — recover it (step 5) before crossing the barrier. This is the one place the loop is genuinely synchronous; everywhere else teammates run free.

## Delegate mode (lead-as-pure-orchestrator)

When the lead should do nothing but coordinate, `Shift+Tab` into delegate mode restricts it to spawn/message/shutdown/task tools — no code editing. Use for large fan-outs where the lead running the loop full-time beats also holding an implementation slice. Detail: `references/agent-teams-controls-and-modes.md` § Delegate Mode.

## Loop invariants (violating any = a stalled or corrupt team)

- **Every monitor tick ends with a `TaskList` read**, not with an assumption about who is busy.
- **Verify the artifact on DONE** before acting on it — a `completed` status is a claim, not proof.
- **Recover before you merge** — the barrier never crosses on a FAILED task.
- **One merger** — only the lead merges worktree branches; teammates never merge each other's.
- **No silent abandonment** — a task you give up on is explicitly closed with a handoff note, not left dangling `in_progress`.
