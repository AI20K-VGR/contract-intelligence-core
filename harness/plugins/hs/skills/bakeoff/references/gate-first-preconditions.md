# Gate-first preconditions

A bake-off costs N× the build effort. Worth it only when ALL FOUR conditions hold. Gate exists so you do NOT bake-off a decision reasoning settles in a minute — the most common abuse.

## The four conditions

| # | Condition | Checked by | How |
|---|---|---|---|
| 1 | **Mechanical, discriminating metric** | machine (partial) | `bakeoff_rank.py` can't judge "discriminating" semantically, but the SKILL dry-runs the metric: it MUST exit 0 and print exactly one number (same contract as hs:loop). If every candidate lands in the band, the verdict returns `tie_within_noise` — which *is* the signal "your metric doesn't discriminate". |
| 2 | **Small N (2-4)** | machine | `preflight` rejects N<2 (pointless) and N>4 (cut by reasoning first). |
| 3 | **Cheap, bounded probe** | machine (partial) + judgment | `preflight` enforces the per-probe budget ceiling. Whether the probe is a *stub* (not a full feature) is your judgment — confirm it. |
| 4 | **Load-bearing, costly to reverse** | judgment | Pure product judgment. Confirm with the user. |

Any condition missing → **do NOT bake-off**. Fall back to `hs:predict` (LLM reasons, far cheaper).

## Machine half — preflight

Run before building any probe:

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/bakeoff_rank.py preflight \
  --candidate redis --candidate in-memory --candidate sqlite \
  --metric-cmd 'pytest -q tests/bench_latency.py | tail -1' \
  --budget-seconds 180 --budget-tokens 60000
```

- Exit 0 → `{"ok": true}`, proceed.
- Exit 2 → `{"ok": false, "reasons": [...]}`. Read the reasons, fix, re-run. Reasons include: N out of range, empty metric, unsafe metric (`rm -rf /`, `curl|sh`, fork bomb), no budget, budget over ceiling.
- At least one budget axis (`--budget-seconds` / `--budget-tokens`) is required. Ceilings default to 600s / 2,000,000 tokens; pass `--ceiling-seconds` / `--ceiling-tokens` to change them.

Then dry-run the metric ONCE in-tree: confirm it prints one number + exits 0. A metric needing the candidate's changes to run is fine — dry-run checks shape only, not value.

## Judgment half — the checklist (you + the user)

Before fanning out, get an explicit "yes" to BOTH:

- **Stub, not feature?** "Can each candidate be probed with a throwaway stub that measures only the contested axis, in under the budget?" If a candidate needs a 2-day full integration, the bake-off is more expensive than the thing you were trying to avoid — cut it.
- **Load-bearing + costly to reverse?** "If we guess wrong here, is it expensive to undo later?" If undoing is cheap, just guess and move on — reasoning is cheaper than N probes.

If either is "no" → fall back to `hs:predict` / `hs:brainstorm`. Record the skipped bake-off reason; do not silently downgrade.

## The fake-objectivity trap (read this)

The single most dangerous failure: a metric that is an LLM judgment in disguise (e.g. "a model scores each candidate's quality 0-10"). That pays N× the build cost and removes none of the unreliability — it just hides it behind a number that *looks* objective, which is worse than admitting "the LLM guessed". The metric must be a real number a shell command computes (latency ms, bundle bytes, %
tests passing, accuracy on a labelled set). If you cannot name such a metric, you do not have a bake-off — use `hs:predict`.
