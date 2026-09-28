# Cycle-memory convention — `cycle_N.md`

A built-in autonomous loop is memory-blind between ticks: built-in `/goal` and `/loop` both reset context every tick, never fire `UserPromptSubmit` mid-loop — a tick can't remember what the previous tick did. Fix: file-based — each tick writes a `cycle_N.md` breadcrumb the next tick reads. ONE convention, TWO entry points — only difference is who armed the
run.

## The file shape

One file per tick, numbered, in the run's cycle dir — SAME dir the built-in host writes `goal.md` into, namely `goals/<goal_name>/`:

```
goals/<goal_name>/cycle_1.md, goals/<goal_name>/cycle_2.md, …
```

Each file has four sections:

```markdown
## Done
- what THIS tick actually finished (file:line / commit / artifact)

## Next
- the single next unit the following tick should pick up

## Blocker
- anything that stopped progress (or "none")

## Decisions
- any call made this tick the next tick must not re-litigate
```

## Read-latest, write-next protocol

Every tick:

1. **Read** the highest-numbered `cycle_N.md` first — work from that state, not memory (no memory across the tick boundary).
2. Do one unit of work toward the objective.
3. **Write** `cycle_{N+1}.md` with the four sections above before the tick ends.

The breadcrumb is the loop's only durable working memory inside the run.

## Scope — intra-run only

The cycle files live in the ephemeral goal/loop run dir, share its lifecycle, aligned to the `hs:autonomous-bell` cron-stop substrate (no new substrate). Durable **WITHIN one run only** — the run dir is ephemeral, so breadcrumbs do NOT persist **cross-run**. Do not treat `cycle_N.md` as a durable cross-run or cross-plan store; for that use the backlog register or a memory
file. The convention's whole job: bridge the tick-to-tick context reset of a single run.

## Two entry points, one shape — and what is OUT

- Built-in `/goal` (armed via `hs:goal`) writes this shape.
- Built-in `/loop` (the host's recurring re-run of a prompt) writes the SAME shape — only the arming differs.
- Explicitly OUT: **`hs:loop`**. The harness `hs:loop` is an IN-SESSION optimization loop — never loses context between iterations, so never memory-blind, needs no breadcrumb. Do not wire `cycle_N.md` into `hs:loop`.

## File-based only (independent of the reinject channel)

This convention is file-based ONLY — does NOT depend on `reinject_stop_context.py` (the Stop decision:block+reason channel), verified and shipped default-ON, goal-gated. The file breadcrumb is a separate, observable durable store that works
regardless of that channel — belt-and-suspenders, not a bet on an unproven mechanism.
