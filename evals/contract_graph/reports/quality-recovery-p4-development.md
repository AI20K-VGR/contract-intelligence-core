# P4 development experiments

**Status:** `BLOCKED`; offline implementation and regression tests pass, but the development quality gate does not.

## Candidate coverage

| Variant / cap | Candidates | Recall-frame pairs hit | CONFLICT | DUPLICATE | GENERAL_SPECIFIC | REFERENCE |
|---|---:|---:|---:|---:|---:|---:|
| B / 40 | 720 | 55/600 | 0/1 | 1/2 | 8/27 | 1/7 |
| C / 40 | 1,000 | 69/600 | 1/1 | 1/2 | 8/27 | 1/7 |
| C / 80 | 1,646 | 107/600 | 1/1 | 1/2 | 10/27 | 1/7 |
| C / uncapped | 11,143 | 424/600 | 1/1 | 2/2 | 22/27 | 4/7 |

Candidate C now retains B core candidates under the same per-document top-K, then uses remaining slots for other sources. At K=40 coverage is 11/37 (B: 10/37), C/80 reaches 13/37, and uncapped C reaches 29/37. A dev-only reconciliation found all 8 uncapped misses (5 GENERAL_SPECIFIC, 3 REFERENCE) absent from current candidate source rules, rather than dropped by the cap or pair exclusions. Uncapped C emits 11,143 candidates, too many for practical classification.

## Classifier oracle

The original oracle measured 13/20. Two registered baseline repeats on the same 20-pair dev sample each measured 14/20. A real checklist prompt variant measured 15/20 and 14/20. All four repeats served `gpt-5.5` and had zero false DUPLICATE predictions. The worst-trial overall score and per-label counts tie between baseline and checklist, so the evidence does not justify changing the baseline prompt. This small, positive-enriched sample is diagnostic only.


## Blockers

- The approved set has 1 CONFLICT, 2 DUPLICATE, 27 GENERAL_SPECIFIC, and 7 REFERENCE positives. Each label is below the plan’s minimum of 60.
- Candidate coverage at K=40 is 11/37 overall and below 95% for every positive label. Uncapped C reaches 29/37 but emits 11,143 candidates; the eight misses (5 GENERAL_SPECIFIC, 3 REFERENCE) have no current source rule.
- Baseline and checklist prompt trials are complete (two each), with no measurable worst-trial winner at n=20; prompt ablation does not clear the quality gate.
- The user explicitly waived independent second human annotation. The AI blind annotation remains labeled as AI annotation, not human review; this waiver is not a P4 quality gate.
- P5 and held-out remain locked. No held-out files were read or scored.

## Verification

- Candidate/classifier/evaluation tests after prompt variant: **100 passed**.
- Builder/consent/flag/predictor regression tests: **105 passed in 144.10s**.
- The new candidate preservation test failed before the implementation and passed after it.
- Runtime flag remains **OFF**.
