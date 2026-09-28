# Authoring protocol — preparing a built-in /goal run

`hs:goal` runs ONCE at the start, then hands the loop to built-in `/goal`. Detail behind the three START actions in `SKILL.md`.

## Why authoring-time, not loop-time

Verified from the binary: built-in `/goal` takes a string objective, self-iterates until its Stop-hook reports "met". Two facts shape everything here:

1. The loop **resets context every tick**, **never fires `UserPromptSubmit` mid-loop** — rule layer and terminal voice are NOT re-injected during the run (memory: autonomy-loop-bypasses-context-injection, verified 0/30).
2. So the run cannot rely on conversation memory — must work from FILES: self-contained `goal.md`, the bell ledger, `cycle_N.md` breadcrumbs.

`hs:goal` cannot change the loop (built-in); it makes the run self-sufficient before the loop starts.

## Action 1 — generate a NEW self-contained goal.md

Interview for three things, then write into a fresh `goal.md`:

- **Objective** — the string the loop iterates toward.
- **Acceptance** — what "met" means concretely (the Stop-hook's target). Vague acceptance is the main way a goal run never ends or ends early.
- **Scope fence** — what is explicitly OUT, so the loop does not wander.

Include a pointer to `harness/rules/` in the file itself — the loop won't have rules re-injected, so the reference must be IN the goal.md.

**Authoring boundary:** see SKILL.md Boundaries (always author a NEW `goal.md`) — editing an existing one couples this run to another run's leftovers.

## Action 2 — arm the bell with a run tag

Arm `hs:autonomous-bell` (see its SKILL.md) keyed by the run tag (cron id / goal run id). Two threads matter:

- The bell's stop decision is a consecutive-empty counter read from disk — the deterministic off-switch the memory-blind loop cannot make from recollection.
- The bell's backlog evidence is **run-scoped**: any backlog item the run defers is added with `source_ref: <run-tag>`, bell reads `autonomy_bell.py --backlog-signal --source-ref <run-tag>` — producer side of the run scope the bell consumes; a global open item from another run must never pin THIS run to `found` (C2).

## Action 3 — scaffold the cycle dir

The built-in host writes `goal.md` to `goals/<goal_name>/goal.md` (relative to launch cwd). Scaffold cycle memory in that SAME dir — `goals/<goal_name>/cycle_N.md`, beside the host's `goal.md` — so each tick appends a breadcrumb the next tick reads. Shape + read-latest/write-next protocol: `references/cycle-convention.md`. The dir shares the goal run's lifecycle
(durable WITHIN one run only); the whole `goals/` tree is gitignored — ephemeral per-run, never a tracked artifact.

## Then hand off

Start built-in `/goal iterate-until-met` and stop. `hs:goal` owns no iteration code: built-in engine drives the loop, bell owns the stop decision, cycle breadcrumbs carry memory across ticks — the skill's whole job was making those three things possible before the loop began.
