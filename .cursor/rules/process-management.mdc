# Process and resource management

Load this when a step starts, reuses, or ends a long-running process: a dev
server, watcher, build daemon, tunnel, emulator, or a test runner you leave
running. It exists to stop orphaned processes accumulating until the machine
runs out of memory or the ports a project needs are all held by something
nobody owns any more.

## The failure mode

An agent starts a dev environment and abandons it. The next run finds the port
busy and — instead of stopping the stale owner — picks a different port and
starts a second process. Repeat that a few times and the machine carries
duplicates of everything, each holding a port.

Worktrees make it worse. Each worktree spawns its own processes, and when the
worktree is removed or the session ends, those processes stay behind with no
path back to an owner.

## Rules

- **Track what you start**: command, PID, port, and which worktree it belongs
  to. Prefer the Bash tool's `run_in_background` over a detached `&` — a
  backgrounded run re-invokes the model when it exits, so the exit is
  observable. A `&` you cannot see finish is an orphan waiting to happen.
- **Look before you spawn.** Check whether a process is already serving this
  project or port. Reuse it or stop it; never start a duplicate.
- **Bind a deterministic port per project/worktree.** On "address in use",
  identify and stop the stale owner rather than incrementing to a free port.
  Inspect with `ss -ltnp` or `lsof -i :PORT` on Linux/macOS, `netstat -ano` on
  Windows.
- **Stop what you started when its task, session, or worktree ends.** Terminate
  a worktree's background processes BEFORE removing the worktree, not after —
  after, you no longer have the path that identifies them.
- **Reconcile periodically.** List the processes you are still running and stop
  the ones that no longer map to an active task.
- **Stop cleanly first** (`SIGTERM`, or `pkill -f <pattern>`; `taskkill /PID` on
  Windows). Escalate to a hard kill only when the process ignores the signal.
- **Never wait on a wall clock.** A foreground `sleep` is blocked here for this
  reason. Wait on a condition (the Monitor tool with an until-loop), not on an
  elapsed-time guess — an assertion phrased as `elapsed < K` fails under load
  and passes for the wrong reason when the machine is idle.

## Safety — ownership before termination

Only stop a process you started or can prove you own.

This is not a formality. A detector scoped WIDER than your ownership will
accuse the innocent: a `ps -e` sweep matching a generic pattern in this repo
once named a process belonging to a different concurrent session, and the
recommended action would have killed another agent's work mid-run.

So, before any kill:

- Match on something that identifies YOUR process — the recorded PID, the port
  you bound, the worktree path — not on a command substring that any session
  could produce.
- Never let a `pkill` pattern be broad enough to catch an unrelated process. If
  the pattern would also match a process you did not start, it is the wrong
  pattern.
- Never terminate a process belonging to the user, another session, or the OS
  without confirmation.

When you cannot establish ownership, report the stale process and its evidence
and let the user decide. An unowned process left running is a smaller failure
than a killed one that belonged to someone else.
