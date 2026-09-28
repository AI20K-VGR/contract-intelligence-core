# hs:critique — lens-set rationale (on-demand)

Fan-out mechanics (batching, lens independence, finding contract, hand-off to the consolidator) live inline in `SKILL.md` step 2 — load this file only when the *why* behind a lens-set pick needs justifying (e.g. a new default in `critique.yaml`, or explaining why `--lenses` overrides the config default).

## Why these lens sets

`"${HARNESS_BIN_ROOT:-.}"/harness/data/critique.yaml` ships the defaults; this is the reasoning behind them.

| Artifact type | Lenses | Why these |
|---|---|---|
| plan / decision / design | `hs:red-teamer`, `hs:independent-revalidator`, `hs:brainstormer`, `hs:product-value-critic`, `hs:market-fit-critic` | failure-mode + irreversibility; sealed-room re-derivation of the load-bearing claim; assumption / alternative challenge; desirability (real user need, riskiest assumption); positioning (alternatives, defensibility, value capture) |
| code / diff | `hs:red-teamer`, `hs:code-reviewer`, `hs:independent-revalidator` | attack surface; production-readiness (concurrency, trust boundary, N+1); independent re-derivation of a claimed result |

Each lens is an existing read-only agent already carrying the Evidence Filter (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`): findings anchor to `file:line`/a reproduction/a triggering input, and separate `proven` from `suspected` (`[ASSUMED]`).

## Hand-off

For what to pass to `hs:critique-consolidator` and what comes back, see `consolidation-contract.md`.
