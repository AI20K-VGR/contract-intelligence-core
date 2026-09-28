# hs:critique — refute loop (on-demand, `--loop` only)

Load ONLY when the user passes `--loop`. A normal critique runs once: lenses -> consolidate -> report. The loop adds a defense pass so a contested verdict is tested before it stands. Pattern mirrors `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/predict/references/chain-modes.md` (`--chain reason`).

## When to loop

Use `--loop` when the consolidated verdict is contested — a blocker the artifact's author would plausibly rebut, or a `suspected` finding doing load-bearing work. Skip when the verdict is already clean (PASS, nothing to defend) or every blocker is `proven` and unarguable (defending a proven data-loss path wastes cycles — fix it).

## Protocol

```
1. Critique (round 1)
   - Run the lens fan-out + consolidate as normal (critique-protocol.md + consolidation-contract.md).
   - Take the surviving blockers and load-bearing majors as the contested set.

2. Refute
   - For each contested finding, run a defense pass that tries to REBUT it with evidence:
     does the anchor actually trigger? is there a guard the lens missed? is the consequence real?
   - The refutation is held to the same Evidence Filter: a rebuttal needs its own anchor
     (file:line / repro / input) or it is itself [ASSUMED] and does not overturn the finding.

3. Re-consolidate
   - Feed the original findings + the refutations back to critique-consolidator.
   - A finding rebutted with proven evidence is downgraded or dropped (record why).
   - A finding whose rebuttal is only [ASSUMED] stands.

4. Convergence check
   - STOP when the surviving-blocker set is unchanged from the previous round, OR all blockers are
     resolved, OR loop.max_rounds ("${HARNESS_BIN_ROOT:-.}"/harness/data/critique.yaml, default 3) is reached.
   - Otherwise feed the survivors back to step 2.

5. On max_rounds without convergence
   - Surface the lineage (what each round added/removed) and hand the unresolved set to the user —
     do NOT silently pick a side.
```

## Output (append to the critique report)

```
## Refute lineage (--loop)

| Round | Contested set | Rebuttals (anchored) | Survivors |
|-------|---------------|----------------------|-----------|
| 1 | [blockers + load-bearing majors] | [proven rebuttals only] | [what stood] |
| 2 | ... | ... | ... |

## Converged verdict
[Final verdict + the rationale, replacing round 1's verdict. Note any finding dropped on a proven
rebuttal and the evidence that dropped it.]
```

Tone stays neutral: the refute pass argues with the finding's evidence, never the lens or the author. A rebuttal that cannot anchor does not win.
