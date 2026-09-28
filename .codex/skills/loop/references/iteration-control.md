# iteration-control — loop heuristics (on-demand)

Required-every-iteration reads (git log/diff/tsv + 3 review Qs) and the atomicity test now live inline in `SKILL.md` Phase 1/Phase 2. Load this file for pattern heuristics beyond the inline summary.

## Exploiting successful patterns

- Files of the same type that improved before → try adjacent files
- Technique that was KEPTed (e.g., adding null guard) → apply to unchecked functions
- Module that yielded large delta → prioritize next

## Avoiding failed patterns

- File + technique pair already DISCARDed → do not retry the same pair
- Zero-delta change (refactor that did not move the metric) → skip
- Metric fluctuating on one file → leave it, move to another file

## Stuck — rotate strategy

| Consecutive discards | Action |
|---|---|
| 3 | Re-read log, switch to a different file area or technique |
| 5 | Analyze loop-results.tsv for patterns → change direction explicitly |
| 10 | Stop — see `references/exit-conditions.md` |

## Technique selection by metric

| Metric | Starting technique |
|---|---|
| Test coverage | Add test cases for uncovered branches; fill edge cases |
| Lint / type error | Fix individual errors, do not mass-refactor |
| Bundle size | Tree-shake unused imports; replace heavy dependencies |
| Build time | Split chunks; remove synchronous dependencies |

Full metric library (verify commands by stack): see hs:loop references — adapt to project toolchain.
