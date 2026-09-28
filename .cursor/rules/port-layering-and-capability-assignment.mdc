# Port layering & capability assignment (on-demand)

Load during `hs:port` Step 2 (Map) when deciding whether a piece of ported/adapted
behavior becomes real code, a script, a model-judgment call, or gets cut. Prevents
two failure modes: baking logic that needs code into prose the model re-derives
every run, and writing a script for a call that genuinely needs judgment.

## Decision tree — ask in order

1. **Does this step run the SAME WAY every time, with no judgment call?** Yes ->
   continue to question 2. No -> MODEL-JUDGMENT-SLOT.
2. **Does correctness depend on state/data this session cannot hold in context**
   (a large dataset, an external API, an iteration loop)? Yes -> ORCHESTRATOR-CODE.
   No -> continue to question 3.
3. **Is it callable standalone with no persistent cross-run state** (a CLI/gate the
   harness itself already shells out to)? Yes -> PURE-SCRIPT. No -> DROP (it adds
   no value the surrounding steps do not already cover).

## Cartesian-grid-gate example -> ORCHESTRATOR-CODE

A coverage-floor check that must hold across every (dimension x threshold) cell of a
grid is deterministic, repeats every run, and needs no judgment -> ORCHESTRATOR-CODE,
never a prose instruction asking the model to "check the grid" by hand each time.

### ORCHESTRATOR-CODE

Deterministic, state-bearing across runs, correctness matters at scale — lives in
the tier-2 orchestrator driver, never re-derived by the model turn by turn.

### PURE-SCRIPT

Deterministic, no persistent state across runs, callable standalone — the harness's
own pattern (`harness/scripts/*.py`, `harness/hooks/*.py`).

### MODEL-JUDGMENT-SLOT

Genuinely needs judgment: ambiguous input, a trade-off call, reading intent from
prose. **Never park a step here that needs code** just because writing the script
is more effort — a judgment slot re-derives a cheaply-computed fact every run
instead of computing it once, reintroducing the exact drift a script would prevent.

### DROP

The step adds no information the surrounding steps do not already produce, or its
result goes unused downstream. Cut it rather than porting it out of completeness.
