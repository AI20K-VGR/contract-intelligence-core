# Honesty: the ledger, the noise band, the three verdicts

The verdict is the asset. An LLM reading a scoreboard will always tell a story for why the top number wins; `bakeoff_rank.py` stays silent when the gap is inside the noise. This drawer is the rulebook it follows — read it to trust + report the verdict without spinning it.

## The score ledger

Append-only JSONL at `state_dir()/bakeoff/<run-id>.jsonl`. One line per trial, never rewritten:

```json
{"run":"<id>","candidate":"redis","trial":1,"value":0.42,"elapsed_s":8.1,"tokens":12000,
 "actor":"user:hieubt","ts":"2026-06-15T10:22:31.004+00:00"}
```

Every record carries `actor` (via `resolve_actor()`) and an aware-UTC `ts`. Ledger = audit trail: lets anyone re-derive the verdict + see which candidate cost what.

## Representative score (by noise)

Each candidate's trials collapse to one comparable number:

| Noise | Trials | Representative | Why |
|---|---|---|---|
| `low` | 1 | the single value | metric is deterministic (LOC, bundle bytes) — trust one run |
| `medium` | ≥2 | the **worse** trial (max if lower-better, min if higher-better) | conservative — don't reward a lucky run |
| `high` | ≥3 | the **median** | robust to one outlier |

## The noise band (the honesty mechanism)

```
spread(candidate)     = max(trials) - min(trials)          # measured run-to-run noise
observed_spread_floor = max spread across ALL candidates
band                  = max( rel_band * |rep(best)| , observed_spread_floor )    # rel_band default 0.05
gap                   = how much the best beats the runner-up (≥ 0)

winner  ⇔  gap > band
```

`band = max(relative, observed_spread)` is the part that beats "LLM reads the numbers": if every candidate already swings ±8% between its own trials, then a 5% gap between two candidates **cannot** be a real win — the band widens to the measured noise and the verdict becomes a tie. The data polices itself.

No t-tests, no confidence intervals, no p-values — at n ≤ 5 they are pseudo-science, producing a scientific-looking but noisy number. The band rule is deliberately simple and conservative.

## The three verdicts

| Verdict | Exit | Meaning | What you do |
|---|---|---|---|
| `winner` | 0 | best beats runner-up beyond the band, trials sufficient | report the winner + full scoreboard; return the direction to the caller |
| `tie_within_noise` | 3 | gap ≤ band | **hand to the human.** Do not invent a winner. Often means "the metric doesn't discriminate" — report that honestly |
| `insufficient_trials` | 4 | some candidate has fewer trials than the noise minimum | collect more trials, or hand to the human. Never crown a winner on one lucky run |

## No silent cuts

The verdict lists EVERY candidate with its `rep`, `spread`, and trial count — losers included — plus `observed_spread_floor` and any `over_budget` candidates. When you report, show the whole board. A bake-off that hides the losers' scores is just an opinion with extra steps.

## Rank command

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/bakeoff_rank.py rank --run <run-id> \
  --direction lower --noise high --rel-band 0.05 --plan-dir plans/<slug>/ \
  --budget-seconds 180 --budget-tokens 60000
```

Writes `bakeoff-verdict.json` (schema `artifact-bakeoff-verdict`) into the plan dir and prints the verdict. Branch on the exit code: 0 proceed with the winner, 3/4 hand to the human.
