# Loop pattern — running gemini for many rounds, Claude-driven

This is a **pattern Claude reads and executes by hand**, not an engine. There is no hook, no autopilot, no gemini self-drive. Claude holds every round: spawn a `gemini-relayer` (one call), score the result, decide continue/stop, and — if continuing — spawn a FRESH relayer with the delta. The loop lets a second-engine pass iterate to a bar without one round's I/O flooding main context.

## Why Claude drives (and what is safe by construction)

The round cap is **model-honored**, exactly like the autonomy bell's STOP: the number lives in `gemini-partner.yaml` (`loop.max_rounds`, default 3) and Claude honors it. There is deliberately no code that rejects `round_n > max_rounds`.

What IS safe by construction — three independent facts, none of which is the cap:

1. **gemini never self-drives.** It is a function: no spawn, no hook, no ability to re-invoke itself. It answers once and returns.
2. **The relayer makes one companion call per spawn** (see `agents/gemini-relayer.md`). It never loops. More rounds means Claude spawns it again.
3. **No Stop-hook.** This loop is NOT wired to a Stop hook. A Stop-hook that injects `additionalContext` re-invokes the model and runs away (the harness learned this the hard way with goal-cycle autopilot — fixed by gating on an explicit `goal_status`, not letting the hook self-continue). **Do NOT wire this loop to a Stop hook.** If you ever need to harden the cap, add a guard that reads
   the highest `round_n` in the job registry and refuses beyond `max_rounds` — a deliberate option, not required here.

So: the *safety* is gemini-is-a-function + one-call-per-spawn + no-hook. The *cap* is a discipline Claude keeps.

## Memory model — fresh spawn + delta, never a session resume

Each round spawns a NEW relayer (a new `gemini -p` print process, a new session). Claude does NOT resume gemini's prior session. Instead Claude carries forward only what it chooses — the **delta**: "here is what you found last round; here is what is still open; focus on X." This keeps provenance clean (every round's input is exactly what Claude handed over) and keeps Claude in control of what
gemini sees.

The job registry stamps `round_n` on each round's records (append-only), so the lineage of a multi-round engagement is auditable after the fact.

## The three modes (chosen at call time)

Pick the mode from the task before the first round.

### (a) converge — mechanical, hs:loop discipline

Stop when **no NEW finding** appears. A finding's identity is `file:line + normalized-summary`; "new" means an identity not seen in prior rounds. Stop when a round adds ≤ k new findings (k often 0) — i.e. the set has converged. Mechanical stop rule, `hs:loop` family: the metric is counted, not judged.

### (b) target — mechanical, hs:loop discipline

Stop when a **mechanical metric Claude measures between rounds** hits its target: coverage %, a count, a size. Claude runs the measurement itself (a test run, a grep, a line count) — gemini does not self-report the metric. Also `hs:loop` discipline: the stop is a number crossing a threshold.

### (c) judge — Claude-driven, NOT hs:loop

Stop when a **criterion Claude sets for this task** is met, scored by Claude each round. The metric here is a judgment ("is the analysis deep enough?", "did it cover the security angle?"), so this is a SEPARATE track from the mechanical modes above — it is not `hs:loop`, because `hs:loop` is for counted metrics. Keep the two straight: converge/target are counted; judge is judged.

## The loop, step by step

```
mode ← converge | target | judge          (chosen from the task)
max  ← gemini-partner.yaml loop.max_rounds (default 3)
seen ← {}                                  (finding identities, for converge)
round ← 1
task  ← the initial prompt

while round <= max:
    spawn a gemini-relayer:
        gemini_companion.py <verb> [--skill <name>] -p "<task>" --round <round>
    read the returned envelope (verbatim)

    STOP?  by mode:
        converge → no new file:line finding vs `seen`  → STOP
        target   → Claude measures the metric ≥ target → STOP
        judge    → Claude's criterion met              → STOP
    if STOP: break

    build the delta (what is still open / focus for next round)
    task ← original task + delta
    round ← round + 1

if round > max: STOP at the cap (model-honored) — report that the cap was hit,
                do not silently keep going.
```

Notes:
- `--round <n>` only stamps the registry; it does not change gemini's behavior.
- Choose `<verb>` and `--skill` the same way as a one-shot: consult the `injectable` allowlist (a skill must be `injectable: true`) before naming a skill; never inject an executor/spine skill.
- Parallel fan-out is orthogonal: independent engagements can each run their own loop in their own relayer spawns.

## Boundaries

- **No hook, ever.** This pattern is prose Claude follows. Wiring it to a Stop hook (or any hook) is out of bounds — the autopilot the harness forbids.
- **Cap is honored, not enforced.** Respect `max_rounds`; report when you hit it.
- **Fresh spawn + delta only.** Never resume a gemini session to "remember" — carry the delta forward explicitly.
- **Keep converge/target separate from judge.** Mechanical vs judged; do not blur a judgment into an `hs:loop` count.
