# P4 root cause and remaining blockers

Date: 2026-10-11

## Root cause

The low end-to-end recall is led by candidate generation. On the locked 37-positive dev sample, current candidate C at the production cap of 40 returns 11/37 positives (29.7%). Removing the cap raises this to 29/37 (78.4%) but produces 11,143 candidates, far beyond the per-document classification budget. Of the eight positives still absent when uncapped, five are GENERAL_SPECIFIC and three are REFERENCE; none matches an existing deterministic source rule. Expanding topic text from the first 80 characters to the full clause adds only one positive. Broad lexical overlap does not retrieve the remaining misses without producing hundreds or thousands of low-quality candidates.

The classifier is a second failure point. The diagnostic oracle achieved 13/20 exact on a positive-enriched dev sample. Two baseline repeats were 14/20 each; the checklist variant was 15/20 then 14/20. The worst-trial result ties, so the ablation provides no reliable improvement. These small samples do not estimate production recall.

## Why the Wilson recall gate cannot pass on this gold yet

The approved gold has only 1 CONFLICT, 2 DUPLICATE, 27 GENERAL_SPECIFIC and 7 REFERENCE positives. With a two-sided 95% Wilson interval, even a perfect result needs at least 22 independent successes for the lower bound to reach 0.85. The rarer labels cannot meet that even in the best possible outcome with the current sample. The plan's stronger readiness target is 60 positives per label, from at least three independent clusters, with cluster dominance controlled.

The current capped candidate coverage by label is 1/1 CONFLICT, 1/2 DUPLICATE, 8/27 GENERAL_SPECIFIC and 1/7 REFERENCE. Uncapped coverage is 1/1, 2/2, 22/27 and 4/7. These point estimates are already below the target for GENERAL_SPECIFIC and REFERENCE; their confidence bounds are lower still.

The eight uncapped misses were rederived against the exact locked recall frame and source documents: all are eligible, not Luong-1 exclusions, and not ancestor pairs. Their document-order gaps are 1, 1, 2, 4, 5, 6, 8 and 14. This confirms that there is no current long-distance semantic source rule, while also showing that locality alone is not a sufficient ranking fix. At K=40, 18 other approved positives are generated but ranked below the cap. An offline proximity-rank simulation improved candidate coverage only from 11/37 to at most 15/37 on the tested grid, so that heuristic is not a passing remediation.

## What is not a fix

- Increasing top-K alone exceeds the classifier request budget and still leaves most positive pairs below the shortlist.
- The prompt checklist did not improve worst-trial exact quality.
- Treating AI blind annotations or model suggestions as user-approved gold would invalidate the evaluation.
- Lowering the Wilson floor, candidate coverage target, or false-DUPLICATE rule would conceal the failure rather than resolve it.

## Data available for the next review packet

The current locked dev corpus has 21 documents. Two additional local tranches contain 29 and 34 documents, but they overlap on 29 documents: the union has 34 unique documents, only five beyond the first tranche. No approved gold/review lock was found for either tranche. They can support a fresh candidate and annotation packet after versioned split/cluster checks; their model-generated labels must remain suggestions until the user reviews them. The user's waiver removes the independent-second-review requirement, but does not convert AI labels into human-approved evidence.

## Model selector probe status

The first preregistered semantic-selector command did not produce a captured, schema-valid result artifact. The command runner returned without usable output, so no metric from that attempt is reported; it is marked invalid/unscored in the local run ledger. A separate bounded retry is preregistered for four requests over only the 32 locked dev documents (balanced by input size), capped at 500,000 total tokens and 550 seconds. It will return node-ID pairs only. No held-out data is included. Do not describe the first attempt as a successful experiment.

## Product state

P4 remains BLOCKED; P5 remains locked; the runtime feature flag remains OFF. Existing offline regression evidence remains recorded in the P4 development report. Passing those tests proves the current code's regressions only; it does not clear candidate recall, classifier quality, gold-size or held-out gates.
