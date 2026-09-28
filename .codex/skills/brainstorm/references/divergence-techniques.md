# Divergence techniques — on-demand drawer

Load when in the Analysis phase and the `hs:brainstormer` agent needs a structure for exploring multiple directions. Do not read in --critique mode.

## Option comparison framework

Present each option across the following dimensions:

| Dimension | Guiding question |
|---|---|
| Complexity | How many moving parts? Who maintains this 6 months from now? |
| Cost (build + run) | Implementation time + operating cost at scale? |
| Latency / throughput | How is the hot path affected? |
| Maintainability | Hidden coupling? What assumption change would break this? |
| Second-order effects | What downstream is pulled along? Who else is affected? |
| Reversibility | If wrong, how costly is a rollback? |

## The "simplest viable option" rule

In every brainstorm, explicitly identify the option with the least complexity that still meets the requirements. Name it "MVS" (minimum viable solution) and place it first on the list. Default to the MVS unless there is specific evidence it is insufficient.

## Scope decomposition

A request describing ≥3 independent concerns (e.g., "build platform with chat, billing, analytics") → decompose first:

1. List the independent pieces.
2. Draw a dependency graph (text, no diagram tool needed).
3. Propose a build order (bottom-up by dependency).
4. Brainstorm each piece separately; each sub-session has its own scope boundary.

Do not brainstorm the whole block at once → no meaningful trade-offs emerge.

## Exploration techniques (choose 1-2 per problem)

- **Reversal**: assume the opposite approach — what actually happens?
- **Constraint removal**: if constraint X is removed, what is the best solution?
  Then ask: is constraint X real?
- **Analogy mapping**: how is a similar problem solved in another domain? Map the analogy onto the current domain.
- **Failure-first**: start from "what breaks fastest" → work backward to a design that avoids that failure.

## Checklist before ending Analysis

- [ ] ≥2 options that are genuinely different (not variants of the same idea)
- [ ] MVS is clearly named
- [ ] Each option has ≥1 second-order effect
- [ ] Reversibility of each option is stated
- [ ] No option has only upsides — if so, analysis is incomplete
