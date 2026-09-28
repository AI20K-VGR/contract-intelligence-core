# Sampled-rate reporting (on-demand)

Load when a claim is a **rate** — an accuracy, a pass fraction, a coverage percentage, a
detector's recall, an agreement score. The engine is `harness/scripts/wilson.py`.

A rate measured on a sample is not a fact; it is an estimate with a width. Report the
width or do not report the rate.

## The claim grammar

`[OBSERVED]` on a rate is valid only with **`k/n` and an interval**. A bare
`[OBSERVED] 92% accuracy` is malformed — downgrade it to `[ASSUMED]` until the counts
and the interval are there. Labels: `verification-mechanism.md`.

```
python3 harness/scripts/wilson.py --k 8 --n 8 --conf 0.95 --method wilson --json
```

Write it as `k/n rate [lo, hi]`. Carry `k` and `n`, not just the bounds — bounds alone
cannot be re-pooled, re-derived, or argued with.

## Choosing the method

| method | use it when |
|---|---|
| `wilson` | default; the primary number in every report |
| `wilson-cc` | you want the conservative reading at small `n` |
| `clopper-pearson` | a guarantee is required and width is acceptable |
| `jeffreys` | the shortest interval, Bayesian-flavoured |

Report one method and name it. Do not shop for the method whose bounds suit the
conclusion; pick before the numbers are in.

## Never conclude from an interval that straddles the line

A rate is "above the threshold" only when the interval's **lower bound clears it**. A
point estimate above the line with an interval spanning it is *"not distinguishable from
acceptable"*, and the honest next step is more samples, not a verdict. Say
`UNSUPPORTED at n=<n>` rather than reporting the flag as if it were established.

Comparing two rates: use the difference interval (`--diff`), or `--mcnemar` on the same
test set. **Overlapping intervals are not a comparison** — do not use them as one.

## Before the probe, not after

- Fix `n` **before** the run, and say what it was fixed to. `--min-n` answers "how many
  samples do I need for this threshold": use it instead of "run a few to be safe".
- Record how many candidates or dimensions were tried. A best-of-twenty reported as one
  result is a different number than it appears to be.
- Record how many tuning rounds the golden set has seen.

State all three with the rate. A rate whose `n` was chosen after seeing the data is
`[ASSUMED]`.

## LLM-scored numbers

A gate or report containing LLM-judged scores carries a **judge calibration record** —
the confusion matrix over at least 50 balanced human-scored samples (`--judge-screen`,
then `--judge-adjust` to correct the observed rate). Without that record the number is
`[ASSUMED]`, whatever its interval says. Never fabricate the calibration to satisfy this.

## Clustered samples

Samples drawn from a few sources (files, repos, sessions) are not independent, and the
naive interval is too narrow. Use `--clusters` for the design-effect-adjusted interval,
and say how many clusters there were.

## The Bayesian second number

`P(p ≥ T)` (`--bayes --prob-ge`) is reported **alongside** Wilson, never instead of it —
the two answer different questions. A prior needs a link to its source evidence and a
weight `w ≤ 0.5` with a stated justification. An invented prior outweighs thousands of
real samples.

## The failure this rule exists to prevent

Pasting an interval into a report because it looks rigorous, and reading none of the
above. Four signs it has happened: the method is never named; `n` appears nowhere; a
flag fires on evidence whose interval straddles its own threshold; two rates are called
different because their intervals "overlap a bit".
